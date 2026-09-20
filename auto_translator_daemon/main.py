"""
Chương trình chính (Entrypoint) của Auto Translator Daemon.
Quy trình tối ưu hóa:
1. Batch Query Drive + Whitelist Google Sheet.
2. Sắp xếp ứng viên theo cờ --sort-by (recent / oldest).
3. Lazy Streaming Inspection qua RAM (Zero Disk Usage) -> Đủ 300 chương DỪNG LẬP TỨC.
4. Chỉ tải DUY NHẤT các truyện được chọn vào thư mục tạm.
5. Dịch qua AGY CLI -> Hậu kiểm QC -> Ghi đè Drive -> Tự động xóa sạch thư mục tạm (Auto-clean).
"""
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Đảm bảo encoding UTF-8 và xả buffer thời gian thực
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "story-translator-cli"))

from app.services.gdrive import GoogleDriveService
from auto_translator_daemon.config import (
    DAILY_CHAPTER_LIMIT,
    MAX_CHAPTERS_PER_STORY,
    MAX_PARALLEL_WORKERS,
    BOUNDARY_STRATEGY,
    TIMEOUT_HOURS,
    STORAGE_DIR,
    TEMP_FAILED_DIR,
    format_chapter_ranges
)
from auto_translator_daemon.worker import process_single_resume_story, isolate_failed_story
from auto_translator_daemon.whitelist_manager import WhitelistManager
from auto_translator_daemon.web_priority_manager import WebPriorityManager
from auto_translator_daemon.drive_scanner import DriveScanner
from auto_translator_daemon.chapter_inspector import ChapterInspector
from auto_translator_daemon.queue_manager import QueueManager
from auto_translator_daemon.agy_runner import AGYRunner
from auto_translator_daemon.qc_validator import QCValidator
from auto_translator_daemon.drive_syncer import DriveSyncer
from auto_translator_daemon.telegram_notifier import TelegramNotifier

def parse_story_ids(raw_value) -> list:
    """
    Chuẩn hóa chuỗi story_id phân tách bằng dấu phẩy thành danh sách duy nhất.
    Ví dụ: "id_A, id_B, id_C" -> ['id_A', 'id_B', 'id_C']
    """
    if not raw_value:
        return []
    result = []
    seen = set()
    for item in str(raw_value).split(','):
        sid = item.strip()
        if sid and sid not in seen:
            seen.add(sid)
            result.append(sid)
    return result

def parse_args():
    parser = argparse.ArgumentParser(description="Auto Translator Daemon - Quét và dịch truyện tự động hàng ngày qua AGY CLI.")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ quét và lập danh sách hàng đợi qua RAM, không tải file, không gọi dịch và không upload Drive.")
    parser.add_argument("--sort-by", type=str, choices=["recent", "oldest"], default="recent", help="Tiêu chí sắp xếp ưu tiên: recent (modifiedTime mới nhất) hoặc oldest (tồn đọng lâu nhất). Mặc định: recent.")
    parser.add_argument("--chapters", "--limit", dest="chapters", type=int, default=DAILY_CHAPTER_LIMIT, help=f"Hạn mức tổng số chương dịch tối đa trong ngày (Mặc định: {DAILY_CHAPTER_LIMIT}).")
    parser.add_argument("--max-per-story", type=int, default=MAX_CHAPTERS_PER_STORY, help=f"Số chương tối đa phân bổ cho 1 bộ truyện trong phiên (0 = không giới hạn, Mặc định: {MAX_CHAPTERS_PER_STORY}).")
    parser.add_argument("--workers", type=int, default=MAX_PARALLEL_WORKERS, help=f"Số lượng truyện dịch song song cùng lúc (Mặc định: {MAX_PARALLEL_WORKERS}).")
    parser.add_argument("--strategy", type=str, choices=["ATOMIC", "SPLIT"], default=BOUNDARY_STRATEGY, help=f"Chiến lược xử lý khi chạm trần (Mặc định: {BOUNDARY_STRATEGY}).")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_HOURS, help=f"Timeout tối đa cho mỗi mẻ AGY CLI tính theo giờ (Mặc định: {TIMEOUT_HOURS} giờ).")
    parser.add_argument("--story-id", type=str, default=None, help='Chỉ định 1 hoặc nhiều story_id (phân cách bằng dấu phẩy: "id_A, id_B").')
    parser.add_argument("--exclude-story-id", type=str, default=None, help='Chỉ định loại trừ 1 hoặc nhiều story_id (phân cách bằng dấu phẩy: "id_A, id_B").')
    parser.add_argument("--no-upload", action="store_true", help="Bỏ qua bước upload/đồng bộ lên Google Drive (dùng cho chạy thử nghiệm an toàn).")
    return parser.parse_args()

def main():
    args = parse_args()
    start_time = datetime.now()

    target_story_ids = parse_story_ids(args.story_id)
    excluded_story_ids = set(parse_story_ids(args.exclude_story_id))
    if excluded_story_ids and target_story_ids:
        target_story_ids = [sid for sid in target_story_ids if sid not in excluded_story_ids]

    max_per_story = args.max_per_story
    if target_story_ids and "--max-per-story" not in sys.argv:
        max_per_story = 0

    print("=" * 70)
    print(f"🤖 AUTO TRANSLATOR DAEMON KHỞI ĐỘNG: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️ Cấu hình: Hạn mức = {args.chapters} chaps | Max/Truyện = {max_per_story if max_per_story > 0 else 'Không giới hạn'} | Song song = {args.workers} workers | Sắp xếp = {args.sort_by} | Chiến lược = {args.strategy} | Timeout = {args.timeout}h | Dry-run = {args.dry_run}")
    if target_story_ids:
        print(f"🎯 Chỉ định {len(target_story_ids)} story_id: {', '.join(target_story_ids)}")
    if excluded_story_ids:
        print(f"🚫 Loại trừ {len(excluded_story_ids)} story_id: {', '.join(excluded_story_ids)}")
    print("=" * 70)

    # 1. Khởi tạo dịch vụ
    try:
        notifier = TelegramNotifier()
        gdrive_service = GoogleDriveService()
        web_priority_mgr = WebPriorityManager()

        # Nếu gọi Web Priority API gặp lỗi -> Gửi cảnh báo qua Telegram ngay lập tức
        if web_priority_mgr.last_error:
            notifier.notify_warning("Lỗi kết nối Web Priority API", web_priority_mgr.last_error)

        scanner = DriveScanner(
            gdrive_service,
            whitelist_mgr=None,  # Lazy loaded ở Chặng 2 nếu Quota còn thiếu
            web_priority_mgr=web_priority_mgr
        )
        inspector = ChapterInspector(gdrive_service)
        queue_mgr = QueueManager(limit=args.chapters, strategy=args.strategy, max_per_story=max_per_story)
        agy_runner = AGYRunner(timeout_hours=args.timeout)
        qc_validator = QCValidator()
        syncer = DriveSyncer(gdrive_service)
    except Exception as e:
        print(f"❌ Khởi tạo dịch vụ thất bại: {e}")
        sys.exit(1)

    # 2. CHẶNG 1: Quét các truyện ưu tiên từ Web (Thịnh Phong Các API)
    # Lấy danh sách từ API trước, duyệt và thẩm định từng truyện qua RAM
    # Nếu chạm trần args.chapters -> BỎ QUA HOÀN TOÀN Chặng 2 (Google Sheet Whitelist)
    web_queue = []
    current_count = 0
    processed_story_ids = set()
    all_skipped_stories = []

    if target_story_ids:
        priority_targets = {sid: web_priority_mgr.get_story_info(sid) for sid in target_story_ids if web_priority_mgr.is_priority(sid)}
        if priority_targets:
            orig_stories = web_priority_mgr.priority_stories
            web_priority_mgr.priority_stories = priority_targets
            web_queue, current_count, processed_story_ids, web_skipped = scanner.inspect_web_priority_stories(
                inspector,
                limit=args.chapters,
                strategy=args.strategy,
                max_per_story=max_per_story
            )
            all_skipped_stories.extend(web_skipped)
            web_priority_mgr.priority_stories = orig_stories
    else:
        orig_stories = web_priority_mgr.priority_stories
        if excluded_story_ids:
            web_priority_mgr.priority_stories = {sid: info for sid, info in orig_stories.items() if sid not in excluded_story_ids}

        web_queue, current_count, processed_story_ids, web_skipped = scanner.inspect_web_priority_stories(
            inspector,
            limit=args.chapters,
            strategy=args.strategy,
            max_per_story=max_per_story
        )
        all_skipped_stories.extend(web_skipped)
        if excluded_story_ids:
            web_priority_mgr.priority_stories = orig_stories

    # CHẶNG 2: Whitelist Fallback (Chỉ chạy khi Quota ngày vẫn còn dư hoặc còn truyện chỉ định chưa xử lý)
    whitelist_queue = []
    unprocessed_targets = set(target_story_ids) - processed_story_ids if target_story_ids else set()

    if current_count >= args.chapters and not unprocessed_targets:
        print(f"\n🎯 Quota ngày ({args.chapters} chaps) đã được lấp đầy 100% bởi truyện Ưu Tiên Web!")
        print("⚡ BỎ QUA HOÀN TOÀN việc quét Google Sheet Whitelist và Google Drive.")
    else:
        remaining_quota = max(0, args.chapters - current_count)
        if unprocessed_targets:
            print(f"\n📑 [CHẶNG 2] Tiếp tục tìm kiếm {len(unprocessed_targets)} story_id còn lại trên Google Drive: {', '.join(unprocessed_targets)}...")
        else:
            print(f"\n📑 [CHẶNG 2] Quota còn dư {remaining_quota}/{args.chapters} chaps. Bắt đầu tải Google Sheet Whitelist để bù đắp...")

        # Khởi tạo WhitelistManager theo cơ chế Lazy Loading (chỉ tải khi thực sự cần)
        whitelist_mgr = WhitelistManager()
        scanner.whitelist_mgr = whitelist_mgr

        # Quét các nguồn trên Drive, tự động loại trừ các truyện đã xử lý ở Chặng 1 và các truyện bị exclude (Chống trùng lặp 100%)
        scan_excluded = processed_story_ids.union(excluded_story_ids)
        candidate_sources = scanner.scan_all_sources(
            sort_by=args.sort_by,
            excluded_story_ids=scan_excluded
        )

        if target_story_ids:
            for src in candidate_sources:
                candidate_sources[src] = [s for s in candidate_sources[src] if s['story_id'] in target_story_ids]

        whitelist_queue, wl_skipped = queue_mgr.build_lazy_queue(
            candidate_sources,
            inspector,
            current_count=current_count
        )
        all_skipped_stories.extend(wl_skipped)

    # Tổng hợp hàng đợi cuối cùng:
    queue = web_queue + whitelist_queue

    # In thông báo các truyện bị loại do nhảy cóc (nếu có)
    if all_skipped_stories:
        print(f"\n⚠️ ĐÃ LOẠI BỎ {len(all_skipped_stories)} BỘ TRUYỆN BỊ NHẢY CÓC / KHUYẾT CHƯƠNG:")
        for s in all_skipped_stories:
            badge_str = f" [{s['badge']}]" if s.get('badge') else ""
            vip_str = " [ƯU TIÊN WEB]" if s.get('is_web_priority') else ""
            print(f"  ❌ [{s['source']}]{badge_str}{vip_str} {s['story_id']}: {s['reason']}")

    if not queue:
        print("\n☕ Không có chương mới nào cần dịch hôm nay (toàn bộ truyện đã dịch 100% hoặc các truyện đều bị lỗi). Kết thúc phiên.")
        return

    # In danh sách hàng đợi đã chốt
    print("\n📋 DANH SÁCH CÁC BỘ TRUYỆN ĐƯỢC CHỌN VÀO HÀNG ĐỢI:")
    for idx, item in enumerate(queue, 1):
        chaps = item['chapters_to_translate']
        raw_total = (item.get('inspected_meta') or {}).get('raw_chapters_count')
        total_str = f" / {raw_total} chaps" if raw_total else ""
        tag_vip = " [⭐ ƯU TIÊN WEB]" if item.get('is_web_priority') else ""
        chaps_range_str = format_chapter_ranges(chaps)
        print(f"  {idx}. [{item['source']}] {item['story_id']}{tag_vip}: {len(chaps)} chương ({chaps_range_str}{total_str}) {'[DỊCH DỞ]' if item['is_partial'] else '[TRỌN VẸN]'}")

    if args.dry_run:
        print("\n🔍 Chế độ --dry-run đang bật. Đã hoàn tất mô phỏng quét qua RAM (0 byte ghi xuống ổ cứng).")
        return

    # Gửi thông báo bắt đầu ca dịch qua Telegram (kèm danh sách truyện bị loại nếu có)
    total_planned_chaps = sum(len(item['chapters_to_translate']) for item in queue)
    notifier.notify_session_start(
        queue,
        total_planned_chaps,
        args.chapters,
        args.sort_by,
        skipped_stories=all_skipped_stories
    )

    # 4. Thực thi dịch thuật, hậu kiểm QC và đồng bộ Drive
    execution_results = []
    temp_root = STORAGE_DIR / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)

    print(f"\n⚡ Kích hoạt Worker Pool ({args.workers} workers song song) để xử lý {len(queue)} bộ truyện...")

    if args.workers <= 1:
        # Chạy tuần tự nếu workers = 1
        for item in queue:
            res = process_single_resume_story(
                item=item,
                gdrive_service=gdrive_service,
                agy_runner=agy_runner,
                qc_validator=qc_validator,
                syncer=syncer,
                notifier=notifier,
                no_upload=args.no_upload
            )
            execution_results.append(res)
    else:
        # Chạy song song đa luồng
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_story = {
                executor.submit(
                    process_single_resume_story,
                    item,
                    gdrive_service,
                    agy_runner,
                    qc_validator,
                    syncer,
                    notifier,
                    args.no_upload
                ): item['story_id']
                for item in queue
            }

            for future in as_completed(future_to_story):
                story_id = future_to_story[future]
                try:
                    res = future.result()
                    execution_results.append(res)
                except Exception as exc:
                    print(f"❌ [{story_id}] Ngoại lệ bất ngờ từ worker thread: {exc}")
                    execution_results.append({
                        'story_id': story_id,
                        'chapters': 0,
                        'agy_status': 'THREAD ERROR ❌',
                        'qc_status': 'SKIPPED',
                        'sync_status': 'SKIPPED',
                        'duration': '0s'
                    })

    # 5. Báo cáo kết quả tổng kết & gửi Telegram kết thúc
    duration = datetime.now() - start_time
    duration_str = str(duration).split('.')[0]
    notifier.notify_session_end(execution_results, duration_str)

    print("\n" + "=" * 70)
    print(f"🏁 BÁO CÁO TỔNG KẾT PHIÊN CHẠY (Thời gian: {duration}):")
    print("-" * 70)
    print(f"{'Bộ Truyện':<20} | {'Số Chương':<10} | {'AGY':<12} | {'QC':<15} | {'Drive Sync':<12}")
    print("-" * 70)
    for r in execution_results:
        print(f"{r['story_id']:<20} | {r['chapters']:<10} | {r['agy_status']:<12} | {r['qc_status']:<15} | {r['sync_status']:<12}")
    print("=" * 70)

if __name__ == "__main__":
    main()

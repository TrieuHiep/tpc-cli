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
    BOUNDARY_STRATEGY,
    TIMEOUT_HOURS,
    STORAGE_DIR,
    TEMP_FAILED_DIR
)

def isolate_failed_story(temp_story_dir: Path, story_id: str):
    """Di chuyển thư mục truyện bị lỗi vào storage/temp_failed để phục vụ kiểm tra/debug."""
    if not temp_story_dir.exists():
        return
    failed_dest = TEMP_FAILED_DIR / story_id
    if failed_dest.exists():
        shutil.rmtree(failed_dest, ignore_errors=True)
    try:
        shutil.move(str(temp_story_dir), str(failed_dest))
        print(f"📦 [{story_id}] Đã chuyển dữ liệu lỗi sang {failed_dest} để phục vụ debug/kiểm tra!")
    except Exception as e:
        print(f"⚠️ Không thể di chuyển sang {failed_dest} ({e}), tiến hành xóa để dọn đĩa.")
        shutil.rmtree(temp_story_dir, ignore_errors=True)
from auto_translator_daemon.whitelist_manager import WhitelistManager
from auto_translator_daemon.web_priority_manager import WebPriorityManager
from auto_translator_daemon.drive_scanner import DriveScanner
from auto_translator_daemon.chapter_inspector import ChapterInspector
from auto_translator_daemon.queue_manager import QueueManager
from auto_translator_daemon.agy_runner import AGYRunner
from auto_translator_daemon.qc_validator import QCValidator
from auto_translator_daemon.drive_syncer import DriveSyncer
from auto_translator_daemon.telegram_notifier import TelegramNotifier

def parse_args():
    parser = argparse.ArgumentParser(description="Auto Translator Daemon - Quét và dịch truyện tự động hàng ngày qua AGY CLI.")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ quét và lập danh sách hàng đợi qua RAM, không tải file, không gọi dịch và không upload Drive.")
    parser.add_argument("--sort-by", type=str, choices=["recent", "oldest"], default="recent", help="Tiêu chí sắp xếp ưu tiên: recent (modifiedTime mới nhất) hoặc oldest (tồn đọng lâu nhất). Mặc định: recent.")
    parser.add_argument("--chapters", "--limit", dest="chapters", type=int, default=DAILY_CHAPTER_LIMIT, help=f"Hạn mức tổng số chương dịch tối đa trong ngày (Mặc định: {DAILY_CHAPTER_LIMIT}).")
    parser.add_argument("--strategy", type=str, choices=["ATOMIC", "SPLIT"], default=BOUNDARY_STRATEGY, help=f"Chiến lược xử lý khi chạm trần (Mặc định: {BOUNDARY_STRATEGY}).")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_HOURS, help=f"Timeout tối đa cho mỗi mẻ AGY CLI tính theo giờ (Mặc định: {TIMEOUT_HOURS} giờ).")
    parser.add_argument("--story-id", type=str, default=None, help="Chỉ định dịch riêng 1 story_id cụ thể (bỏ qua quét toàn bộ).")
    parser.add_argument("--no-upload", action="store_true", help="Bỏ qua bước upload/đồng bộ lên Google Drive (dùng cho chạy thử nghiệm an toàn).")
    return parser.parse_args()

def main():
    args = parse_args()
    start_time = datetime.now()

    print("=" * 70)
    print(f"🤖 AUTO TRANSLATOR DAEMON KHỞI ĐỘNG: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️ Cấu hình: Hạn mức = {args.chapters} chaps | Sắp xếp = {args.sort_by} | Chiến lược = {args.strategy} | Timeout = {args.timeout}h | Dry-run = {args.dry_run}")
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
        queue_mgr = QueueManager(limit=args.chapters, strategy=args.strategy)
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

    if args.story_id:
        if web_priority_mgr.is_priority(args.story_id):
            orig_stories = web_priority_mgr.priority_stories
            web_priority_mgr.priority_stories = {args.story_id: web_priority_mgr.get_story_info(args.story_id)}
            web_queue, current_count, processed_story_ids = scanner.inspect_web_priority_stories(
                inspector,
                limit=args.chapters,
                strategy=args.strategy
            )
            web_priority_mgr.priority_stories = orig_stories
    else:
        web_queue, current_count, processed_story_ids = scanner.inspect_web_priority_stories(
            inspector,
            limit=args.chapters,
            strategy=args.strategy
        )

    # CHẶNG 2: Whitelist Fallback (Chỉ chạy khi Quota ngày vẫn còn dư)
    whitelist_queue = []
    if current_count >= args.chapters:
        print(f"\n🎯 Quota ngày ({args.chapters} chaps) đã được lấp đầy 100% bởi truyện Ưu Tiên Web!")
        print("⚡ BỎ QUA HOÀN TOÀN việc quét Google Sheet Whitelist và Google Drive.")
    else:
        remaining_quota = args.chapters - current_count
        print(f"\n📑 [CHẶNG 2] Quota còn dư {remaining_quota}/{args.chapters} chaps. Bắt đầu tải Google Sheet Whitelist để bù đắp...")

        # Khởi tạo WhitelistManager theo cơ chế Lazy Loading (chỉ tải khi thực sự cần)
        whitelist_mgr = WhitelistManager()
        scanner.whitelist_mgr = whitelist_mgr

        # Quét 2 nguồn trên Drive, tự động loại trừ các truyện đã xử lý ở Chặng 1 (processed_story_ids - Chống trùng lặp 100%)
        candidate_sources = scanner.scan_all_sources(
            sort_by=args.sort_by,
            excluded_story_ids=processed_story_ids
        )

        if args.story_id:
            for src in candidate_sources:
                candidate_sources[src] = [s for s in candidate_sources[src] if s['story_id'] == args.story_id]

        whitelist_queue = queue_mgr.build_lazy_queue(
            candidate_sources,
            inspector,
            current_count=current_count
        )

    # Tổng hợp hàng đợi cuối cùng:
    queue = web_queue + whitelist_queue

    if not queue:
        print("\n☕ Không có chương mới nào cần dịch hôm nay (toàn bộ truyện đã dịch 100%). Kết thúc phiên.")
        return

    # In danh sách hàng đợi đã chốt
    print("\n📋 DANH SÁCH CÁC BỘ TRUYỆN ĐƯỢC CHỌN VÀO HÀNG ĐỢI:")
    for idx, item in enumerate(queue, 1):
        chaps = item['chapters_to_translate']
        tag_vip = " [⭐ ƯU TIÊN WEB]" if item.get('is_web_priority') else ""
        print(f"  {idx}. [{item['source']}] {item['story_id']}{tag_vip}: {len(chaps)} chương ({chaps[0]} -> {chaps[-1]}) {'[DỊCH DỞ]' if item['is_partial'] else '[TRỌN VẸN]'}")

    if args.dry_run:
        print("\n🔍 Chế độ --dry-run đang bật. Đã hoàn tất mô phỏng quét qua RAM (0 byte ghi xuống ổ cứng).")
        return

    # Gửi thông báo bắt đầu ca dịch qua Telegram
    total_planned_chaps = sum(len(item['chapters_to_translate']) for item in queue)
    notifier.notify_session_start(queue, total_planned_chaps, args.chapters, args.sort_by)

    # 4. Thực thi dịch thuật, hậu kiểm QC và đồng bộ Drive
    execution_results = []
    temp_root = STORAGE_DIR / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)

    for item in queue:
        story_id = item['story_id']
        chaps = item['chapters_to_translate']
        temp_story_dir = temp_root / story_id
        story_start = datetime.now()

        print("\n" + "#" * 60)
        print(f"▶️ TIẾN TRÌNH DỊCH: [{item['source']}] {story_id} ({len(chaps)} chương)")
        print("#" * 60)

        # 4.1. Tải DUY NHẤT bộ truyện này về thư mục tạm
        download_ok = inspector.download_story_to_dir(item['story_info'], temp_story_dir)
        if not download_ok:
            print(f"❌ [{story_id}] Tải dữ liệu về thư mục tạm thất bại!")
            notifier.notify_story_failed(story_id, len(chaps), "Lỗi tải dữ liệu từ Google Drive về thư mục tạm")
            execution_results.append({
                'story_id': story_id,
                'chapters': len(chaps),
                'agy_status': 'DOWNLOAD FAILED ❌',
                'qc_status': 'SKIPPED',
                'sync_status': 'SKIPPED'
            })
            shutil.rmtree(temp_story_dir, ignore_errors=True)
            continue

        # 4.2. Chạy AGY CLI
        success = agy_runner.run_translation(temp_story_dir, chaps)
        if not success:
            notifier.notify_story_failed(story_id, len(chaps), "AGY CLI kết thúc thất bại hoặc timeout")
            execution_results.append({
                'story_id': story_id,
                'chapters': len(chaps),
                'agy_status': 'FAILED ❌',
                'qc_status': 'SKIPPED',
                'sync_status': 'SKIPPED'
            })
            shutil.rmtree(temp_story_dir, ignore_errors=True)
            continue

        # 4.3. Hậu kiểm chất lượng QC
        print(f"\n🕵️ [{story_id}] Đang thực hiện hậu kiểm QC (Chữ Hán, thẻ HTML, tỷ lệ cắt gọt)...")
        chapters_dir = temp_story_dir / "chapters"
        qc_passed, qc_details = qc_validator.validate_directory_chapters(str(chapters_dir), chaps)

        failed_chaps = [d for d in qc_details if not d['passed']]
        if not qc_passed:
            print(f"❌ [{story_id}] Phát hiện {len(failed_chaps)} chương KHÔNG ĐẠT chuẩn QC:")
            for fc in failed_chaps:
                print(f"   - Chương {fc['chapter']}: {fc['reason']}")
            isolate_failed_story(temp_story_dir, story_id)
            notifier.notify_story_failed(
                story_id,
                len(chaps),
                f"Không đạt kiểm định QC ({len(failed_chaps)} chương lỗi)",
                isolated_path=f"storage/temp_failed/{story_id}",
                failed_details=failed_chaps
            )
            execution_results.append({
                'story_id': story_id,
                'chapters': len(chaps),
                'agy_status': 'SUCCESS ✅',
                'qc_status': f'FAILED ({len(failed_chaps)} chaps) ❌',
                'sync_status': 'BLOCKED 🛑'
            })
            continue

        print(f"✅ [{story_id}] Toàn bộ {len(chaps)} chương ĐẠT 100% chuẩn QC!")

        # 4.4. Đồng bộ ngược lên Google Drive (Nếu không bật cờ --no-upload)
        story_duration_str = str(datetime.now() - story_start).split('.')[0]

        if args.no_upload:
            print(f"\n⚠️ [{story_id}] CỜ --no-upload ĐANG BẬT: Bỏ qua bước đóng gói và upload Google Drive theo yêu cầu thử nghiệm.")
            sync_status_str = "SKIPPED (--no-upload)"
            notifier.notify_story_success(story_id, len(chaps), f"{chaps[0]} -> {chaps[-1]}", story_duration_str, uploaded=False)
        else:
            sync_success = syncer.sync_story(item['story_info'], temp_story_dir, chaps)
            sync_status_str = "SUCCESS ✅" if sync_success else "FAILED ❌"
            if sync_success:
                notifier.notify_story_success(story_id, len(chaps), f"{chaps[0]} -> {chaps[-1]}", story_duration_str, uploaded=True)

        execution_results.append({
            'story_id': story_id,
            'chapters': len(chaps),
            'agy_status': 'SUCCESS ✅',
            'qc_status': 'PASSED ✅',
            'sync_status': sync_status_str
        })

        # 4.5. Tự động dọn dẹp sạch thư mục tạm sau khi đồng bộ
        print(f"🧹 [{story_id}] Đang giải phóng bộ nhớ đĩa (xóa thư mục tạm {temp_story_dir})...")
        shutil.rmtree(temp_story_dir, ignore_errors=True)
        print(f"✨ [{story_id}] Đã giải phóng hoàn toàn dung lượng ổ cứng!")

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

"""
Chương trình chính (Entrypoint) của New Story Translator Daemon.
Tiến trình độc lập chuyên quét, lập hàng đợi 10 truyện mới và chạy song song AGY CLI để dịch 100 chương đầu.
"""
import sys
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
from new_story_translator_daemon.config import (
    TARGET_CHAPTERS_PER_STORY,
    TARGET_STORY_QUEUE_SIZE,
    MAX_PARALLEL_WORKERS,
    TIMEOUT_HOURS,
    TEMP_NEW_DIR
)
from new_story_translator_daemon.whitelist_manager import WhitelistManager
from new_story_translator_daemon.drive_new_scanner import DriveNewScanner
from new_story_translator_daemon.remote_zip_inspector import RemoteZipInspector
from new_story_translator_daemon.parallel_queue_manager import ParallelQueueManager
from new_story_translator_daemon.agy_runner import AGYRunner
from new_story_translator_daemon.qc_validator import QCValidator
from new_story_translator_daemon.drive_syncer import DriveSyncer
from new_story_translator_daemon.telegram_notifier import TelegramNotifier
from new_story_translator_daemon.worker import process_single_new_story

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
    parser = argparse.ArgumentParser(description="New Story Translator Daemon - Quét và dịch mới 100 chương đầu cho truyện mới song song.")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ quét và lập danh sách hàng đợi qua RAM, không tải file, không dịch và không upload Drive.")
    parser.add_argument("--workers", type=int, default=MAX_PARALLEL_WORKERS, help=f"Số lượng truyện dịch song song cùng lúc (Mặc định: {MAX_PARALLEL_WORKERS}).")
    parser.add_argument("--limit-stories", type=int, default=TARGET_STORY_QUEUE_SIZE, help=f"Số lượng truyện trong hàng đợi (Mặc định: {TARGET_STORY_QUEUE_SIZE}).")
    parser.add_argument("--chapters", type=int, default=TARGET_CHAPTERS_PER_STORY, help=f"Số chương dịch cho mỗi truyện mới (Mặc định: {TARGET_CHAPTERS_PER_STORY}).")
    parser.add_argument("--sort-by", type=str, choices=["recent", "oldest"], default="recent", help="Tiêu chí sắp xếp: recent (mới nhất) hoặc oldest (cũ nhất). Mặc định: recent.")
    parser.add_argument("--source", type=str, choices=["ixdzs8", "biquge", "truyendichwiki", "novel543"], default=None, help="Chỉ định quét riêng 1 nguồn cụ thể.")
    parser.add_argument("--story-id", type=str, default=None, help='Chỉ định 1 hoặc nhiều story_id (phân cách bằng dấu phẩy: "id_A, id_B").')
    parser.add_argument("--exclude-story-id", type=str, default=None, help='Chỉ định loại trừ 1 hoặc nhiều story_id (phân cách bằng dấu phẩy: "id_A, id_B").')
    parser.add_argument("--no-upload", action="store_true", help="Bỏ qua bước upload lên Google Drive (dùng cho chạy thử nghiệm an toàn).")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_HOURS, help=f"Timeout tối đa cho mỗi mẻ AGY CLI tính theo giờ (Mặc định: {TIMEOUT_HOURS}h).")
    return parser.parse_args()

def main():
    args = parse_args()
    start_time = datetime.now()

    target_story_ids = parse_story_ids(args.story_id)
    excluded_story_ids = set(parse_story_ids(args.exclude_story_id))
    if excluded_story_ids and target_story_ids:
        target_story_ids = [sid for sid in target_story_ids if sid not in excluded_story_ids]

    print("=" * 75)
    print(f"🆕 NEW STORY TRANSLATOR DAEMON KHỞI ĐỘNG: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️ Cấu hình: Hàng đợi = {args.limit_stories} truyện | Mỗi truyện = {args.chapters} chaps | Song song = {args.workers} workers | Dry-run = {args.dry_run}")
    if target_story_ids:
        print(f"🎯 Chỉ định {len(target_story_ids)} story_id: {', '.join(target_story_ids)}")
    if excluded_story_ids:
        print(f"🚫 Loại trừ {len(excluded_story_ids)} story_id: {', '.join(excluded_story_ids)}")
    print("=" * 75)

    # 1. Khởi tạo các dịch vụ
    try:
        notifier = TelegramNotifier()
        gdrive_service = GoogleDriveService()
        whitelist_mgr = WhitelistManager()
        scanner = DriveNewScanner(gdrive_service, whitelist_mgr=whitelist_mgr)

        # Lấy token xác thực từ gdrive_service để dùng cho RemoteZipInspector
        creds = gdrive_service.service._http.credentials
        if not creds.valid:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        remote_inspector = RemoteZipInspector(auth_token=creds.token)

        queue_mgr = ParallelQueueManager(
            queue_size=args.limit_stories,
            target_chapters=args.chapters
        )
    except Exception as e:
        print(f"❌ Khởi tạo dịch vụ thất bại: {e}")
        sys.exit(1)

    # 2. Quét các truyện mới từ Google Drive
    candidate_sources = scanner.scan_all_new_stories(
        sort_by=args.sort_by,
        target_source=args.source
    )

    if excluded_story_ids:
        for src in candidate_sources:
            candidate_sources[src] = [s for s in candidate_sources[src] if s['story_id'] not in excluded_story_ids]

    if target_story_ids:
        print(f"\n🎯 Đang lọc theo danh sách {len(target_story_ids)} story_id chỉ định: {', '.join(target_story_ids)}")
        for src in candidate_sources:
            candidate_sources[src] = [s for s in candidate_sources[src] if s['story_id'] in target_story_ids]

    # 3. Lập hàng đợi 10 truyện mới (lấy 100 chương đầu)
    queue = queue_mgr.build_queue(candidate_sources, remote_inspector, sort_by=args.sort_by)

    if not queue:
        print("\n☕ Không tìm thấy truyện mới nào chưa dịch trên Google Drive (hoặc toàn bộ truyện mới chưa nằm trong Whitelist). Kết thúc.")
        return

    # In danh sách hàng đợi
    print("\n" + "=" * 75)
    print(f"📋 DANH SÁCH {len(queue)} TRUYỆN MỚI ĐƯỢC CHỌN VÀO HÀNG ĐỢI:")
    print("=" * 75)
    for idx, item in enumerate(queue, 1):
        chaps = item['chapters_to_translate']
        raw_total = item.get('raw_total')
        total_str = f" / {raw_total} chaps" if raw_total else ""
        sheet_meta = item.get('sheet_meta') or {}
        title = sheet_meta.get('title') or item['story_id']
        badge = item.get('badge') or sheet_meta.get('badge') or ""
        badge_str = f" {badge}" if badge else ""
        priority = item.get('priority') or sheet_meta.get('priority') or 99
        print(f"  {idx}. [{item['source']}]{badge_str} (P{priority}) {item['story_id']}: {len(chaps)} chương ({chaps[0]} -> {chaps[-1]}{total_str}) | {title}")
    print("=" * 75)

    if args.dry_run:
        print("\n🔍 Chế độ --dry-run đang bật. Đã hoàn tất kiểm tra mục lục qua RAM (0 byte ghi xuống ổ cứng).")
        return

    # Gửi thông báo Telegram bắt đầu phiên dịch mới
    notifier.notify_session_start(queue, args.workers, sort_by=args.sort_by, chapters_per_story=args.chapters)

    # 4. Thực thi dịch song song qua ThreadPoolExecutor
    execution_results = []
    TEMP_NEW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n⚡ Kích hoạt Worker Pool ({args.workers} workers song song) để xử lý {len(queue)} truyện mới...")

    # Khởi tạo các helper tái sử dụng
    agy_runner = AGYRunner(timeout_hours=args.timeout)
    qc_validator = QCValidator()
    syncer = DriveSyncer(gdrive_service)

    if args.workers <= 1:
        # Chạy tuần tự nếu workers = 1
        for item in queue:
            res = process_single_new_story(
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
                    process_single_new_story,
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

    # 5. Báo cáo tổng kết
    total_duration = str(datetime.now() - start_time).split('.')[0]
    notifier.notify_session_end(execution_results, total_duration)

    print("\n" + "=" * 75)
    print(f"🏁 BÁO CÁO TỔNG KẾT PHIÊN DỊCH MỚI (Thời gian: {total_duration}):")
    print("-" * 75)
    print(f"{'Bộ Truyện':<25} | {'Số Chương':<10} | {'AGY CLI':<12} | {'QC':<15} | {'Drive Sync':<12}")
    print("-" * 75)
    for r in execution_results:
        print(f"{r['story_id']:<25} | {r['chapters']:<10} | {r['agy_status']:<12} | {r['qc_status']:<15} | {r['sync_status']:<12}")
    print("=" * 75)

if __name__ == "__main__":
    main()

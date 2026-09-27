"""
Module Worker xử lý đơn vị 1 bộ truyện dịch tiếp (Auto Translator Daemon):
Quy trình trọn gói:
1. Tải chapters.zip, translated_chapters.zip và metadata từ Google Drive về thư mục tạm riêng (Thread-Safe qua HTTP stream).
2. Thực thi AGY CLI dịch các chương chỉ định.
3. Hậu kiểm chất lượng QC (chữ Hán, HTML, chống cắt gọt).
4. Đóng gói lại và đồng bộ translated_chapters.zip, glossary.json, checkpoints.json lên Drive.
5. Giải phóng thư mục tạm và thông báo Telegram.
"""
import json
import shutil
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from googleapiclient.http import MediaIoBaseDownload

from auto_translator_daemon.config import STORAGE_DIR, TEMP_FAILED_DIR, format_chapter_ranges
from auto_translator_daemon.agy_runner import AGYRunner
from auto_translator_daemon.pre_translate_validator import PreTranslateValidator
from auto_translator_daemon.qc_validator import QCValidator
from auto_translator_daemon.drive_syncer import DriveSyncer
from auto_translator_daemon.telegram_notifier import TelegramNotifier

TEMP_RESUME_DIR = STORAGE_DIR / "temp"

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

def get_drive_auth_token(gdrive_service) -> str:
    """Lấy hoặc làm mới OAuth Bearer token từ gdrive_service."""
    try:
        creds = gdrive_service.service._http.credentials
        if not creds.valid:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        return creds.token
    except Exception as e:
        print(f"⚠️ Lỗi lấy OAuth token: {e}")
        return ""

def download_file_from_drive(file_id: str, dest_path: Path, auth_token: str = "", service = None) -> bool:
    """
    Tải file từ Google Drive về đường dẫn cục bộ.
    Ưu tiên dùng urllib HTTP streaming với Bearer token (100% thread-safe, không bị xung đột socket SSL).
    Fallback sang MediaIoBaseDownload nếu không có token.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Phương thức Thread-Safe: HTTP GET Stream qua urllib
    if auth_token:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        req = urllib.request.Request(url, headers={'Authorization': f"Bearer {auth_token}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, 'wb') as f:
                while True:
                    chunk = resp.read(1024 * 1024 * 2) # 2MB chunk
                    if not chunk:
                        break
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"⚠️ Tải qua HTTP stream gặp lỗi ({e}), chuyển sang fallback MediaIoBaseDownload...")

    # 2. Fallback qua Google API Client
    if service:
        try:
            request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
            with open(dest_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request, chunksize=1024 * 1024 * 5)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            return True
        except Exception as e:
            print(f"❌ Lỗi tải file {file_id} về {dest_path}: {e}")
            return False

    return False

def download_resume_story_to_dir(story_info: Dict[str, Any], local_dir: Path, auth_token: str, service = None) -> bool:
    """Tải toàn bộ file cần thiết của truyện dịch dở về thư mục tạm."""
    local_dir.mkdir(parents=True, exist_ok=True)
    story_id = story_info['story_id']

    print(f"📥 [{story_id}] Đang tải dữ liệu bộ truyện về thư mục tạm...")

    # 1. Tải chapters.zip
    czip_id = story_info['chapters_file']['id']
    if not download_file_from_drive(czip_id, local_dir / "chapters.zip", auth_token=auth_token, service=service):
        return False

    # 2. Tải translated_chapters.zip
    tzip_file = story_info.get('translated_chapters_file')
    if tzip_file and 'id' in tzip_file:
        if not download_file_from_drive(tzip_file['id'], local_dir / "translated_chapters.zip", auth_token=auth_token, service=service):
            return False

    # 3. Tải các file metadata nếu có
    files_meta = story_info.get('files_meta', {})
    for meta_name in ['info.json', 'glossary.json', 'summary.txt', 'checkpoints.json']:
        if meta_name in files_meta:
            download_file_from_drive(files_meta[meta_name]['id'], local_dir / meta_name, auth_token=auth_token, service=service)

    # 4. Khởi tạo file rỗng nếu chưa có sẵn
    glossary_file = local_dir / "glossary.json"
    if not glossary_file.exists():
        glossary_file.write_text("{}", encoding='utf-8')

    summary_file = local_dir / "summary.txt"
    if not summary_file.exists():
        summary_file.write_text("", encoding='utf-8')

    return True

def process_single_resume_story(
    item: Dict[str, Any],
    gdrive_service,
    agy_runner: AGYRunner,
    qc_validator: QCValidator,
    syncer: DriveSyncer,
    notifier: TelegramNotifier,
    no_upload: bool = False
) -> Dict[str, Any]:
    """
    Xử lý trọn gói 1 bộ truyện dịch tiếp (an toàn chạy trong luồng song song).
    """
    story_id = item['story_id']
    chaps = item['chapters_to_translate']
    temp_story_dir = TEMP_RESUME_DIR / story_id
    story_start = datetime.now()

    folder_id = (item.get('story_info') or {}).get('story_folder_id')
    sheet_meta = item.get('sheet_meta') or {}
    web_meta = item.get('web_meta') or {}
    story_title = sheet_meta.get('title') or web_meta.get('name') or web_meta.get('title')

    tag_vip = " [⭐ ƯU TIÊN WEB]" if item.get('is_web_priority') else ""
    chaps_str = format_chapter_ranges(chaps)
    print("\n" + "=" * 60)
    title_display = f" - {story_title}" if story_title else ""
    print(f"▶️ BẮT ĐẦU DỊCH: [{item['source']}]{tag_vip} {story_id}{title_display} ({len(chaps)} chương: {chaps_str})")
    print("=" * 60)

    # 1. Tải dữ liệu về thư mục tạm với Bearer token thread-safe
    auth_token = get_drive_auth_token(gdrive_service)
    download_ok = download_resume_story_to_dir(
        story_info=item['story_info'],
        local_dir=temp_story_dir,
        auth_token=auth_token,
        service=gdrive_service.service
    )

    if not download_ok:
        print(f"❌ [{story_id}] Tải dữ liệu về thư mục tạm thất bại!")
        notifier.notify_story_failed(
            story_id, len(chaps), "Lỗi tải dữ liệu từ Google Drive về thư mục tạm",
            source=source, title=story_title, folder_id=folder_id
        )
        shutil.rmtree(temp_story_dir, ignore_errors=True)
        return {
            'story_id': story_id,
            'chapters': len(chaps),
            'agy_status': 'DOWNLOAD FAILED ❌',
            'qc_status': 'SKIPPED',
            'sync_status': 'SKIPPED',
            'duration': '0s'
        }

    chaps_range_label = format_chapter_ranges(chaps, arrow="➔")

    # 1.5. Thẩm định ngữ nghĩa dữ liệu truyện bằng AGY CLI trước khi cấp phép dịch (Pre-Translate Sanity Check)
    print(f"\n🕵️ [{story_id}] Đang chuẩn bị workspace và thẩm định dữ liệu raw (Pre-Translate Sanity Check)...")
    ws_story_name = agy_runner.prepare_local_workspace(temp_story_dir)
    if ws_story_name and ws_story_name != story_id:
        story_title = ws_story_name

    pre_checker = PreTranslateValidator(timeout_minutes=5)
    pre_ok, check_data = pre_checker.validate_story(temp_story_dir, chaps, item['story_info'])

    allowed_to_translate = check_data.get('allowed_to_translate', False)
    is_complete_story = check_data.get('is_complete', False)
    report_brief = check_data.get('report_brief', 'Không có báo cáo chi tiết.')

    # Gửi thông báo Telegram ngay lập tức cho Admin / Đội Crawler
    notifier.notify_pre_check_result(
        story_id=story_id,
        chapters_count=len(chaps),
        chaps_range=chaps_range_label,
        allowed=allowed_to_translate,
        is_complete=is_complete_story,
        report_brief=report_brief,
        isolated_path=f"storage/temp_failed/{story_id}" if not allowed_to_translate else None,
        source=source,
        title=story_title,
        folder_id=folder_id
    )

    if not allowed_to_translate:
        print(f"❌ [{story_id}] THẨM ĐỊNH KHÔNG ĐẠT: Từ chối dịch mẻ này!")
        print(f"   📝 Báo cáo lỗi: {report_brief}")
        isolate_failed_story(temp_story_dir, story_id)
        return {
            'story_id': story_id,
            'chapters': len(chaps),
            'agy_status': 'REJECTED (Pre-check) ❌',
            'qc_status': 'SKIPPED',
            'sync_status': 'BLOCKED 🛑',
            'duration': str(datetime.now() - story_start).split('.')[0]
        }

    print(f"✅ [{story_id}] THẨM ĐỊNH THÀNH CÔNG: Được phép tiến hành dịch!")
    print(f"   📝 Đánh giá: {report_brief}")
    if is_complete_story:
        print(f"   🏆 DẤU HIỆU ĐẠI KẾT CỤC: Bộ truyện đã đi đến hồi kết toàn văn!")

    # 2. Chạy AGY CLI
    success = agy_runner.run_translation(temp_story_dir, chaps)
    if not success:
        notifier.notify_story_failed(
            story_id, len(chaps), "AGY CLI kết thúc thất bại hoặc timeout",
            source=source, title=story_title, folder_id=folder_id
        )
        shutil.rmtree(temp_story_dir, ignore_errors=True)
        return {
            'story_id': story_id,
            'chapters': len(chaps),
            'agy_status': 'FAILED ❌',
            'qc_status': 'SKIPPED',
            'sync_status': 'SKIPPED',
            'duration': str(datetime.now() - story_start).split('.')[0]
        }

    # 3. Hậu kiểm chất lượng QC
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
            failed_details=failed_chaps,
            source=source,
            title=story_title,
            folder_id=folder_id
        )
        return {
            'story_id': story_id,
            'chapters': len(chaps),
            'agy_status': 'SUCCESS ✅',
            'qc_status': f'FAILED ({len(failed_chaps)} chaps) ❌',
            'sync_status': 'BLOCKED 🛑',
            'duration': str(datetime.now() - story_start).split('.')[0]
        }

    print(f"✅ [{story_id}] Toàn bộ {len(chaps)} chương ĐẠT 100% chuẩn QC!")

    # Ghi nhận trạng thái Đại kết cục vào checkpoints.json nếu có (tuyệt đối không đụng vào info.json)
    if is_complete_story:
        cp_file = temp_story_dir / "checkpoints.json"
        try:
            cp_data = {}
            if cp_file.exists():
                cp_data = json.loads(cp_file.read_text(encoding='utf-8', errors='ignore'))
            cp_data["is_complete"] = True
            cp_data["completed_at"] = datetime.now().isoformat()
            cp_file.write_text(json.dumps(cp_data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"🏆 [{story_id}] Đã ghi nhận cờ is_complete: true vào checkpoints.json!")
        except Exception as e:
            print(f"⚠️ [{story_id}] Lỗi cập nhật checkpoints.json: {e}")

    # 4. Đồng bộ ngược lên Google Drive
    story_duration_str = str(datetime.now() - story_start).split('.')[0]
    raw_total = (item.get('inspected_meta') or {}).get('raw_chapters_count')

    if no_upload:
        print(f"\n⚠️ [{story_id}] CỜ --no-upload ĐANG BẬT: Bỏ qua bước đóng gói và upload Google Drive theo yêu cầu thử nghiệm.")
        sync_status_str = "SKIPPED (--no-upload)"
        notifier.notify_story_success(
            story_id, len(chaps), chaps_range_label, story_duration_str,
            uploaded=False, total_raw=raw_total, is_complete=is_complete_story,
            source=source, title=story_title, folder_id=folder_id
        )
    else:
        sync_success = syncer.sync_story(item['story_info'], temp_story_dir, chaps)
        sync_status_str = "SUCCESS ✅" if sync_success else "FAILED ❌"
        if sync_success:
            notifier.notify_story_success(
                story_id, len(chaps), chaps_range_label, story_duration_str,
                uploaded=True, total_raw=raw_total, is_complete=is_complete_story,
                source=source, title=story_title, folder_id=folder_id
            )

    # 5. Tự động dọn dẹp sạch thư mục tạm giải phóng dung lượng đĩa
    print(f"🧹 [{story_id}] Đang giải phóng bộ nhớ đĩa ({temp_story_dir})...")
    shutil.rmtree(temp_story_dir, ignore_errors=True)
    print(f"✨ [{story_id}] Đã giải phóng hoàn toàn dung lượng ổ cứng!")

    return {
        'story_id': story_id,
        'chapters': len(chaps),
        'agy_status': 'SUCCESS ✅',
        'qc_status': 'PASSED ✅',
        'sync_status': sync_status_str,
        'duration': story_duration_str
    }

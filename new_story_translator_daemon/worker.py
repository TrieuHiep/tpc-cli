"""
Module Worker xử lý đơn vị 1 bộ truyện mới:
Quy trình trọn gói:
1. Tải chapters.zip & info.json từ Google Drive về thư mục tạm riêng (Thread-Safe qua HTTP stream).
2. Thực thi AGY CLI dịch các chương chỉ định.
3. Hậu kiểm chất lượng QC (chữ Hán, HTML, chống cắt gọt).
4. Tạo mới và đồng bộ translated_chapters.zip, glossary.json, checkpoints.json lên Drive.
5. Giải phóng thư mục tạm và thông báo Telegram.
"""
import shutil
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from googleapiclient.http import MediaIoBaseDownload

from new_story_translator_daemon.config import TEMP_NEW_DIR, TEMP_FAILED_DIR
from new_story_translator_daemon.agy_runner import AGYRunner
from new_story_translator_daemon.qc_validator import QCValidator
from new_story_translator_daemon.drive_syncer import DriveSyncer
from new_story_translator_daemon.telegram_notifier import TelegramNotifier

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

def download_new_story_to_dir(story_info: Dict[str, Any], local_dir: Path, auth_token: str, service = None) -> bool:
    """Tải dữ liệu của truyện mới về thư mục tạm."""
    local_dir.mkdir(parents=True, exist_ok=True)
    story_id = story_info['story_id']

    print(f"📥 [{story_id}] Đang tải chapters.zip về {local_dir}...")
    czip_id = story_info['chapters_file']['id']
    if not download_file_from_drive(czip_id, local_dir / "chapters.zip", auth_token=auth_token, service=service):
        return False

    # Tải info.json nếu có
    files_meta = story_info.get('files_meta', {})
    if 'info.json' in files_meta:
        download_file_from_drive(files_meta['info.json']['id'], local_dir / "info.json", auth_token=auth_token, service=service)

    return True

def process_single_new_story(
    item: Dict[str, Any],
    gdrive_service,
    agy_runner: AGYRunner,
    qc_validator: QCValidator,
    syncer: DriveSyncer,
    notifier: TelegramNotifier,
    no_upload: bool = False
) -> Dict[str, Any]:
    """
    Xử lý trọn gói 1 bộ truyện mới độc lập (an toàn chạy trong luồng song song).
    """
    story_id = item['story_id']
    chaps = item['chapters_to_translate']
    temp_story_dir = TEMP_NEW_DIR / story_id
    story_start = datetime.now()

    badge = item.get('badge') or (item.get('sheet_meta') or {}).get('badge') or ""
    badge_str = f" {badge}" if badge else ""
    title = (item.get('sheet_meta') or {}).get('title') or story_id
    print("\n" + "=" * 60)
    print(f"▶️ BẮT ĐẦU DỊCH MỚI: [{item['source']}]{badge_str} {story_id} - {title} ({len(chaps)} chương)")
    print("=" * 60)

    # 1. Tải chapters.zip về thư mục tạm với thread-safe token
    auth_token = get_drive_auth_token(gdrive_service)
    download_ok = download_new_story_to_dir(
        story_info=item['story_info'],
        local_dir=temp_story_dir,
        auth_token=auth_token,
        service=gdrive_service.service
    )

    if not download_ok:
        print(f"❌ [{story_id}] Tải dữ liệu về thư mục tạm thất bại!")
        notifier.notify_story_failed(story_id, len(chaps), "Lỗi tải chapters.zip từ Google Drive")
        shutil.rmtree(temp_story_dir, ignore_errors=True)
        return {
            'story_id': story_id,
            'chapters': len(chaps),
            'agy_status': 'DOWNLOAD FAILED ❌',
            'qc_status': 'SKIPPED',
            'sync_status': 'SKIPPED',
            'duration': '0s'
        }

    # 2. Chạy AGY CLI
    success = agy_runner.run_translation(temp_story_dir, chaps)
    if not success:
        notifier.notify_story_failed(story_id, len(chaps), "AGY CLI kết thúc thất bại hoặc timeout")
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
        for fc in failed_chaps[:5]:
            print(f"   - Chương {fc['chapter']}: {fc['reason']}")
        isolate_failed_story(temp_story_dir, story_id)
        notifier.notify_story_failed(
            story_id,
            len(chaps),
            f"Không đạt kiểm định QC ({len(failed_chaps)} chương lỗi)",
            isolated_path=f"storage/temp_failed/{story_id}"
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

    # 4. Tạo mới và upload lên Google Drive
    story_duration_str = str(datetime.now() - story_start).split('.')[0]

    if no_upload:
        print(f"\n⚠️ [{story_id}] CỜ --no-upload ĐANG BẬT: Bỏ qua upload Drive theo yêu cầu thử nghiệm.")
        sync_status_str = "SKIPPED (--no-upload)"
        notifier.notify_story_success(story_id, len(chaps), f"{chaps[0]} -> {chaps[-1]}", story_duration_str, uploaded=False)
    else:
        sync_success = syncer.sync_story(item['story_info'], temp_story_dir, chaps)
        sync_status_str = "SUCCESS ✅" if sync_success else "FAILED ❌"
        if sync_success:
            notifier.notify_story_success(story_id, len(chaps), f"{chaps[0]} -> {chaps[-1]}", story_duration_str, uploaded=True)

    # 5. Dọn dẹp thư mục tạm giải phóng ổ cứng
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

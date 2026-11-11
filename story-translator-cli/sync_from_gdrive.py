import os
import sys
import io
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from googleapiclient.http import MediaIoBaseDownload
from app.services.gdrive import GoogleDriveService, RAW_DRIVE_FOLDERS, VAULT_DRIVE_FOLDERS, DRIVE_FOLDERS
from app.utils.logger import logger, console
from rich.table import Table

def download_file_from_drive(service, file_id: str, local_path: Path):
    """Downloads a file from Google Drive to local_path."""
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(local_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

import argparse
from typing import Optional

def sync_gdrive_to_local(storage_dir: Path, repo_type: Optional[str] = None, story_id: Optional[str] = None, raw_only: bool = False):
    """Scans Google Drive root folders (RAW + VAULT tpc-dw) and syncs story datasets down to local storage_dir."""
    storage_dir = storage_dir.resolve()
    target_info = f" [Mã truyện: {story_id}]" if story_id else ""
    raw_info = " [Chế độ: CHỈ KÉO FILE THÔ info.json & chapters.zip]" if raw_only else ""
    logger.info(f"🚀 Bắt đầu đồng bộ dữ liệu từ Google Drive{target_info}{raw_info} về: [bold cyan]{storage_dir}[/bold cyan]...")

    ALLOWED_RAW_FILES = {"info.json", "chapters.zip"}
    ALLOWED_VAULT_FILES = {"translated_chapters.zip", "glossary.json", "summary.txt", "checkpoints.json"}

    try:
        gdrive_service = GoogleDriveService()
        service = gdrive_service.service
    except Exception as e:
        logger.error(f"❌ Không thể khởi tạo Google Drive Service: {e}")
        return

    synced_stories = 0
    updated_files_count = 0

    if repo_type and repo_type.lower() in RAW_DRIVE_FOLDERS:
        target_folders = {repo_type.lower(): RAW_DRIVE_FOLDERS[repo_type.lower()]}
    else:
        target_folders = RAW_DRIVE_FOLDERS

    for repo_key, root_folder_id in target_folders.items():
        vault_root_id = VAULT_DRIVE_FOLDERS.get(repo_key)
        repo_local_dir = storage_dir / repo_key
        repo_local_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🔍 Quét thư mục kho Raw trên Drive: [bold gold1]{repo_key}[/bold gold1] (ID: {root_folder_id})...")

        if story_id:
            safe_sid = story_id.strip().replace("'", "\\'")
            query = f"'{root_folder_id}' in parents and name = '{safe_sid}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        else:
            query = f"'{root_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"

        drive_stories = []
        page_token = None
        while True:
            response = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            drive_stories.extend(response.get('files', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break

        # Lập bảng băm thư mục bên Kho Dịch tpc-dw nếu cần kéo cả bản dịch/metadata
        vault_folder_map = {}
        if not raw_only and vault_root_id:
            if story_id:
                safe_sid = story_id.strip().replace("'", "\\'")
                v_query = f"'{vault_root_id}' in parents and name = '{safe_sid}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            else:
                v_query = f"'{vault_root_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            v_token = None
            while True:
                v_res = service.files().list(
                    q=v_query,
                    fields="nextPageToken, files(id, name)",
                    pageToken=v_token,
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                for vf in v_res.get('files', []):
                    vault_folder_map[(vf.get('name') or '').strip()] = vf['id']
                v_token = v_res.get('nextPageToken')
                if not v_token:
                    break

        logger.info(f"📊 Tìm thấy {len(drive_stories)} bộ truyện phù hợp trên Drive kho [cyan]{repo_key}[/cyan].")

        for story in drive_stories:
            s_name = (story['name'] or '').strip()
            story_folder_id = story['id']
            local_story_dir = repo_local_dir / s_name

            file_query = f"'{story_folder_id}' in parents and trashed = false"
            file_res = service.files().list(
                q=file_query,
                fields="files(id, name, modifiedTime, size)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            candidate_files = [
                df for df in file_res.get('files', [])
                if df['name'].lower() in ALLOWED_RAW_FILES
            ]

            if not raw_only and s_name in vault_folder_map:
                v_fid = vault_folder_map[s_name]
                v_fres = service.files().list(
                    q=f"'{v_fid}' in parents and trashed = false",
                    fields="files(id, name, modifiedTime, size)",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                for vdf in v_fres.get('files', []):
                    if vdf['name'].lower() in ALLOWED_VAULT_FILES:
                        candidate_files.append(vdf)

            story_updated = False

            for df in candidate_files:
                file_name = df['name']
                file_id = df['id']

                drive_mod_time = df.get('modifiedTime')
                local_file_path = local_story_dir / file_name

                should_download = False
                if not local_file_path.exists():
                    should_download = True
                elif drive_mod_time:
                    drive_mtime = datetime.fromisoformat(drive_mod_time.replace('Z', '+00:00')).timestamp()
                    local_mtime = local_file_path.stat().st_mtime
                    if drive_mtime > local_mtime + 5:
                        should_download = True

                if should_download:
                    logger.info(f"⬇️ Tải/Cập nhật file [cyan]{s_name}/{file_name}[/cyan] từ Drive...")
                    download_file_from_drive(service, file_id, local_file_path)
                    updated_files_count += 1
                    story_updated = True

            if story_updated:
                synced_stories += 1

    logger.info(f"\n🎉 [HOÀN THÀNH ĐỒNG BỘ] Đã đồng bộ {synced_stories} bộ truyện ({updated_files_count} file mới/cập nhật) từ Google Drive về local!")

def main():
    parser = argparse.ArgumentParser(description="Story Translator CLI - Google Drive Sync Engine")
    parser.add_argument("--type", type=str, choices=list(DRIVE_FOLDERS.keys()), help="Tùy chọn: Chọn nhóm kho Drive cần đồng bộ")
    parser.add_argument("--story-id", type=str, help="Tùy chọn: Chỉ đồng bộ DUY NHẤT 1 Mã truyện chỉ định (Ví dụ: W_Ap1lS4CEbyOJSq hoặc 0110518544)")
    parser.add_argument("--raw-only", action="store_true", help="Chỉ tải dữ liệu thô gốc (info.json và chapters.zip), KHÔNG tải ảnh bìa hay translated_chapters.zip")

    args = parser.parse_args()

    root_dir = (Path(__file__).resolve().parent.parent / "storage").resolve()
    root_dir.mkdir(parents=True, exist_ok=True)
    sync_gdrive_to_local(root_dir, repo_type=args.type, story_id=args.story_id, raw_only=args.raw_only)

if __name__ == "__main__":
    main()

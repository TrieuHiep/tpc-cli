import os
import sys
import mimetypes
from pathlib import Path
from typing import Dict, Tuple, Optional, List

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.utils.logger import logger

SCOPES = ['https://www.googleapis.com/auth/drive']

DRIVE_FOLDERS = {
    "ixdzs8": "1biCwkUl5IT1R0C-CrZsRpgQkFAX-vE3c",
    "truyendichwiki": "1c1W2OYlO8s06DVK3PkLPbi8hkdynGLrc",
    "novel543": "1sulNp0yvLx8G04Uod0KAYPemGSNOsEBP"
}

class GoogleDriveService:
    """Service handling Google Drive API interactions (Folder lookup & file upload/overwrite)."""

    def __init__(self):
        self.conf_dir = Path(__file__).parent.parent.parent / "conf"
        self.token_path = self.conf_dir / "token.json"
        self.client_secret_path = self.conf_dir / "client_secret.json"
        self.service_account_path = self.conf_dir / "gdrive-key.json"

        self.service = self._init_drive_service()

    def _init_drive_service(self):
        """Initializes Google Drive API service client with fallback mechanism."""
        creds = None

        # 1. Ưu tiên nạp token.json (User OAuth đã ủy quyền trước đó)
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(self.token_path, 'w', encoding='utf-8') as f:
                        f.write(creds.to_json())
            except Exception as e:
                logger.warning(f"Không thể refresh OAuth token: {e}")
                creds = None

        # 2. Nếu chưa có token, thử luồng OAuth Client Secret
        if not creds or not creds.valid:
            if self.client_secret_path.exists():
                try:
                    logger.info("🔑 Khởi tạo luồng xác thực OAuth User...")
                    flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), SCOPES)
                    creds = flow.run_local_server(port=0, open_browser=True)
                    with open(self.token_path, 'w', encoding='utf-8') as f:
                        f.write(creds.to_json())
                except Exception as e:
                    logger.warning(f"Luồng OAuth thất bại: {e}")

        # 3. Fallback dùng Service Account key
        if not creds or not creds.valid:
            if self.service_account_path.exists():
                logger.info("🔑 Khởi tạo kết nối bằng Service Account key...")
                creds = service_account.Credentials.from_service_account_file(str(self.service_account_path), scopes=SCOPES)
            else:
                raise FileNotFoundError("Không tìm thấy thông tin xác thực Google Drive nào trong thư mục conf/!")

        return build('drive', 'v3', credentials=creds)

    def detect_repo_info(self, dataset_dir: Path) -> Tuple[str, str, str]:
        """Detects repo key, story ID, and root Drive folder ID from local dataset path.
        
        Example dataset_dir: F:\\Workplace\\outside\\test-tmp\\storage\\truyendichwiki\\W_Ap1lS4CEbyOJSq
        Parent: truyendichwiki -> Root ID: 1c1W2OYlO8s06DVK3PkLPbi8hkdynGLrc
        Name: W_Ap1lS4CEbyOJSq -> Story ID: W_Ap1lS4CEbyOJSq
        """
        dataset_dir = dataset_dir.resolve()
        story_id = dataset_dir.name
        parent_name = dataset_dir.parent.name.lower()

        repo_key = "truyendichwiki"
        root_folder_id = DRIVE_FOLDERS["truyendichwiki"]

        for key, folder_id in DRIVE_FOLDERS.items():
            if key in parent_name:
                repo_key = key
                root_folder_id = folder_id
                break

        return repo_key, story_id, root_folder_id

    def get_or_create_story_folder(self, root_folder_id: str, story_id: str) -> str:
        """Finds or creates story_id folder inside root_folder_id on Google Drive."""
        query = f"'{root_folder_id}' in parents and name = '{story_id}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        response = self.service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        files = response.get('files', [])
        if files:
            folder_id = files[0]['id']
            logger.info(f"✅ Đã tìm thấy thư mục truyện [cyan]{story_id}[/cyan] trên Drive (ID: {folder_id})")
            return folder_id
        else:
            logger.info(f"📁 Thư mục [cyan]{story_id}[/cyan] chưa có trên Drive. Tiến hành tạo mới...")
            file_metadata = {
                'name': story_id,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [root_folder_id]
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
            folder_id = folder.get('id')
            logger.info(f"✅ Đã tạo thư mục truyện mới [cyan]{story_id}[/cyan] thành công (ID: {folder_id})")
            return folder_id

    @staticmethod
    def get_mimetype(file_path: Path) -> str:
        """Determines appropriate mimetype for file."""
        mime, _ = mimetypes.guess_type(str(file_path))
        if mime:
            return mime
        suffix = file_path.suffix.lower()
        if suffix == '.json':
            return 'application/json'
        elif suffix == '.txt':
            return 'text/plain; charset=utf-8'
        elif suffix == '.zip':
            return 'application/zip'
        return 'application/octet-stream'

    def upload_or_update_file(self, local_file_path: Path, story_folder_id: str, remote_file_name: str) -> Optional[str]:
        """Uploads new file or overwrites existing file in story_folder_id. Returns webViewLink."""
        if not local_file_path.exists():
            logger.error(f"File local không tồn tại: {local_file_path}")
            return None

        file_query = f"'{story_folder_id}' in parents and name = '{remote_file_name}' and trashed = false"
        file_res = self.service.files().list(
            q=file_query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        existing_files = file_res.get('files', [])
        mimetype = self.get_mimetype(local_file_path)
        media = MediaFileUpload(str(local_file_path), mimetype=mimetype, resumable=True)

        try:
            if existing_files:
                file_id = existing_files[0]['id']
                logger.info(f"🔄 File [cyan]{remote_file_name}[/cyan] đã tồn tại trên Drive. Đang tiến hành ghi đè (update)...")
                updated_file = self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                    fields='id, name, webViewLink',
                    supportsAllDrives=True
                ).execute()
                link = updated_file.get('webViewLink')
                logger.info(f"🎉 Ghi đè [green]{remote_file_name}[/green] lên Google Drive THÀNH CÔNG!")
                return link
            else:
                logger.info(f"⬆️ Đang tải [cyan]{remote_file_name}[/cyan] lên Google Drive...")
                file_metadata = {
                    'name': remote_file_name,
                    'parents': [story_folder_id]
                }
                uploaded_file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, webViewLink',
                    supportsAllDrives=True
                ).execute()
                link = uploaded_file.get('webViewLink')
                logger.info(f"🎉 Tải file [green]{remote_file_name}[/green] lên Google Drive THÀNH CÔNG!")
                return link
        except Exception as e:
            logger.error(f"❌ Lỗi khi upload/update file lên Google Drive: {e}", exc_info=True)
            return None
        finally:
            del media

    def upload_story_metadata(self, story_dir: Path, story_folder_id: str) -> Dict[str, Optional[str]]:
        """Uploads/updates core metadata files (summary.txt, glossary.json, checkpoints.json) if present."""
        story_dir = Path(story_dir).resolve()
        metadata_files = ["summary.txt", "glossary.json", "checkpoints.json"]
        uploaded = {}

        for filename in metadata_files:
            file_path = story_dir / filename
            if file_path.exists():
                link = self.upload_or_update_file(file_path, story_folder_id, filename)
                uploaded[filename] = link
            else:
                logger.debug(f"Không tìm thấy file {filename} để upload tại {story_dir.name}")

        return uploaded

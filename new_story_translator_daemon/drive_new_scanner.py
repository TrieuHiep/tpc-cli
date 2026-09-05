"""
Module quét và phát hiện các bộ truyện MỚI trên Google Drive:
Điều kiện chọn truyện mới:
1. Nằm trong Google Sheet Whitelist (được biên tập viên phê duyệt).
2. ĐÃ CÓ file raw chapters.zip trên Google Drive.
3. CHƯA CÓ file translated_chapters.zip (hoặc file rỗng <= 100 bytes).
"""
from typing import Dict, Any, List, Optional
from new_story_translator_daemon.config import DRIVE_FOLDERS, SOURCE_PRIORITY
from new_story_translator_daemon.whitelist_manager import WhitelistManager

class DriveNewScanner:
    """Quét và lọc các bộ truyện mới tinh từ Google Drive."""

    def __init__(self, gdrive_service, whitelist_mgr: Optional[WhitelistManager] = None):
        self.gdrive_service = gdrive_service
        self.service = self.gdrive_service.service
        self.whitelist_mgr = whitelist_mgr or WhitelistManager()

    def fetch_all_child_folders(self, root_folder_id: str) -> Dict[str, Dict[str, str]]:
        """Lấy tất cả folder con trong root_folder_id, trả về dict: {folder_id: {'id': ..., 'name': ...}}"""
        query = f"'{root_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        page_token = None
        folders = {}

        while True:
            response = self.service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                pageToken=page_token,
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            for f in response.get('files', []):
                folders[f['id']] = f

            page_token = response.get('nextPageToken', None)
            if not page_token:
                break

        return folders

    def fetch_all_relevant_files(self) -> Dict[str, Dict[str, Any]]:
        """
        Gom toàn bộ file chapters.zip, translated_chapters.zip, info.json
        bằng 1 lần truy vấn batch siêu tốc.
        Trả về dict: {parent_folder_id: {filename: file_obj}}
        """
        query = (
            "(name = 'chapters.zip' or name = 'translated_chapters.zip' or "
            "name = 'info.json' or name = 'glossary.json' or "
            "name = 'summary.txt') and trashed = false"
        )
        page_token = None
        files_by_parent = {}

        while True:
            response = self.service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, modifiedTime, size, parents)',
                pageToken=page_token,
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            for f in response.get('files', []):
                parents = f.get('parents', [])
                if parents:
                    pid = parents[0]
                    if pid not in files_by_parent:
                        files_by_parent[pid] = {}
                    files_by_parent[pid][f['name']] = f

            page_token = response.get('nextPageToken', None)
            if not page_token:
                break

        return files_by_parent

    def scan_all_new_stories(
        self,
        sort_by: str = "recent",
        target_source: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Quét và lọc các bộ truyện MỚI từ các nguồn trên Drive:
        - target_source: nếu chỉ định thì chỉ quét nguồn đó (ví dụ 'truyendichwiki' hoặc 'novel543').
        - sort_by: 'recent' (mới cập nhật nhất) hoặc 'oldest' (tồn đọng lâu nhất).
        """
        sources_to_scan = [target_source] if target_source else SOURCE_PRIORITY
        results = {}

        print("\n🔍 Đang gom danh sách toàn bộ file từ Google Drive...")
        all_files_by_parent = self.fetch_all_relevant_files()
        print(f"📦 Đã thu thập dữ liệu của {len(all_files_by_parent)} thư mục truyện.")

        for source in sources_to_scan:
            root_id = DRIVE_FOLDERS.get(source)
            if not root_id:
                continue

            print(f"\n📁 Đang quét danh mục thư mục nguồn [{source}] (Folder ID: {root_id})...")
            folders = self.fetch_all_child_folders(root_id)
            print(f"   Tìm thấy tổng cộng {len(folders)} thư mục con trên Drive.")

            eligible_new_stories = []

            for folder_id, folder_obj in folders.items():
                story_id = folder_obj['name']

                # Điều kiện 1: BẮT BUỘC nằm trong Whitelist (Google Sheet)
                if not self.whitelist_mgr.is_whitelisted(source, story_id):
                    continue
                meta_from_sheet = self.whitelist_mgr.get_story_info(source, story_id)

                story_files = all_files_by_parent.get(folder_id, {})

                # Điều kiện 2: BẮT BUỘC phải có chapters.zip (raw tiếng Trung)
                if 'chapters.zip' not in story_files:
                    continue

                # Điều kiện 3: BẮT BUỘC CHƯA CÓ translated_chapters.zip (hoặc file rỗng <= 100 bytes)
                tzip = story_files.get('translated_chapters.zip')
                if tzip:
                    tzip_size = int(tzip.get('size', 0))
                    if tzip_size > 100:
                        # Đã có bản dịch -> Bỏ qua, nhường cho daemon dịch tiếp
                        continue

                chapters_file = story_files['chapters.zip']
                chap_mod = chapters_file.get('modifiedTime')

                eligible_new_stories.append({
                    'source': source,
                    'story_id': story_id,
                    'story_folder_id': folder_id,
                    'chapters_file': chapters_file,
                    'translated_chapters_file': tzip,
                    'modified_time': chap_mod,
                    'files_meta': story_files,
                    'sheet_meta': meta_from_sheet
                })

            # Sắp xếp theo sort_by
            if sort_by == "oldest":
                eligible_new_stories.sort(key=lambda x: x['modified_time'] or '', reverse=False)
            else:
                eligible_new_stories.sort(key=lambda x: x['modified_time'] or '', reverse=True)

            print(f"✨ Nguồn [{source}]: Tìm thấy {len(eligible_new_stories)} bộ truyện MỚI CHƯA DỊCH (xếp theo: {sort_by}).")
            results[source] = eligible_new_stories

        return results

"""
Module quét thư mục Google Drive để phát hiện các truyện đang dịch dở có cập nhật mới.
Được tối ưu hóa bằng Batch Query (truy vấn gom cụm) với tốc độ siêu nhanh (~2 giây).
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime

# Đảm bảo import được story-translator-cli
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "story-translator-cli"))

from app.services.gdrive import GoogleDriveService
from auto_translator_daemon.config import DRIVE_FOLDERS, SOURCE_PRIORITY
from auto_translator_daemon.whitelist_manager import WhitelistManager
from auto_translator_daemon.web_priority_manager import WebPriorityManager

class DriveScanner:
    """Quét và lọc danh sách truyện đủ điều kiện từ Google Drive bằng Batch Query siêu tốc."""

    def __init__(
        self,
        gdrive_service: Optional[GoogleDriveService] = None,
        whitelist_mgr: Optional[WhitelistManager] = None,
        web_priority_mgr: Optional[WebPriorityManager] = None
    ):
        self.gdrive_service = gdrive_service or GoogleDriveService()
        self.service = self.gdrive_service.service
        self.whitelist_mgr = whitelist_mgr
        self.web_priority_mgr = web_priority_mgr

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
        Gom toàn bộ file chapters.zip, translated_chapters.zip, info.json, glossary.json, summary.txt, checkpoints.json
        bằng 1 lần truy vấn batch siêu tốc.
        Trả về dict: {parent_folder_id: {filename: file_obj}}
        """
        query = (
            "(name = 'chapters.zip' or name = 'translated_chapters.zip' or "
            "name = 'info.json' or name = 'glossary.json' or "
            "name = 'summary.txt' or name = 'checkpoints.json') and trashed = false"
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

    def inspect_web_priority_stories(
        self,
        chapter_inspector,
        limit: int = 100,
        strategy: str = "SPLIT",
        max_per_story: int = 0
    ) -> Tuple[List[Dict[str, Any]], int, Set[str]]:
        """
        Chặng 1: Xử lý Fast-Path các truyện ưu tiên từ Web API theo driveUrl (Folder ID).
        - Trỏ thẳng vào driveUrl lấy file mà không phụ thuộc thư mục cha.
        - Đọc 1MB đuôi file zip qua RAM kiểm tra diff chương tồn đọng.
        - Nạp vào hàng đợi và trừ dần quota.
        - Ghi nhận mọi story_id đã thẩm định vào processed_story_ids để chống trùng lặp ở Chặng 2.
        Trả về: (web_queue, accumulated_chapters, processed_story_ids)
        """
        web_queue = []
        current_count = 0
        processed_story_ids = set()

        if not self.web_priority_mgr:
            return web_queue, current_count, processed_story_ids

        priority_stories = self.web_priority_mgr.priority_stories
        if not priority_stories:
            return web_queue, current_count, processed_story_ids

        print(f"\n🚀 [CHẶNG 1] Bắt đầu xử lý Fast-Path Web Priority ({len(priority_stories)} bộ truyện từ Web API)...")

        for story_id, item in priority_stories.items():
            processed_story_ids.add(story_id)
            folder_id = item.get('drive_folder_id', '').strip()

            if not folder_id:
                print(f"⚠️ [{story_id}] Thiếu driveUrl (folder ID) từ API. Bỏ qua.")
                continue

            # 1. Truy vấn trực tiếp các file trong folder_id trên Google Drive
            query = (
                f"'{folder_id}' in parents and "
                f"(name = 'chapters.zip' or name = 'translated_chapters.zip' or "
                f"name = 'info.json' or name = 'glossary.json' or "
                f"name = 'summary.txt' or name = 'checkpoints.json') and trashed = false"
            )
            try:
                resp = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name, modifiedTime, size, parents)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                story_files = {f['name']: f for f in resp.get('files', [])}
            except Exception as e:
                print(f"⚠️ [{story_id}] Lỗi truy vấn file từ folder {folder_id}: {e}")
                continue

            if 'chapters.zip' not in story_files or 'translated_chapters.zip' not in story_files:
                print(f"⚠️ [{story_id}] Thiếu chapters.zip hoặc translated_chapters.zip trong {folder_id}. Bỏ qua.")
                continue

            # 2. Nhận diện nguồn (Source) qua parents của folder hoặc mặc định
            source = "web_priority"
            try:
                folder_obj = self.service.files().get(
                    fileId=folder_id,
                    fields='parents',
                    supportsAllDrives=True
                ).execute()
                parents = folder_obj.get('parents', [])
                for s_name, s_id in DRIVE_FOLDERS.items():
                    if s_id in parents:
                        source = s_name
                        break
            except Exception:
                pass

            if source == "web_priority" and item.get('source'):
                source = item.get('source')

            chapters_file = story_files['chapters.zip']
            trans_file = story_files['translated_chapters.zip']

            s_info = {
                'source': source,
                'story_id': story_id,
                'story_folder_id': folder_id,
                'chapters_file': chapters_file,
                'translated_chapters_file': trans_file,
                'modified_time': chapters_file.get('modifiedTime'),
                'files_meta': story_files,
                'is_web_priority': True,
                'web_meta': item
            }

            # 3. Thẩm định mục lục zip từ xa qua RAM (Zero Disk Usage)
            inspected = chapter_inspector.inspect_story_remotely(s_info)
            if not inspected.get('is_valid', False):
                print(f"  ⚠️ [{story_id}] [ƯU TIÊN WEB]: Bỏ qua: {inspected.get('reason')}")
                continue

            new_chaps = inspected.get('new_chapters', [])
            if not new_chaps:
                print(f"  ☕ [{story_id}] [ƯU TIÊN WEB]: Đã dịch 100% ({inspected['translated_chapters_count']}/{inspected['raw_chapters_count']} chaps). Không phát sinh chương mới.")
                continue

            chap_len = len(new_chaps)
            remaining_quota = limit - current_count

            print(f"  📊 [{story_id}] ⭐ [ƯU TIÊN WEB] Gốc: {inspected['raw_chapters_count']} | Đã dịch: {inspected['translated_chapters_count']} | Cần dịch tiếp: {chap_len} chương")

            if remaining_quota <= 0:
                break

            # Xác định số lượng chương mong muốn cho truyện này (tôn trọng max_per_story nếu > 0)
            desired_len = min(chap_len, max_per_story) if max_per_story > 0 else chap_len

            if current_count + desired_len <= limit:
                selected_chaps = new_chaps[:desired_len]
                is_partial = len(selected_chaps) < chap_len
                web_queue.append({
                    'story_id': story_id,
                    'source': source,
                    'story_info': s_info,
                    'chapters_to_translate': selected_chaps,
                    'is_partial': is_partial,
                    'total_new_available': chap_len,
                    'inspected_meta': inspected,
                    'is_web_priority': True
                })
                current_count += len(selected_chaps)
                if is_partial:
                    print(f"  ✂️ [{story_id}]: Giới hạn tối đa {max_per_story} chaps/truyện. Lấy {len(selected_chaps)}/{chap_len} chương đầu. (Tích lũy: {current_count}/{limit})")
                else:
                    print(f"  ➕ [{story_id}]: Nhận toàn bộ {chap_len} chương. (Tích lũy: {current_count}/{limit})")
            else:
                if strategy == "SPLIT":
                    selected_chaps = new_chaps[:remaining_quota]
                    web_queue.append({
                        'story_id': story_id,
                        'source': source,
                        'story_info': s_info,
                        'chapters_to_translate': selected_chaps,
                        'is_partial': True,
                        'total_new_available': chap_len,
                        'inspected_meta': inspected,
                        'is_web_priority': True
                    })
                    current_count += len(selected_chaps)
                    print(f"  ✂️ [{story_id}]: Chạm trần quota! Lấy {len(selected_chaps)}/{chap_len} chương đầu (chế độ SPLIT). (Tích lũy: {current_count}/{limit})")
                    break
                else:
                    print(f"  🛑 [{story_id}]: Có {desired_len} chương cần dịch, vượt quota còn lại ({remaining_quota}). Dừng theo ATOMIC.")
                    break

            if current_count >= limit:
                print(f"🎯 ĐÃ ĐẠT TRẦN {limit} CHƯƠNG NGAY TỪ CHẶNG 1 (WEB PRIORITY)!")
                break

        print(f"✅ Hoàn tất Chặng 1: {len(web_queue)} truyện ưu tiên được chọn, tích lũy {current_count}/{limit} chương.")
        return web_queue, current_count, processed_story_ids

    def scan_all_sources(
        self,
        sort_by: str = "recent",
        excluded_story_ids: Optional[Set[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Quét toàn bộ các nguồn theo thứ tự ưu tiên bằng Batch Query:
        - Gom toàn bộ file và thư mục trong 1-2 lần gọi API.
        - Bỏ qua các truyện đã xử lý ở Chặng 1 (excluded_story_ids - Deduplication).
        - Lọc các truyện đang dịch dở (có cả chapters.zip và translated_chapters.zip) trong Whitelist.
        - Sắp xếp danh sách theo tiêu chí sort_by (mặc định: recent).
        """
        print("⚡ Đang quét siêu tốc toàn bộ kho truyện trên Google Drive bằng Batch Query...")
        all_files_by_parent = self.fetch_all_relevant_files()

        results = {}

        for source in SOURCE_PRIORITY:
            root_id = DRIVE_FOLDERS.get(source)
            if not root_id:
                results[source] = []
                continue

            print(f"📁 Đang lấy danh sách thư mục truyện nguồn [{source}]...")
            child_folders = self.fetch_all_child_folders(root_id)
            print(f"   Tìm thấy {len(child_folders)} thư mục truyện trong [{source}].")

            eligible_stories = []

            for folder_id, folder_obj in child_folders.items():
                story_id = folder_obj['name']

                # BƯỚC CHỐNG TRÙNG LẶP (Deduplication Check):
                # Nếu truyện này đã được xử lý hoặc thẩm định ở Chặng 1 (Web Priority) -> BỎ QUA NGAY
                if excluded_story_ids and story_id in excluded_story_ids:
                    continue

                # Điều kiện 0: BẮT BUỘC nằm trong danh sách Whitelist (Google Sheet)
                meta_from_sheet = None
                if self.whitelist_mgr:
                    if not self.whitelist_mgr.is_whitelisted(source, story_id):
                        continue
                    meta_from_sheet = self.whitelist_mgr.get_story_info(source, story_id)

                story_files = all_files_by_parent.get(folder_id, {})

                # Điều kiện 1: Đang dịch dở (phải có cả chapters.zip và translated_chapters.zip)
                if 'chapters.zip' not in story_files or 'translated_chapters.zip' not in story_files:
                    continue

                chapters_file = story_files['chapters.zip']
                trans_file = story_files['translated_chapters.zip']
                chap_mod = chapters_file.get('modifiedTime')

                eligible_stories.append({
                    'source': source,
                    'story_id': story_id,
                    'story_folder_id': folder_id,
                    'chapters_file': chapters_file,
                    'translated_chapters_file': trans_file,
                    'modified_time': chap_mod,
                    'files_meta': story_files,
                    'is_web_priority': False,
                    'web_meta': None,
                    'sheet_meta': meta_from_sheet
                })

            # Sắp xếp danh sách truyện ứng viên theo tiêu chí sort_by
            if sort_by == "oldest":
                eligible_stories.sort(key=lambda x: x['modified_time'] or '', reverse=False)
            else:
                # Mặc định: recent (mới cập nhật nhất lên đầu)
                eligible_stories.sort(key=lambda x: x['modified_time'] or '', reverse=True)

            print(f"✅ Nguồn [{source}]: Tìm thấy {len(eligible_stories)} bộ truyện đang dịch dở (được xếp theo: {sort_by}).")
            results[source] = eligible_stories

        return results

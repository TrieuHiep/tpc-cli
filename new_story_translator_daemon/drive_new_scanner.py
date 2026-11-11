"""
Module quét và phát hiện các bộ truyện MỚI trên Google Drive:
Điều kiện chọn truyện mới:
1. ĐÃ CÓ file raw chapters.zip trên Google Drive.
2. CHƯA CÓ file translated_chapters.zip (hoặc file rỗng <= 100 bytes).
3. Đạt yêu cầu thẩm định cấu trúc chương (không khuyết chương / nhảy cóc).
"""
from typing import Dict, Any, List, Optional
from new_story_translator_daemon.config import RAW_DRIVE_FOLDERS, VAULT_DRIVE_FOLDERS, SOURCE_PRIORITY

class DriveNewScanner:
    """Quét và lọc các bộ truyện mới tinh từ Google Drive (Đối chiếu Kho Nguồn Raw ↔ Kho Dịch tpc-dw)."""

    def __init__(self, gdrive_service):
        self.gdrive_service = gdrive_service
        self.service = self.gdrive_service.service

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

    def fetch_child_folders_by_name(
        self,
        root_folder_id: str,
        files_by_parent: Dict[str, Dict[str, Any]],
        preferred_filename: str,
        label: str = ""
    ) -> Dict[str, Dict[str, str]]:
        """
        Lập bảng băm Map<story_id, folder_obj> cho một thư mục nguồn.
        Nếu phát hiện 2 folder trùng tên trên Google Drive, ưu tiên chọn folder có chứa preferred_filename hợp lệ.
        """
        raw_folders = self.fetch_all_child_folders(root_folder_id)
        by_name: Dict[str, Dict[str, str]] = {}

        for fid, fobj in raw_folders.items():
            name = (fobj.get('name') or '').strip()
            if not name:
                continue

            if name not in by_name:
                by_name[name] = fobj
                continue

            existing_fobj = by_name[name]
            existing_id = existing_fobj['id']
            existing_target = files_by_parent.get(existing_id, {}).get(preferred_filename)
            new_target = files_by_parent.get(fid, {}).get(preferred_filename)

            existing_size = int(existing_target.get('size', 0)) if existing_target else -1
            new_size = int(new_target.get('size', 0)) if new_target else -1

            if new_size > existing_size:
                print(f"   ⚠️ [{label}] Trùng tên folder '{name}': chọn ID {fid} (có {preferred_filename}) thay cho {existing_id}.")
                by_name[name] = fobj
            else:
                print(f"   ⚠️ [{label}] Trùng tên folder '{name}': giữ ID {existing_id}, bỏ qua bản trùng {fid}.")

        return by_name

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
        Quét và lọc các bộ truyện MỚI từ các nguồn trên Drive (Ánh xạ 2 tầng Raw ↔ Vault tpc-dw):
        - Tầng 1: Ghép cặp RAW_DRIVE_FOLDERS[source] và VAULT_DRIVE_FOLDERS[source].
        - Tầng 2: Left Anti Join theo story_id (Có chapters.zip bên Raw nhưng chưa có translated_chapters.zip bên Vault).
        """
        sources_to_scan = [target_source] if target_source else SOURCE_PRIORITY
        results = {}

        print("\n🔍 Đang gom danh sách toàn bộ file từ Google Drive (Kho Nguồn Raw & Kho Dịch tpc-dw)...")
        all_files_by_parent = self.fetch_all_relevant_files()
        print(f"📦 Đã thu thập dữ liệu của {len(all_files_by_parent)} thư mục truyện.")

        for source in sources_to_scan:
            raw_root_id = RAW_DRIVE_FOLDERS.get(source)
            vault_root_id = VAULT_DRIVE_FOLDERS.get(source)
            if not raw_root_id or not vault_root_id:
                continue

            print(f"\n📁 Đang quét nguồn [{source}] (Raw Root: {raw_root_id} ↔ Vault Root: {vault_root_id})...")
            raw_map = self.fetch_child_folders_by_name(
                raw_root_id, all_files_by_parent, preferred_filename="chapters.zip", label=f"{source}:RAW"
            )
            vault_map = self.fetch_child_folders_by_name(
                vault_root_id, all_files_by_parent, preferred_filename="translated_chapters.zip", label=f"{source}:VAULT"
            )
            print(f"   Tìm thấy {len(raw_map)} thư mục bên Kho Nguồn | {len(vault_map)} thư mục bên Kho Dịch (tpc-dw).")

            eligible_new_stories = []

            for story_id, raw_folder_obj in raw_map.items():
                raw_folder_id = raw_folder_obj['id']
                raw_files = all_files_by_parent.get(raw_folder_id, {})

                # Điều kiện 1: BẮT BUỘC phải có chapters.zip (raw tiếng Trung) bên Kho Nguồn
                if 'chapters.zip' not in raw_files:
                    continue

                # Điều kiện 2: Đối chiếu bên Kho Dịch tpc-dw (CHƯA CÓ folder hoặc CHƯA CÓ translated_chapters.zip > 100B)
                vault_folder_obj = vault_map.get(story_id)
                vault_folder_id = vault_folder_obj['id'] if vault_folder_obj else None
                vault_files = all_files_by_parent.get(vault_folder_id, {}) if vault_folder_id else {}

                tzip = vault_files.get('translated_chapters.zip')
                if tzip:
                    tzip_size = int(tzip.get('size', 0))
                    if tzip_size > 100:
                        # Đã có bản dịch trên Kho Dịch tpc-dw -> Bỏ qua, nhường cho daemon dịch tiếp
                        continue

                chapters_file = raw_files['chapters.zip']
                chap_mod = chapters_file.get('modifiedTime')

                # Chỉ lấy các file thuộc Kho Nguồn (tránh đọc nhầm file cũ nếu còn sót bên Kho Nguồn)
                clean_raw_meta = {}
                for fname in ('chapters.zip', 'info.json'):
                    if fname in raw_files:
                        clean_raw_meta[fname] = raw_files[fname]

                eligible_new_stories.append({
                    'source': source,
                    'story_id': story_id,
                    'raw_folder_id': raw_folder_id,
                    'vault_folder_id': vault_folder_id,
                    'story_folder_id': raw_folder_id,
                    'chapters_file': chapters_file,
                    'translated_chapters_file': tzip,
                    'modified_time': chap_mod,
                    'files_meta': clean_raw_meta,
                    'sheet_meta': None
                })

            # Sắp xếp theo sort_by
            if sort_by == "oldest":
                eligible_new_stories.sort(key=lambda x: x['modified_time'] or '', reverse=False)
            else:
                eligible_new_stories.sort(key=lambda x: x['modified_time'] or '', reverse=True)

            print(f"✨ Nguồn [{source}]: Tìm thấy {len(eligible_new_stories)} bộ truyện MỚI CHƯA DỊCH trên tpc-dw (xếp theo: {sort_by}).")
            results[source] = eligible_new_stories

        return results

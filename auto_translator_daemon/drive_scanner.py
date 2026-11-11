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
from auto_translator_daemon.config import RAW_DRIVE_FOLDERS, VAULT_DRIVE_FOLDERS, SOURCE_PRIORITY
from auto_translator_daemon.web_priority_manager import WebPriorityManager

class DriveScanner:
    """Quét và lọc danh sách truyện đủ điều kiện từ Google Drive bằng Batch Query siêu tốc (Dual-Drive: Raw ↔ Vault tpc-dw)."""

    def __init__(
        self,
        gdrive_service: Optional[GoogleDriveService] = None,
        web_priority_mgr: Optional[WebPriorityManager] = None
    ):
        self.gdrive_service = gdrive_service or GoogleDriveService()
        self.service = self.gdrive_service.service
        self.web_priority_mgr = web_priority_mgr
        self._batch_files_by_parent: Optional[Dict[str, Dict[str, Any]]] = None
        self._batch_raw_maps: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._batch_vault_maps: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._batch_raw_id_to_meta: Dict[str, Tuple[str, str]] = {}
        self._batch_vault_id_to_meta: Dict[str, Tuple[str, str]] = {}

    def _ensure_batch_index(self) -> None:
        """
        Tải trước và lập chỉ mục RAM một lần duy nhất cho toàn bộ 5 nguồn (Raw ↔ Vault tpc-dw),
        dùng chung giữa Chặng 1 (khi có nhiều truyện ưu tiên) và Chặng 2 để triệt tiêu hàng trăm API call lẻ.
        """
        if self._batch_files_by_parent is not None:
            return

        print("⚡ Đang tải Batch Index toàn bộ kho truyện (Kho Nguồn Raw & Kho Dịch tpc-dw)...")
        self._batch_files_by_parent = self.fetch_all_relevant_files()
        self._batch_raw_maps = {}
        self._batch_vault_maps = {}
        self._batch_raw_id_to_meta = {}
        self._batch_vault_id_to_meta = {}

        for source in SOURCE_PRIORITY:
            raw_root_id = RAW_DRIVE_FOLDERS.get(source)
            vault_root_id = VAULT_DRIVE_FOLDERS.get(source)
            if not raw_root_id or not vault_root_id:
                continue

            raw_map = self.fetch_child_folders_by_name(
                raw_root_id, self._batch_files_by_parent, preferred_filename="chapters.zip", label=f"{source}:RAW"
            )
            vault_map = self.fetch_child_folders_by_name(
                vault_root_id, self._batch_files_by_parent, preferred_filename="translated_chapters.zip", label=f"{source}:VAULT"
            )
            self._batch_raw_maps[source] = raw_map
            self._batch_vault_maps[source] = vault_map

            for s_name, fobj in raw_map.items():
                self._batch_raw_id_to_meta[fobj['id']] = (source, s_name)
            for s_name, fobj in vault_map.items():
                self._batch_vault_id_to_meta[fobj['id']] = (source, s_name)

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
            if not isinstance(page_token, str) or not page_token:
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
        Nếu có 2 folder trùng tên trên Drive, ưu tiên chọn folder đang chứa preferred_filename hợp lệ.
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

    def _find_child_folder_id(self, root_folder_id: str, story_id: str) -> Optional[str]:
        """Tìm nhanh folder con theo tên story_id bên trong root_folder_id (dùng cho Fast-Path Chặng 1)."""
        safe_name = story_id.strip().replace("'", "\\'")
        query = (
            f"'{root_folder_id}' in parents and name = '{safe_name}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        resp = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = resp.get('files', [])
        return files[0]['id'] if files else None

    def _list_folder_files(self, folder_id: str, filenames: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
        """Lấy metadata các file chỉ định bên trong 1 folder_id."""
        name_clauses = " or ".join(f"name = '{fn}'" for fn in filenames)
        query = f"'{folder_id}' in parents and ({name_clauses}) and trashed = false"
        resp = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, modifiedTime, size, md5Checksum, parents)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        return {f['name']: f for f in resp.get('files', [])}

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
                fields='nextPageToken, files(id, name, modifiedTime, size, md5Checksum, parents)',
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
            if not isinstance(page_token, str) or not page_token:
                break

        return files_by_parent

    def inspect_web_priority_stories(
        self,
        chapter_inspector,
        limit: int = 100,
        strategy: str = "SPLIT",
        max_per_story: int = 0,
        priority_story_ids: Optional[List[str]] = None,
        skip_stories_over: Optional[int] = None
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
        skipped_stories = []

        if not self.web_priority_mgr:
            return web_queue, current_count, processed_story_ids, skipped_stories

        priority_stories = self.web_priority_mgr.priority_stories
        if not priority_stories:
            return web_queue, current_count, processed_story_ids, skipped_stories

        print(f"\n🚀 [CHẶNG 1] Bắt đầu xử lý Fast-Path Web Priority ({len(priority_stories)} bộ truyện từ Web API)...")

        items_to_inspect = list(priority_stories.items())
        if priority_story_ids:
            prio_order = {sid: idx for idx, sid in enumerate(priority_story_ids)}
            items_to_inspect.sort(key=lambda x: prio_order.get(x[0], 9999))

        # Tối ưu siêu tốc: Nếu có từ 5 truyện Web Priority trở lên, nạp sẵn Batch Index 1 lần duy nhất
        # (chỉ ~11 request cho toàn bộ kho, tái sử dụng luôn ở Chặng 2 thay vì bắn hàng trăm API call lẻ)
        if len(items_to_inspect) >= 5:
            self._ensure_batch_index()

        for story_id, item in items_to_inspect:
            processed_story_ids.add(story_id)
            folder_id = item.get('drive_folder_id', '').strip()

            if not folder_id:
                print(f"⚠️ [{story_id}] Thiếu driveUrl (folder ID) từ API. Bỏ qua.")
                continue

            # 1. Nhận diện nguồn và ánh xạ cặp (raw_folder_id, vault_folder_id) theo thiết kế 2 tầng
            source = "web_priority"
            raw_folder_id = None
            vault_folder_id = None
            folder_actual_name = story_id
            used_batch_index = False

            if self._batch_files_by_parent is not None:
                if folder_id in self._batch_raw_id_to_meta:
                    source, folder_actual_name = self._batch_raw_id_to_meta[folder_id]
                    raw_folder_id = folder_id
                    vmap = self._batch_vault_maps.get(source, {})
                    vobj = vmap.get(story_id) or vmap.get(folder_actual_name)
                    if vobj:
                        vault_folder_id = vobj['id']
                        used_batch_index = True
                elif folder_id in self._batch_vault_id_to_meta:
                    source, folder_actual_name = self._batch_vault_id_to_meta[folder_id]
                    vault_folder_id = folder_id
                    rmap = self._batch_raw_maps.get(source, {})
                    robj = rmap.get(story_id) or rmap.get(folder_actual_name)
                    if robj:
                        raw_folder_id = robj['id']
                        used_batch_index = True

            if not used_batch_index:
                try:
                    folder_obj = self.service.files().get(
                        fileId=folder_id,
                        fields='id, name, parents',
                        supportsAllDrives=True
                    ).execute()
                    folder_actual_name = (folder_obj.get('name') or story_id).strip()
                    parents = folder_obj.get('parents', [])

                    for s_name, s_id in RAW_DRIVE_FOLDERS.items():
                        if s_id in parents:
                            source = s_name
                            raw_folder_id = folder_id
                            break

                    if not raw_folder_id:
                        for s_name, s_id in VAULT_DRIVE_FOLDERS.items():
                            if s_id in parents:
                                source = s_name
                                vault_folder_id = folder_id
                                break
                except Exception as e:
                    print(f"⚠️ [{story_id}] Không đọc được thông tin folder {folder_id} từ Drive: {e}. Bỏ qua.")
                    continue

                # Ánh xạ sang kho đối ứng theo story_id (hoặc tên folder thực tế nếu khác)
                try:
                    if raw_folder_id and source in VAULT_DRIVE_FOLDERS:
                        vault_root = VAULT_DRIVE_FOLDERS[source]
                        vault_folder_id = self._find_child_folder_id(vault_root, story_id)
                        if not vault_folder_id and folder_actual_name != story_id:
                            vault_folder_id = self._find_child_folder_id(vault_root, folder_actual_name)
                    elif vault_folder_id and source in RAW_DRIVE_FOLDERS:
                        raw_root = RAW_DRIVE_FOLDERS[source]
                        raw_folder_id = self._find_child_folder_id(raw_root, story_id)
                        if not raw_folder_id and folder_actual_name != story_id:
                            raw_folder_id = self._find_child_folder_id(raw_root, folder_actual_name)
                    else:
                        # Fallback nếu folder_id không nằm trực tiếp dưới 5 root đã biết: dò trên 5 nguồn Vault
                        raw_folder_id = folder_id
                        api_src = (item.get('source') or '').strip().lower()
                        if 'truyenwiki' in api_src:
                            api_src = 'truyendichwiki'
                        search_order = [api_src] + [s for s in SOURCE_PRIORITY if s != api_src] if api_src in VAULT_DRIVE_FOLDERS else SOURCE_PRIORITY
                        for cand_src in search_order:
                            vid = self._find_child_folder_id(VAULT_DRIVE_FOLDERS[cand_src], story_id)
                            if vid:
                                source = cand_src
                                vault_folder_id = vid
                                break
                except Exception as e:
                    print(f"⚠️ [{story_id}] Lỗi ánh xạ folder đối ứng trên tpc-dw: {e}. Bỏ qua.")
                    continue

            if not raw_folder_id or not vault_folder_id:
                print(f"⚠️ [{story_id}] Chưa khớp đủ cặp thư mục (Raw={raw_folder_id}, Vault={vault_folder_id}). Bỏ qua.")
                continue

            # 2. Truy vấn tách biệt file Raw từ Kho Nguồn và file Dịch/Metadata từ Kho Dịch tpc-dw
            if used_batch_index and self._batch_files_by_parent is not None:
                raw_parent_files = self._batch_files_by_parent.get(raw_folder_id, {})
                vault_parent_files = self._batch_files_by_parent.get(vault_folder_id, {})
                raw_files = {k: raw_parent_files[k] for k in ('chapters.zip', 'info.json') if k in raw_parent_files}
                vault_files = {
                    k: vault_parent_files[k]
                    for k in ('translated_chapters.zip', 'glossary.json', 'summary.txt', 'checkpoints.json')
                    if k in vault_parent_files
                }
            else:
                try:
                    raw_files = self._list_folder_files(raw_folder_id, ('chapters.zip', 'info.json'))
                    vault_files = self._list_folder_files(
                        vault_folder_id,
                        ('translated_chapters.zip', 'glossary.json', 'summary.txt', 'checkpoints.json')
                    )
                except Exception as e:
                    print(f"⚠️ [{story_id}] Lỗi truy vấn file từ Raw ({raw_folder_id}) / Vault ({vault_folder_id}): {e}")
                    continue

            if 'chapters.zip' not in raw_files:
                print(f"⚠️ [{story_id}] Thiếu chapters.zip bên Kho Nguồn ({raw_folder_id}). Bỏ qua.")
                continue

            trans_file = vault_files.get('translated_chapters.zip')
            if not trans_file or int(trans_file.get('size', 0)) <= 100:
                print(f"⚠️ [{story_id}] Chưa có translated_chapters.zip hợp lệ bên Kho Dịch tpc-dw ({vault_folder_id}). Bỏ qua.")
                continue

            chapters_file = raw_files['chapters.zip']
            story_files = {**raw_files, **vault_files}

            s_info = {
                'source': source,
                'story_id': story_id,
                'raw_folder_id': raw_folder_id,
                'vault_folder_id': vault_folder_id,
                'story_folder_id': vault_folder_id,
                'chapters_file': chapters_file,
                'translated_chapters_file': trans_file,
                'modified_time': chapters_file.get('modifiedTime'),
                'files_meta': story_files,
                'is_web_priority': True,
                'web_meta': item
            }

            # 3. Thẩm định mục lục zip từ xa qua RAM (Zero Disk Usage)
            inspected = chapter_inspector.inspect_story_remotely(s_info, skip_stories_over=skip_stories_over)
            if not inspected.get('is_valid', False):
                reason = inspected.get('reason', 'Không hợp lệ')
                if inspected.get('is_too_long'):
                    print(f"  ⏭️ [{story_id}] ⭐ [ƯU TIÊN WEB]: {reason}. Bỏ qua truyện quá dài.")
                elif inspected.get('is_gap'):
                    print(f"  ❌ [{story_id}] ⭐ [ƯU TIÊN WEB] [SKIP - NHẢY CÓC]: {reason}")
                    title = item.get('name') or item.get('title') or story_id
                    skipped_stories.append({
                        'source': source,
                        'story_id': story_id,
                        'title': title,
                        'reason': reason,
                        'folder_id': raw_folder_id,
                        'is_web_priority': True
                    })
                else:
                    print(f"  ⚠️ [{story_id}] [ƯU TIÊN WEB]: Bỏ qua: {reason}")
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
        return web_queue, current_count, processed_story_ids, skipped_stories

    def scan_all_sources(
        self,
        sort_by: str = "recent",
        excluded_story_ids: Optional[Set[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Quét toàn bộ các nguồn theo thứ tự ưu tiên bằng Batch Query (Ánh xạ 2 tầng Raw ↔ Vault tpc-dw):
        - Tầng 1: Ghép cặp RAW_DRIVE_FOLDERS[source] và VAULT_DRIVE_FOLDERS[source].
        - Tầng 2: Inner Join theo story_id (Có chapters.zip ở Raw VÀ có translated_chapters.zip > 100B ở Vault).
        - Bỏ qua các truyện đã xử lý ở Chặng 1 (excluded_story_ids - Deduplication).
        """
        print("⚡ Đang quét siêu tốc toàn bộ kho truyện (Kho Nguồn Raw & Kho Dịch tpc-dw) bằng Batch Query...")
        self._ensure_batch_index()
        all_files_by_parent = self._batch_files_by_parent or {}

        results = {}

        for source in SOURCE_PRIORITY:
            raw_root_id = RAW_DRIVE_FOLDERS.get(source)
            vault_root_id = VAULT_DRIVE_FOLDERS.get(source)
            if not raw_root_id or not vault_root_id:
                results[source] = []
                continue

            print(f"📁 Đang đối chiếu thư mục nguồn [{source}] (Raw ↔ Vault tpc-dw)...")
            raw_map = self._batch_raw_maps.get(source, {})
            vault_map = self._batch_vault_maps.get(source, {})
            print(f"   Tìm thấy {len(raw_map)} thư mục Raw | {len(vault_map)} thư mục Vault (tpc-dw) trong [{source}].")

            eligible_stories = []

            # Duyệt theo vault_map (tập các truyện đã có thư mục trên tpc-dw) và Join với raw_map theo story_id
            for story_id, vault_folder_obj in vault_map.items():
                # BƯỚC CHỐNG TRÙNG LẶP (Deduplication Check):
                if excluded_story_ids and story_id in excluded_story_ids:
                    continue

                raw_folder_obj = raw_map.get(story_id)
                if not raw_folder_obj:
                    continue

                raw_folder_id = raw_folder_obj['id']
                vault_folder_id = vault_folder_obj['id']

                raw_files = all_files_by_parent.get(raw_folder_id, {})
                vault_files = all_files_by_parent.get(vault_folder_id, {})

                # Điều kiện 1: Phải có chapters.zip ở Kho Nguồn VÀ translated_chapters.zip hợp lệ ở Kho Dịch tpc-dw
                if 'chapters.zip' not in raw_files or 'translated_chapters.zip' not in vault_files:
                    continue

                trans_file = vault_files['translated_chapters.zip']
                if int(trans_file.get('size', 0)) <= 100:
                    continue

                chapters_file = raw_files['chapters.zip']
                chap_mod = chapters_file.get('modifiedTime')

                # Gộp files_meta phân tách chặt theo từng kho (không đọc nhầm bản cũ bên Kho Nguồn)
                merged_files_meta = {}
                for fname in ('chapters.zip', 'info.json'):
                    if fname in raw_files:
                        merged_files_meta[fname] = raw_files[fname]
                for fname in ('translated_chapters.zip', 'glossary.json', 'summary.txt', 'checkpoints.json'):
                    if fname in vault_files:
                        merged_files_meta[fname] = vault_files[fname]

                eligible_stories.append({
                    'source': source,
                    'story_id': story_id,
                    'raw_folder_id': raw_folder_id,
                    'vault_folder_id': vault_folder_id,
                    'story_folder_id': vault_folder_id,
                    'chapters_file': chapters_file,
                    'translated_chapters_file': trans_file,
                    'modified_time': chap_mod,
                    'files_meta': merged_files_meta,
                    'is_web_priority': False,
                    'web_meta': None,
                    'sheet_meta': None
                })

            # Sắp xếp danh sách truyện ứng viên theo tiêu chí sort_by
            if sort_by == "oldest":
                eligible_stories.sort(key=lambda x: x['modified_time'] or '', reverse=False)
            else:
                eligible_stories.sort(key=lambda x: x['modified_time'] or '', reverse=True)

            print(f"✅ Nguồn [{source}]: Khớp được {len(eligible_stories)} bộ truyện đang dịch dở trên tpc-dw (xếp theo: {sort_by}).")
            results[source] = eligible_stories

        return results

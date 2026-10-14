"""
Module kiểm tra tính tuần tự và đối chiếu diff chương tồn đọng từ xa qua RAM.
Chỉ tải file về ổ cứng khi truyện đó thực sự được chọn vào mẻ dịch (Zero disk usage khi quét).
"""
import re
import json
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from googleapiclient.http import MediaIoBaseDownload

from auto_translator_daemon.config import SCAN_CACHE_FILE
from auto_translator_daemon.remote_zip_inspector import RemoteZipInspector

class ChapterInspector:
    """Thẩm định mục lục ZIP từ xa qua RAM (kèm cơ chế Scan Cache) và tải truyện về thư mục làm việc khi cần dịch."""

    def __init__(self, gdrive_service, use_cache: bool = True, refresh_cache: bool = False, cache_file: Path = SCAN_CACHE_FILE):
        self.gdrive_service = gdrive_service
        self.service = self.gdrive_service.service
        self.use_cache = use_cache
        self.cache_file = cache_file
        self.scan_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_dirty = False
        self.cache_hits = 0
        self.cache_misses = 0

        if self.use_cache:
            if refresh_cache:
                print(f"🔄 [ScanCache] Cờ --refresh-cache đang bật: Khởi tạo lại cache mới hoàn toàn.")
                self._cache_dirty = True
            else:
                self._load_cache()

        # Khởi tạo RemoteZipInspector với credentials để tự động refresh token
        creds = getattr(self.service._http, 'credentials', None)
        if creds and not creds.valid:
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            except Exception:
                pass
        self.remote_inspector = RemoteZipInspector(
            auth_token=creds.token if creds else "",
            credentials=creds
        )

    def _load_cache(self):
        """Nạp dữ liệu cache thẩm định từ file scan_cache.json vào RAM."""
        if not self.cache_file or not self.cache_file.exists():
            return
        try:
            raw_text = self.cache_file.read_text(encoding='utf-8')
            data = json.loads(raw_text)
            if isinstance(data, dict):
                self.scan_cache = data
        except Exception as e:
            try:
                print(f"⚠️ [ScanCache] Không thể đọc file cache {self.cache_file} ({e}), sẽ khởi tạo cache mới.")
            except Exception:
                pass
            self.scan_cache = {}
            return

        try:
            print(f"⚡ [ScanCache] Đã nạp {len(self.scan_cache)} bản ghi cache từ {self.cache_file.name}.")
        except Exception:
            pass

    def save_cache(self):
        """Ghi dữ liệu cache từ RAM xuống đĩa theo cơ chế Atomic Write."""
        if not self.use_cache or not self._cache_dirty or not self.cache_file:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.cache_file.with_suffix(".json.tmp")
            tmp_file.write_text(
                json.dumps(self.scan_cache, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            tmp_file.replace(self.cache_file)
            self._cache_dirty = False
        except Exception as e:
            print(f"⚠️ [ScanCache] Lỗi khi lưu file cache {self.cache_file}: {e}")

    @staticmethod
    def _build_file_sig(file_meta: Optional[Dict[str, Any]]) -> str:
        """Tạo chuỗi chữ ký định danh phiên bản file ZIP từ metadata của Google Drive."""
        if not file_meta:
            return ""
        fid = file_meta.get('id', '')
        fsize = file_meta.get('size', '')
        fmd5 = file_meta.get('md5Checksum', '')
        fmod = file_meta.get('modifiedTime', '')
        return f"{fid}_{fsize}_{fmd5}_{fmod}"

    def _update_cache_entry(
        self,
        story_id: str,
        czip_sig: str,
        tzip_sig: str,
        is_valid: bool,
        is_gap: bool,
        reason: str,
        raw_count: int,
        trans_count: int,
        first_new: Optional[int] = None,
        last_new: Optional[int] = None
    ):
        """Cập nhật kết quả thẩm định của 1 bộ truyện vào RAM Cache."""
        if not self.use_cache:
            return
        self.scan_cache[story_id] = {
            'czip_sig': czip_sig,
            'tzip_sig': tzip_sig,
            'is_valid': is_valid,
            'is_gap': is_gap,
            'reason': reason,
            'raw_chapters_count': raw_count,
            'translated_chapters_count': trans_count,
            'first_new': first_new,
            'last_new': last_new,
            'updated_at': datetime.now().isoformat(timespec='seconds')
        }
        self._cache_dirty = True

    def download_file_to_path(self, file_id: str, dest_path: Path) -> bool:
        """Tải một file từ Google Drive về đường dẫn cục bộ."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
            with open(dest_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request, chunksize=1024*1024*5)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            return True
        except Exception as e:
            print(f"❌ Lỗi tải file {file_id} về {dest_path}: {e}")
            return False

    @staticmethod
    def check_sequential(chapter_numbers: List[int]) -> Tuple[bool, str]:
        """
        Kiểm tra số thứ tự chapters có tăng tuần tự không (1, 2, 3... không bị nhảy cóc).
        """
        if not chapter_numbers:
            return False, "Không tìm thấy chương nào trong chapters.zip"

        sorted_nums = sorted(chapter_numbers)
        start_num = sorted_nums[0]

        # Bắt buộc bắt đầu từ chương 1
        if start_num != 1:
            return False, f"Chương bắt đầu từ {start_num}, không phải từ chương 1"

        expected = list(range(start_num, start_num + len(sorted_nums)))
        if sorted_nums != expected:
            for act, exp in zip(sorted_nums, expected):
                if act != exp:
                    return False, f"Bị khuyết chương: Mong đợi chương {exp} nhưng lại thấy chương {act} (nhảy cóc)"
            return False, "Số thứ tự chương bị khuyết hoặc nhảy cóc"

        return True, "OK"

    def inspect_story_remotely(self, story_info: Dict[str, Any], skip_stories_over: Optional[int] = None) -> Dict[str, Any]:
        """
        Thẩm định diff chương hoàn toàn từ xa qua RAM (Zero Disk Usage):
        - Đối chiếu chữ ký (id, size, md5Checksum, modifiedTime) với Scan Cache: nếu không đổi -> trả kết quả 0ms.
        - Nếu có biến động (Cache Miss):
          + Đọc mục lục chapters.zip qua Range Request.
          + Đọc mục lục translated_chapters.zip qua Range Request.
          + Tìm các chương có trong chapters.zip nhưng chưa có trong translated_chapters.zip và cập nhật Cache.
        """
        story_id = story_info['story_id']
        czip = story_info['chapters_file']
        tzip = story_info['translated_chapters_file']

        czip_sig = self._build_file_sig(czip)
        tzip_sig = self._build_file_sig(tzip)

        # 0. Kiểm tra Scan Cache (nếu cả chapters.zip và translated_chapters.zip đều không biến động)
        if self.use_cache and story_id in self.scan_cache:
            cached = self.scan_cache[story_id]
            if cached.get('czip_sig') == czip_sig and cached.get('tzip_sig') == tzip_sig:
                self.cache_hits += 1
                raw_count = cached.get('raw_chapters_count', 0)

                if skip_stories_over and raw_count > skip_stories_over:
                    return {
                        'is_valid': False,
                        'is_too_long': True,
                        'raw_chapters_count': raw_count,
                        'reason': f"Tổng số chương raw ({raw_count}) vượt quá ngưỡng {skip_stories_over} chương"
                    }

                if not cached.get('is_valid', False):
                    return {
                        'is_valid': False,
                        'is_gap': cached.get('is_gap', False),
                        'reason': cached.get('reason', 'Không hợp lệ')
                    }

                first_new = cached.get('first_new')
                last_new = cached.get('last_new')
                new_chapters = (
                    list(range(first_new, last_new + 1))
                    if (first_new is not None and last_new is not None)
                    else []
                )
                return {
                    'is_valid': True,
                    'story_id': story_id,
                    'story_info': story_info,
                    'raw_chapters_count': raw_count,
                    'translated_chapters_count': cached.get('translated_chapters_count', 0),
                    'new_chapters': new_chapters,
                    'first_new': first_new,
                    'last_new': last_new
                }

        self.cache_misses += 1

        czip_size = int(czip.get('size', 0))
        tzip_size = int(tzip.get('size', 0))

        # 1. Đọc mục lục chapters.zip từ xa qua RAM
        raw_chaps = self.remote_inspector.get_chapters_map(czip['id'], czip_size, 'content.txt')
        if raw_chaps is None:
            return {'is_valid': False, 'reason': f'Lỗi kết nối khi đọc chapters.zip của {story_id}'}
        raw_nums = sorted(list(raw_chaps.keys()))

        # 1.5. Lọc bỏ qua các bộ truyện có tổng số chương raw vượt quá ngưỡng skip_stories_over
        if skip_stories_over and len(raw_nums) > skip_stories_over:
            return {
                'is_valid': False,
                'is_too_long': True,
                'raw_chapters_count': len(raw_nums),
                'reason': f"Tổng số chương raw ({len(raw_nums)}) vượt quá ngưỡng {skip_stories_over} chương"
            }

        # 2. Bắt buộc kiểm tra tính toàn vẹn và tuần tự trên TOÀN BỘ file raw (từ chương 1 đến hết)
        is_seq, seq_reason = self.check_sequential(raw_nums)
        if not is_seq:
            reason_str = f"Dải raw gốc bị lỗi toàn vẹn: {seq_reason} (tổng raw: {len(raw_nums)} chaps)"
            self._update_cache_entry(
                story_id=story_id,
                czip_sig=czip_sig,
                tzip_sig=tzip_sig,
                is_valid=False,
                is_gap=True,
                reason=reason_str,
                raw_count=len(raw_nums),
                trans_count=0
            )
            return {
                'is_valid': False,
                'is_gap': True,
                'reason': reason_str
            }

        # 3. Đọc mục lục translated_chapters.zip từ xa qua RAM
        trans_nums = set()
        if tzip and tzip_size > 100:
            trans_chaps = self.remote_inspector.get_chapters_map(tzip['id'], tzip_size, 'content_vi.txt')
            if trans_chaps is None:
                # BỊ LỖI KẾT NỐI KHI ĐỌC TRANSLATED_CHAPTERS.ZIP -> BẮT BUỘC BỎ QUA, KHÔNG ĐƯỢC COI LÀ 0 CHƯƠNG ĐỂ TRÁNH DỊCH ĐÈ!
                return {
                    'is_valid': False,
                    'reason': f'Lỗi mạng khi đọc translated_chapters.zip của {story_id}. Bỏ qua để tránh dịch đè dữ liệu!'
                }
            trans_nums = set(trans_chaps.keys())

        # 4. Tìm các chương chưa dịch (Diff)
        new_chapters = [num for num in raw_nums if num not in trans_nums]
        new_chapters.sort()

        if not new_chapters:
            self._update_cache_entry(
                story_id=story_id,
                czip_sig=czip_sig,
                tzip_sig=tzip_sig,
                is_valid=True,
                is_gap=False,
                reason="OK",
                raw_count=len(raw_nums),
                trans_count=len(trans_nums),
                first_new=None,
                last_new=None
            )
            return {
                'is_valid': True,
                'story_id': story_id,
                'story_info': story_info,
                'raw_chapters_count': len(raw_nums),
                'translated_chapters_count': len(trans_nums),
                'new_chapters': [],
                'first_new': None,
                'last_new': None
            }

        # 5. Kiểm tra tính toàn vẹn và liên tục (Data Integrity & Sequential Continuity)
        first_new = new_chapters[0]

        # 5.1. Nối tiếp chính xác với bản dịch cũ (Continuity with existing translation)
        if trans_nums:
            max_trans = max(trans_nums)
            if first_new != max_trans + 1:
                if first_new > max_trans + 1:
                    gap_msg = f"Đứt mạch dịch: Đã dịch đến chương {max_trans}, nhưng raw tiếp theo là chương {first_new} (khuyết chương {max_trans + 1}➔{first_new - 1})"
                else:
                    gap_msg = f"Bản dịch cũ bị khuyết: Đã dịch đến chương {max_trans}, nhưng phát hiện chương {first_new} chưa dịch (lỗ hổng dữ liệu)"
                self._update_cache_entry(
                    story_id=story_id,
                    czip_sig=czip_sig,
                    tzip_sig=tzip_sig,
                    is_valid=False,
                    is_gap=True,
                    reason=gap_msg,
                    raw_count=len(raw_nums),
                    trans_count=len(trans_nums)
                )
                return {
                    'is_valid': False,
                    'is_gap': True,
                    'reason': gap_msg
                }
        else:
            if first_new != 1:
                gap_msg = f"Chương raw bắt đầu từ chương {first_new}, không phải từ chương 1"
                self._update_cache_entry(
                    story_id=story_id,
                    czip_sig=czip_sig,
                    tzip_sig=tzip_sig,
                    is_valid=False,
                    is_gap=True,
                    reason=gap_msg,
                    raw_count=len(raw_nums),
                    trans_count=0
                )
                return {
                    'is_valid': False,
                    'is_gap': True,
                    'reason': gap_msg
                }

        # 5.2. Kiểm tra tính liên tục của dải chương mới (No gaps in new chapters)
        expected_new = list(range(first_new, first_new + len(new_chapters)))
        if new_chapters != expected_new:
            gap_msg = "Dải chương mới bị khuyết hoặc nhảy cóc"
            for act, exp in zip(new_chapters, expected_new):
                if act != exp:
                    gap_msg = f"Dải chương mới bị nhảy cóc: Mong đợi chương {exp} nhưng lại thấy chương {act}"
                    break
            self._update_cache_entry(
                story_id=story_id,
                czip_sig=czip_sig,
                tzip_sig=tzip_sig,
                is_valid=False,
                is_gap=True,
                reason=gap_msg,
                raw_count=len(raw_nums),
                trans_count=len(trans_nums)
            )
            return {
                'is_valid': False,
                'is_gap': True,
                'reason': gap_msg
            }

        last_new = new_chapters[-1]
        self._update_cache_entry(
            story_id=story_id,
            czip_sig=czip_sig,
            tzip_sig=tzip_sig,
            is_valid=True,
            is_gap=False,
            reason="OK",
            raw_count=len(raw_nums),
            trans_count=len(trans_nums),
            first_new=first_new,
            last_new=last_new
        )

        return {
            'is_valid': True,
            'story_id': story_id,
            'story_info': story_info,
            'raw_chapters_count': len(raw_nums),
            'translated_chapters_count': len(trans_nums),
            'new_chapters': new_chapters,
            'first_new': first_new,
            'last_new': last_new
        }

    def download_story_to_dir(self, story_info: Dict[str, Any], local_story_dir: Path) -> bool:
        """
        Chỉ tải toàn bộ file của bộ truyện về thư mục tạm khi truyện đó ĐƯỢC CHỌN VÀO HÀNG ĐỢI DỊCH:
        - Tải chapters.zip
        - Tải translated_chapters.zip
        - Tải info.json, summary.txt, glossary.json, checkpoints.json (nếu có)
        """
        local_story_dir.mkdir(parents=True, exist_ok=True)
        story_id = story_info['story_id']

        print(f"📥 [{story_id}] Đang tải dữ liệu bộ truyện về thư mục tạm...")

        # 1. Tải chapters.zip
        if not self.download_file_to_path(story_info['chapters_file']['id'], local_story_dir / "chapters.zip"):
            return False

        # 2. Tải translated_chapters.zip
        if not self.download_file_to_path(story_info['translated_chapters_file']['id'], local_story_dir / "translated_chapters.zip"):
            return False

        # 3. Tải các file metadata từ Drive nếu có
        files_meta = story_info.get('files_meta', {})
        for meta_name in ['info.json', 'glossary.json', 'summary.txt', 'checkpoints.json']:
            if meta_name in files_meta:
                self.download_file_to_path(files_meta[meta_name]['id'], local_story_dir / meta_name)

        # 4. Khởi tạo file rỗng nếu trên Drive chưa có sẵn để tránh lỗi IO
        glossary_file = local_story_dir / "glossary.json"
        if not glossary_file.exists():
            glossary_file.write_text("{}", encoding='utf-8')

        summary_file = local_story_dir / "summary.txt"
        if not summary_file.exists():
            summary_file.write_text("", encoding='utf-8')

        return True

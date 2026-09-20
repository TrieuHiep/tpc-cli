"""
Module kiểm tra tính tuần tự và đối chiếu diff chương tồn đọng từ xa qua RAM.
Chỉ tải file về ổ cứng khi truyện đó thực sự được chọn vào mẻ dịch (Zero disk usage khi quét).
"""
import re
import json
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from googleapiclient.http import MediaIoBaseDownload

from auto_translator_daemon.remote_zip_inspector import RemoteZipInspector

class ChapterInspector:
    """Thẩm định mục lục ZIP từ xa qua RAM và tải truyện về thư mục làm việc khi cần dịch."""

    def __init__(self, gdrive_service):
        self.gdrive_service = gdrive_service
        self.service = self.gdrive_service.service
        
        # Khởi tạo RemoteZipInspector với token OAuth
        creds = self.service._http.credentials
        if not creds.valid:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        self.remote_inspector = RemoteZipInspector(auth_token=creds.token)

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

    def inspect_story_remotely(self, story_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Thẩm định diff chương hoàn toàn từ xa qua RAM (Zero Disk Usage):
        - Đọc mục lục chapters.zip qua Range Request.
        - Đọc mục lục translated_chapters.zip qua Range Request.
        - Tìm các chương có trong chapters.zip nhưng chưa có trong translated_chapters.zip.
        """
        story_id = story_info['story_id']
        czip = story_info['chapters_file']
        tzip = story_info['translated_chapters_file']

        czip_size = int(czip.get('size', 0))
        tzip_size = int(tzip.get('size', 0))

        # 1. Đọc mục lục chapters.zip từ xa qua RAM
        raw_chaps = self.remote_inspector.get_chapters_map(czip['id'], czip_size, 'content.txt')
        if raw_chaps is None:
            return {'is_valid': False, 'reason': f'Lỗi kết nối khi đọc chapters.zip của {story_id}'}
        raw_nums = sorted(list(raw_chaps.keys()))

        if not raw_nums:
            return {'is_valid': False, 'reason': 'Không đọc được danh sách chương trong chapters.zip'}

        # 2. Đã bỏ qua kiểm tra tuần tự (check_sequential) vì biên tập viên đã đối chiếu và lọc trên Google Sheet Whitelist

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
                return {
                    'is_valid': False,
                    'is_gap': True,
                    'reason': gap_msg
                }
        else:
            if first_new != 1:
                return {
                    'is_valid': False,
                    'is_gap': True,
                    'reason': f"Chương raw bắt đầu từ chương {first_new}, không phải từ chương 1"
                }

        # 5.2. Kiểm tra tính liên tục của dải chương mới (No gaps in new chapters)
        expected_new = list(range(first_new, first_new + len(new_chapters)))
        if new_chapters != expected_new:
            for act, exp in zip(new_chapters, expected_new):
                if act != exp:
                    return {
                        'is_valid': False,
                        'is_gap': True,
                        'reason': f"Dải chương mới bị nhảy cóc: Mong đợi chương {exp} nhưng lại thấy chương {act}"
                    }
            return {
                'is_valid': False,
                'is_gap': True,
                'reason': "Dải chương mới bị khuyết hoặc nhảy cóc"
            }

        return {
            'is_valid': True,
            'story_id': story_id,
            'story_info': story_info,
            'raw_chapters_count': len(raw_nums),
            'translated_chapters_count': len(trans_nums),
            'new_chapters': new_chapters,
            'first_new': first_new,
            'last_new': new_chapters[-1]
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

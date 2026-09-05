"""
Module đọc mục lục file ZIP từ xa qua bộ nhớ RAM bằng HTTP Range Request.
Hoạt động theo cơ chế Single Request (chỉ đọc 1MB cuối cùng của file qua RAM, 0 byte ghi xuống ổ cứng).
"""
import re
import io
import time
import struct
import urllib.request
from typing import List, Dict, Optional, Tuple

class RemoteZipInspector:
    """Đọc và giải mã mục lục file ZIP trực tiếp từ Google Drive mà không cần tải file về ổ cứng."""

    def __init__(self, auth_token: str, buffer_size: int = 1048576):
        # Mặc định đọc 1MB (1048576 bytes) cuối file zip, đủ chứa mục lục tới hơn 14.000 chương
        self.auth_token = auth_token
        self.buffer_size = buffer_size

    def get_filenames_in_zip(self, file_id: str, file_size: int) -> Optional[List[str]]:
        """
        Gửi 1 HTTP Range Request lấy đoạn đuôi của file zip trên Google Drive,
        tìm thẻ EOCD và giải mã danh sách tên file trong Central Directory trên RAM.
        Trả về None nếu lỗi mạng/timeout (sau 3 lần thử lại).
        """
        if file_size <= 0:
            return []

        tail_size = min(self.buffer_size, file_size)
        start_byte = file_size - tail_size

        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        headers = {
            'Authorization': f"Bearer {self.auth_token}",
            'Range': f"bytes={start_byte}-{file_size - 1}"
        }

        req = urllib.request.Request(url, headers=headers)
        data = None
        last_err = None

        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                break
            except Exception as e:
                last_err = e
                if attempt < 3:
                    time.sleep(1.5 * attempt)

        if data is None:
            print(f"⚠️ Lỗi kết nối đọc Range Request cho file {file_id} (thử lại 3 lần thất bại): {last_err}")
            return None

        # 1. Tìm thẻ End of Central Directory (EOCD): chữ ký PK\x05\x06
        eocd_idx = data.rfind(b'PK\x05\x06')
        if eocd_idx == -1:
            return []

        # 2. Đọc thông tin EOCD
        try:
            total_entries = struct.unpack_from('<H', data, eocd_idx + 10)[0]
            cd_size = struct.unpack_from('<I', data, eocd_idx + 12)[0]
            cd_offset = struct.unpack_from('<I', data, eocd_idx + 16)[0]
        except Exception:
            return []

        # 3. Trích xuất buffer chứa Central Directory
        cd_start_in_buf = cd_offset - start_byte
        cd_data = None

        if cd_start_in_buf >= 0 and cd_start_in_buf + cd_size <= len(data):
            cd_data = data[cd_start_in_buf : cd_start_in_buf + cd_size]
        else:
            # Fallback nếu truyện cực kỳ dài (> 15.000 chương): đọc đúng dải byte mục lục
            cd_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            cd_req = urllib.request.Request(cd_url, headers={
                'Authorization': f"Bearer {self.auth_token}",
                'Range': f"bytes={cd_offset}-{cd_offset + cd_size - 1}"
            })
            for attempt in range(1, 4):
                try:
                    with urllib.request.urlopen(cd_req, timeout=30) as resp:
                        cd_data = resp.read()
                    break
                except Exception as e:
                    last_err = e
                    if attempt < 3:
                        time.sleep(1.5 * attempt)

            if cd_data is None:
                print(f"⚠️ Lỗi đọc Central Directory Range Request cho file {file_id}: {last_err}")
                return None

        # 4. Lần lượt duyệt từng File Header trong Central Directory
        filenames = []
        pos = 0
        while pos < len(cd_data):
            if cd_data[pos:pos+4] != b'PK\x01\x02':
                break

            fname_len = struct.unpack_from('<H', cd_data, pos + 28)[0]
            extra_len = struct.unpack_from('<H', cd_data, pos + 30)[0]
            comment_len = struct.unpack_from('<H', cd_data, pos + 32)[0]

            fname_bytes = cd_data[pos + 46 : pos + 46 + fname_len]
            try:
                fname = fname_bytes.decode('utf-8')
            except Exception:
                fname = fname_bytes.decode('cp437', errors='ignore')

            filenames.append(fname)
            pos += 46 + fname_len + extra_len + comment_len

        return filenames

    @staticmethod
    def extract_chapter_number(entry_path: str) -> Optional[int]:
        """Trích xuất số chương từ đường dẫn file trong zip."""
        parts = entry_path.replace('\\', '/').split('/')
        for part in parts:
            if part.endswith('.txt') or part.endswith('.json'):
                continue
            nums = re.findall(r'\d+', part)
            if nums:
                return int(nums[0])
        return None

    def get_chapters_map(self, file_id: str, file_size: int, target_filename: str) -> Optional[Dict[int, str]]:
        """
        Đọc mục lục từ xa và trả về dict: {chapter_number: entry_path}
        chỉ chứa các file có tên target_filename (ví dụ: 'content.txt' hoặc 'content_vi.txt').
        Trả về None nếu xảy ra lỗi kết nối mạng (tránh hiểu lầm là 0 chương).
        """
        filenames = self.get_filenames_in_zip(file_id, file_size)
        if filenames is None:
            return None

        chapter_map = {}
        for name in filenames:
            if name.endswith('/' + target_filename) or name == target_filename or name.endswith(target_filename):
                chap_num = self.extract_chapter_number(name)
                if chap_num is not None:
                    chapter_map[chap_num] = name
        return chapter_map

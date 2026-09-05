"""
Module quản lý danh sách truyện được phép dịch (Whitelist) từ Google Sheet.
Chỉ những truyện nằm trong danh sách này (theo từng nguồn và từng mã ID) mới được quét và tải về.
"""
import csv
import json
import io
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from auto_translator_daemon.config import STORAGE_DIR

# Danh sách URL xuất CSV của từng Tab tương ứng với từng nguồn
WHITELIST_TABS = {
    "truyendichwiki": "https://docs.google.com/spreadsheets/d/1SDAZTNhL9gEr37JCNV8GIvNwFXNK8yXvAPJ-4lPp-QY/export?format=csv&gid=428851671",
    "novel543": "https://docs.google.com/spreadsheets/d/1SDAZTNhL9gEr37JCNV8GIvNwFXNK8yXvAPJ-4lPp-QY/export?format=csv&gid=2049787905"
}

class WhitelistManager:
    """Tải và đối chiếu danh sách Whitelist truyện từ cả 2 tab Google Sheet."""

    def __init__(self, tab_urls: Optional[Dict[str, str]] = None):
        self.tab_urls = tab_urls or WHITELIST_TABS
        self.cache_file = STORAGE_DIR / "whitelist_cache.json"
        self.whitelist: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.load_whitelist()

    @staticmethod
    def normalize_source(source_str: str) -> str:
        """Chuẩn hóa tên nguồn về định dạng chuẩn (truyendichwiki hoặc novel543)."""
        s = source_str.strip().lower()
        if "truyendichwiki" in s or "truyenwiki" in s:
            return "truyendichwiki"
        if "novel543" in s:
            return "novel543"
        return s

    def fetch_from_google_sheet(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Tải dữ liệu CSV từ tất cả các Tab trong Google Sheet."""
        whitelist = {}

        for default_source, url in self.tab_urls.items():
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read().decode('utf-8')

                reader = csv.DictReader(io.StringIO(data))
                tab_count = 0

                for row in reader:
                    raw_source = row.get('Nguồn', '') or default_source
                    source = self.normalize_source(raw_source)
                    story_id = row.get('ID Truyện', '').strip()
                    title = row.get('Tên Truyện', '').strip()
                    folder_id = row.get('Folder ID', '').strip()
                    chap_count = row.get('Số Chapter', '').strip()

                    if source and story_id:
                        whitelist[(source, story_id)] = {
                            'source': source,
                            'story_id': story_id,
                            'title': title,
                            'folder_id': folder_id,
                            'total_chapters': int(chap_count) if chap_count.isdigit() else 0
                        }
                        tab_count += 1

                print(f"   📑 Tab [{default_source}]: Đã nạp {tab_count} bộ truyện.")

            except Exception as e:
                print(f"⚠️ Lỗi tải tab [{default_source}]: {e}")

        return whitelist

        return whitelist

    def load_whitelist(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Nạp danh sách whitelist, có fallback nạp từ cache cục bộ nếu không có mạng."""
        try:
            print("📑 Đang đồng bộ danh sách Whitelist từ Google Sheet...")
            self.whitelist = self.fetch_from_google_sheet()
            print(f"✅ Đã nạp thành công {len(self.whitelist)} bộ truyện được duyệt từ Google Sheet.")

            # Lưu cache cục bộ
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            serializable = {f"{k[0]}:{k[1]}": v for k, v in self.whitelist.items()}
            self.cache_file.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding='utf-8')

        except Exception as e:
            print(f"⚠️ Không thể tải Whitelist trực tiếp từ Google Sheet ({e}). Đang kiểm tra cache cục bộ...")
            if self.cache_file.exists():
                try:
                    data = json.loads(self.cache_file.read_text(encoding='utf-8'))
                    self.whitelist = {}
                    for k_str, v in data.items():
                        parts = k_str.split(':', 1)
                        if len(parts) == 2:
                            self.whitelist[(parts[0], parts[1])] = v
                    print(f"✅ Đã phục hồi {len(self.whitelist)} bộ truyện từ cache cục bộ.")
                except Exception as ex:
                    print(f"❌ Không thể đọc cache Whitelist: {ex}")
            else:
                print("❌ Không tìm thấy cache Whitelist cục bộ!")

        return self.whitelist

    def is_whitelisted(self, source: str, story_id: str) -> bool:
        """Kiểm tra một bộ truyện có nằm trong danh sách được phép tải/dịch hay không."""
        norm_source = self.normalize_source(source)
        return (norm_source, story_id.strip()) in self.whitelist

    def get_story_info(self, source: str, story_id: str) -> Optional[Dict[str, Any]]:
        """Lấy metadata đã được duyệt của truyện từ Whitelist."""
        norm_source = self.normalize_source(source)
        return self.whitelist.get((norm_source, story_id.strip()))

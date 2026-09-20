"""
Module hậu kiểm chất lượng (QC) bản dịch truyện mới:
1. Quét sạch 100% chữ Hán / ký tự Trung Quốc.
2. Quét sạch 100% các thẻ HTML (<p>, </p>, <br>...).
3. Kiểm tra tỷ lệ dung lượng chống cắt gọt / tóm tắt so với bản gốc.
"""
import re
from pathlib import Path
from typing import Tuple, Dict, Any, List
from new_story_translator_daemon.config import MIN_TRANSLATION_RATIO, MIN_TRANSLATION_WORDS

class QCValidator:
    """Kiểm duyệt chất lượng bản dịch độc lập trước khi upload lên Drive."""

    def __init__(self, min_ratio: float = MIN_TRANSLATION_RATIO, min_words: int = MIN_TRANSLATION_WORDS):
        self.min_ratio = min_ratio
        self.min_words = min_words
        # Pattern phát hiện chữ Hán (CJK Unified Ideographs)
        self.hanzi_pattern = re.compile(r'[\u4e00-\u9fff]')
        # Pattern phát hiện thẻ HTML thường gặp
        self.html_pattern = re.compile(r'<\/?(?:p|br|div|span|h\d)[^>]*>', re.IGNORECASE)

    def validate_content(self, raw_text: str, vi_text: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Thẩm định 1 chương truyện:
        Trả về: (is_passed: bool, message: str, stats: dict)
        """
        raw_clean = raw_text.strip()
        vi_clean = vi_text.strip()

        raw_len = len(raw_clean)
        vi_len = len(vi_clean)
        vi_words = len(vi_clean.split())
        ratio = vi_len / max(raw_len, 1)

        stats = {
            'raw_length': raw_len,
            'vi_length': vi_len,
            'vi_words': vi_words,
            'length_ratio': round(ratio, 3)
        }

        # 1. Kiểm tra rỗng
        if not vi_clean:
            return False, "Bản dịch rỗng hoặc không có nội dung", stats

        # 2. Kiểm tra chữ Hán
        hanzi_matches = self.hanzi_pattern.findall(vi_clean)
        if hanzi_matches:
            sample = "".join(hanzi_matches[:10])
            return False, f"Bản dịch còn sót {len(hanzi_matches)} chữ Hán (Mẫu: '{sample}')", stats

        # 3. Kiểm tra thẻ HTML
        html_matches = self.html_pattern.findall(vi_clean)
        if html_matches:
            sample = ", ".join(html_matches[:5])
            return False, f"Bản dịch chứa thẻ HTML không hợp lệ (Mẫu: '{sample}')", stats

        # 4. Kiểm tra cắt gọt / tóm tắt theo tỷ lệ ký tự (Anti-truncation)
        if ratio < self.min_ratio:
            return False, f"Nội dung bị cắt gọt / tóm tắt: Tỉ lệ ký tự Vi/Zh = {ratio:.2f} < {self.min_ratio}", stats

        # 5. Kiểm tra số lượng từ tối thiểu (chống tóm tắt cực đoan khi raw dài)
        if raw_len >= 1000 and vi_words < self.min_words:
            return False, f"Nội dung bị tóm tắt: Số từ tiếng Việt = {vi_words} < {self.min_words} từ", stats

        return True, "PASSED ✅", stats

    def validate_directory_chapters(self, chapters_dir: str, chapter_nums: List[int]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Kiểm tra toàn bộ danh sách chương trong thư mục chapters cục bộ:
        Đọc raw content.txt và bản dịch content_vi.txt.
        """
        base_path = Path(chapters_dir)
        results = []
        all_passed = True

        for chap_num in chapter_nums:
            chap_folder = base_path / f"chap_{chap_num}"
            if not chap_folder.exists():
                chap_folder = base_path / str(chap_num)

            raw_file = chap_folder / "content.txt"
            vi_file = chap_folder / "content_vi.txt"

            if not vi_file.exists():
                all_passed = False
                results.append({
                    'chapter': chap_num,
                    'passed': False,
                    'reason': f"Không tìm thấy file kết quả {vi_file}",
                    'stats': {}
                })
                continue

            raw_text = raw_file.read_text(encoding='utf-8', errors='ignore') if raw_file.exists() else ""
            vi_text = vi_file.read_text(encoding='utf-8', errors='ignore')

            passed, reason, stats = self.validate_content(raw_text, vi_text)
            if not passed:
                all_passed = False

            results.append({
                'chapter': chap_num,
                'passed': passed,
                'reason': reason,
                'stats': stats
            })

        return all_passed, results

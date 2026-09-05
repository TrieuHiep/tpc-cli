import json
import re
from pathlib import Path
from typing import Dict, Any, List

from app.utils.logger import logger

class GlossaryService:
    """Service managing glossary.json and summary.txt context state."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.glossary_path = data_dir / "glossary.json"
        self.summary_path = data_dir / "summary.txt"

    def load_glossary(self) -> Dict[str, str]:
        """Loads glossary dictionary from data/glossary.json."""
        if not self.glossary_path.exists():
            return {}
        try:
            with open(self.glossary_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc glossary.json: {e}")
            return {}

    def filter_glossary_for_text(self, text: str, max_terms: int = 0) -> Dict[str, str]:
        """Filters relevant terms appearing in raw text, supporting both Chinese raw text and Vietnamese Convert raw text."""
        full_glossary = self.load_glossary()
        matched = {}
        
        # Sắp xếp các thuật ngữ theo độ dài giảm dần (ưu tiên match từ dài trước từ ngắn)
        sorted_terms = sorted(full_glossary.items(), key=lambda x: max(len(x[0]), len(x[1])), reverse=True)
        text_lower = text.lower()
        
        for term_key, term_vi in sorted_terms:
            # 1. Khớp nguyên bản tiếng Trung hoặc tiếng Anh/Latin
            if term_key in text:
                matched[term_key] = term_vi
            # 2. Khớp theo tiếng Việt / Hán Việt / Convert (không phân biệt hoa thường)
            elif (term_key and term_key.lower() in text_lower) or (term_vi and term_vi.lower() in text_lower):
                matched[term_key] = term_vi
            
            if max_terms > 0 and len(matched) >= max_terms:
                break
        return matched

    def update_glossary(self, new_terms: Dict[str, str]):
        """Merges new extracted terms into glossary.json."""
        if not new_terms:
            return
        
        current_glossary = self.load_glossary()
        updated_count = 0
        for zh, vi in new_terms.items():
            zh_clean = zh.strip()
            vi_clean = vi.strip()
            if zh_clean and vi_clean and zh_clean not in current_glossary:
                current_glossary[zh_clean] = vi_clean
                updated_count += 1
                
        if updated_count > 0:
            with open(self.glossary_path, "w", encoding="utf-8") as f:
                json.dump(current_glossary, f, ensure_ascii=False, indent=2)
            logger.info(f"Đã cập nhật thêm [cyan]{updated_count}[/cyan] thuật ngữ mới vào glossary.json")

    def load_summary(self, last_n: int = 15, before_chapter: int = None) -> str:
        """Loads story summary log from data/summary.txt (sliding window of last_n chapters, optionally strictly before before_chapter)."""
        if not self.summary_path.exists():
            return ""
        try:
            with open(self.summary_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            if not lines:
                return ""

            # Nếu chỉ định before_chapter: Lọc chỉ lấy các tóm tắt diễn ra TRƯỚC chương đó
            if before_chapter is not None:
                filtered_lines = []
                for line in lines:
                    match = re.match(r"^(?:Chương|Chapter)\s*(\d+)", line, re.IGNORECASE)
                    if match:
                        chap_idx = int(match.group(1))
                        if chap_idx < before_chapter:
                            filtered_lines.append(line)
                    else:
                        filtered_lines.append(line)
                lines = filtered_lines

            if not lines:
                return ""
            if last_n > 0:
                lines = lines[-last_n:]
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Lỗi đọc summary.txt: {e}")
            return ""

    def append_summary(self, chapter_num: int, chapter_summary: str):
        """Appends or updates chapter summary in data/summary.txt maintaining sorted numerical order."""
        if not chapter_summary:
            return
            
        summary_line = f"Chương {chapter_num}: {chapter_summary.strip()}"
        
        lines = []
        if self.summary_path.exists():
            try:
                with open(self.summary_path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
            except Exception:
                lines = []

        # Kiểm tra xem Chương này đã có dòng tóm tắt trong file chưa
        found_idx = -1
        for idx, line in enumerate(lines):
            match = re.match(r"^(?:Chương|Chapter)\s*(\d+)", line, re.IGNORECASE)
            if match and int(match.group(1)) == chapter_num:
                found_idx = idx
                break

        if found_idx >= 0:
            lines[found_idx] = summary_line
        else:
            # Chèn vào đúng vị trí số thứ tự chương tăng dần
            inserted = False
            for idx, line in enumerate(lines):
                match = re.match(r"^(?:Chương|Chapter)\s*(\d+)", line, re.IGNORECASE)
                if match and int(match.group(1)) > chapter_num:
                    lines.insert(idx, summary_line)
                    inserted = True
                    break
            if not inserted:
                lines.append(summary_line)

        try:
            with open(self.summary_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            logger.info(f"Đã cập nhật tóm tắt Chương {chapter_num} vào summary.txt")
        except Exception as e:
            logger.error(f"Lỗi ghi summary.txt: {e}")


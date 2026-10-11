"""
Module hậu kiểm chất lượng (QC) bản dịch:
1. Quét sạch 100% chữ Hán / ký tự Trung Quốc.
2. Quét sạch 100% các thẻ HTML (<p>, </p>, <br>...).
3. Kiểm tra tỷ lệ dung lượng chống cắt gọt / tóm tắt so với bản gốc.
"""
import re
import hashlib
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional, Union
from auto_translator_daemon.config import MIN_TRANSLATION_RATIO, MIN_TRANSLATION_WORDS

def compute_file_sha256(file_path: Union[str, Path]) -> str:
    """Tính mã băm SHA-256 của file nhị phân (an toàn bộ nhớ bằng chunk 64KB)."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

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
        import os
        from pathlib import Path

        base_path = Path(chapters_dir)
        results = []
        all_passed = True

        for chap_num in chapter_nums:
            # Thử các format tên thư mục chương: chap_12, 12...
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

    def create_chapters_snapshot(self, story_dir: Union[str, Path]) -> Dict[str, str]:
        """
        Quét toàn bộ thư mục chapters/ và tính mã băm SHA-256 cho tất cả các file content_vi.txt hiện có.
        Trả về dict: { "chapters/.../content_vi.txt": "sha256_hex", ... }
        """
        story_path = Path(story_dir)
        chapters_dir = story_path / "chapters"
        if not chapters_dir.exists():
            return {}

        snapshot: Dict[str, str] = {}
        for vi_file in chapters_dir.rglob("content_vi.txt"):
            if vi_file.is_file() and vi_file.stat().st_size > 0:
                rel_path = str(vi_file.relative_to(story_path)).replace('\\', '/')
                snapshot[rel_path] = compute_file_sha256(vi_file)
        return snapshot

    def validate_total_chapters_integrity(
        self,
        chapters_dir,
        initial_count: int,
        new_chaps_count: int,
        initial_files: Optional[Any] = None,
        initial_snapshot: Optional[Dict[str, str]] = None,
        story_dir = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Kiểm tra tổng số lượng luỹ tiến và tính bất biến (Total Chapters & Immutability Integrity Check):
        1. Kiểm tra 100% các file chương cũ (S_old) không bị xóa hoặc làm rỗng.
        2. Nếu có snapshot mã băm SHA-256, kiểm tra tính bất biến (không bị LLM sửa đổi nội dung dù chỉ 1 ký tự).
        3. Đối chiếu số lượng: tổng file content_vi.txt = Số chương cũ (S_old) + Số chương mới giao dịch (|chaps|).

        Trả về: (is_passed: bool, reason: str, stats: dict)
        """
        c_dir = Path(chapters_dir)
        actual_files = [
            f for f in c_dir.rglob("content_vi.txt")
            if f.is_file() and f.stat().st_size > 0
        ]
        actual_count = len(actual_files)
        expected_count = initial_count + new_chaps_count

        stats = {
            'initial_old_count': initial_count,
            'new_chaps_count': new_chaps_count,
            'expected_total': expected_count,
            'actual_total': actual_count
        }

        # Xác định nguồn snapshot mã băm hoặc danh sách file cũ
        snapshot_to_check = initial_snapshot if initial_snapshot is not None else (initial_files if isinstance(initial_files, dict) else None)
        files_to_check = snapshot_to_check.keys() if snapshot_to_check is not None else (initial_files or [])

        # 1. Kiểm tra sự tồn tại và tính bất biến của các file chương cũ
        if files_to_check and story_dir:
            s_dir = Path(story_dir)
            missing_old = []
            modified_old = []

            for rel_path in files_to_check:
                full_path = s_dir / rel_path
                if not full_path.exists() or full_path.stat().st_size == 0:
                    missing_old.append(str(rel_path).replace('\\', '/'))
                    continue

                # Kiểm tra mã băm SHA-256 nếu có snapshot
                if snapshot_to_check and rel_path in snapshot_to_check:
                    expected_hash = snapshot_to_check[rel_path]
                    actual_hash = compute_file_sha256(full_path)
                    if actual_hash != expected_hash:
                        modified_old.append(
                            f"{str(rel_path).replace('\\', '/')} (Hash cũ: {expected_hash[:8]}... ➔ Mới: {actual_hash[:8]}...)"
                        )

            if missing_old:
                sample_missing = ", ".join(missing_old[:5])
                reason = f"Phát hiện {len(missing_old)} file chương cũ đã bị mất hoặc rỗng (Mẫu: {sample_missing})"
                return False, reason, stats

            if modified_old:
                sample_modified = "; ".join(modified_old[:3])
                reason = f"Phát hiện {len(modified_old)} file chương cũ đã bị sửa đổi trái phép (Mẫu: {sample_modified})"
                return False, reason, stats

        # 2. Đối chiếu số lượng: tổng file content_vi.txt == S_old + |chaps|
        if actual_count != expected_count:
            reason = (
                f"Tổng số file content_vi.txt không khớp: Thực tế có {actual_count} file, "
                f"kỳ vọng {expected_count} file ({initial_count} cũ + {new_chaps_count} mới)!"
            )
            return False, reason, stats

        return True, f"PASSED ✅ (Khớp chính xác {actual_count}/{expected_count} file, 100% chương cũ nguyên vẹn)", stats


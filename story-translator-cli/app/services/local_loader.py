import os
import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from app.utils.logger import logger

DERIVED_FILES_TO_PURGE = [
    "translated_chapters.zip",
    "checkpoints.json",
    "summary.txt",
    "glossary.json",
    "manual_audit_report.json",
    "manual_audit_report.txt",
    "translation.log"
]

class LocalLoaderService:
    """Service responsible for loading novel metadata from info.json and raw chapters from local files."""

    def __init__(self, dataset_path: str, retranslate: bool = False):
        self.dataset_dir = Path(dataset_path).resolve()
        self.info_path = self.dataset_dir / "info.json"
        self.chapters_dir = self.dataset_dir / "chapters"
        self.zip_path = self.dataset_dir / "chapters.zip"
        self.translated_zip_path = self.dataset_dir / "translated_chapters.zip"
        self.retranslate = retranslate

        if not self.dataset_dir.exists():
            raise FileNotFoundError(f"Không tìm thấy thư mục dataset: {self.dataset_dir}")

        if self.retranslate:
            logger.warning(f"🔄 [Retranslate Mode] Phát hiện cờ --retranslate. Tiến hành dọn sạch toàn bộ bản dịch và dữ liệu phái sinh cũ...")
            self.purge_all_derived_files()
            self.auto_extract_zip()
        else:
            # Tự động giải nén chapters.zip và translated_chapters.zip nếu tồn tại ở mỗi lần khởi tạo
            self.auto_extract_zip()
            self.auto_extract_translated_zip()

    def purge_all_derived_files(self):
        """Purges all derived files and extracted chapters folder for a clean retranslation from scratch."""
        # 1. Xóa các file phái sinh
        for fname in DERIVED_FILES_TO_PURGE:
            fpath = self.dataset_dir / fname
            if fpath.exists():
                try:
                    fpath.unlink()
                    logger.info(f"   🗑️ Đã xóa file cũ: [dim]{fname}[/dim]")
                except Exception as e:
                    logger.warning(f"Không thể xóa file {fname}: {e}")

        # 2. Xóa thư mục chapters giải nén cũ nếu có
        if self.chapters_dir.exists():
            try:
                shutil.rmtree(self.chapters_dir)
                logger.info(f"   🗑️ Đã dọn dẹp thư mục chapters/ cũ.")
            except Exception as e:
                logger.warning(f"Không thể xóa thư mục chapters: {e}")

    def auto_extract_zip(self):
        """Auto extracts chapters.zip into dataset_dir / chapters/ with smart path detection."""
        if not self.zip_path.exists():
            return

        # Nếu thư mục chapters đã tồn tại và có chứa nội dung thì không cần giải nén lại
        if self.chapters_dir.exists() and any(self.chapters_dir.iterdir()):
            return

        try:
            logger.info(f"📦 Phát hiện file [cyan]chapters.zip[/cyan] -> Tiến hành tự động giải nén...")
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                names = zip_ref.namelist()
                has_chapters_prefix = any(n.startswith("chapters/") for n in names)
                
                if has_chapters_prefix:
                    zip_ref.extractall(self.dataset_dir)
                else:
                    self.chapters_dir.mkdir(parents=True, exist_ok=True)
                    zip_ref.extractall(self.chapters_dir)

            logger.info("✅ Giải nén [cyan]chapters.zip[/cyan] thành công.")
        except Exception as e:
            logger.error(f"❌ Lỗi khi giải nén chapters.zip: {e}")

    def auto_extract_translated_zip(self):
        """Auto extracts translated_chapters.zip if present to restore previous translated chapters."""
        if not self.translated_zip_path.exists():
            return

        try:
            logger.info(f"📦 Phát hiện file [cyan]translated_chapters.zip[/cyan] -> Tiến hành tự động khôi phục bản dịch...")
            with zipfile.ZipFile(self.translated_zip_path, 'r') as zip_ref:
                names = zip_ref.namelist()
                has_chapters_prefix = any(n.startswith("chapters/") for n in names)
                
                if has_chapters_prefix:
                    zip_ref.extractall(self.dataset_dir)
                else:
                    self.chapters_dir.mkdir(parents=True, exist_ok=True)
                    zip_ref.extractall(self.chapters_dir)

            logger.info("✅ Khôi phục bản dịch từ [cyan]translated_chapters.zip[/cyan] thành công.")
        except Exception as e:
            logger.error(f"❌ Lỗi khi khôi phục translated_chapters.zip: {e}")

    def cleanup_extracted_chapters(self):
        """Safely removes extracted chapters/ folder after translation & zip archiving to keep disk clean."""
        if self.chapters_dir.exists():
            try:
                shutil.rmtree(self.chapters_dir)
                logger.info(f"🧹 [Auto-Cleanup] Đã dọn dẹp sạch sẽ thư mục giải nén [cyan]chapters/[/cyan] sau khi đóng gói.")
            except Exception as e:
                logger.warning(f"⚠️ Không thể dọn dẹp thư mục chapters/: {e}")

    def load_info(self) -> Dict[str, Any]:
        """Loads novel metadata from info.json."""
        if not self.info_path.exists():
            logger.warning(f"Không tìm thấy file info.json tại {self.info_path}, sử dụng metadata mặc định.")
            return {
                "title": self.dataset_dir.name,
                "author": "Chưa rõ",
                "description": ""
            }

        with open(self.info_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def is_chapter_translated(self, chapter_dir: Path) -> bool:
        """Checks if content_vi.txt exists in chapter directory."""
        return (chapter_dir / "content_vi.txt").exists()

    def get_available_chapters(self) -> List[Tuple[int, Path]]:
        """Returns sorted list of (chapter_num, chapter_dir_path)."""
        if not self.chapters_dir.exists():
            raise FileNotFoundError(f"Không tìm thấy thư mục chapters tại {self.chapters_dir}")

        chapters = []
        for entry in os.listdir(self.chapters_dir):
            full_path = self.chapters_dir / entry
            if full_path.is_dir() and entry.isdigit():
                chapters.append((int(entry), full_path))

        chapters.sort(key=lambda x: x[0])
        return chapters

    def load_raw_chapter_content(self, chapter_dir: Path) -> str:
        """Reads raw chapter text from content.txt inside chapter directory."""
        content_path = chapter_dir / "content.txt"
        if not content_path.exists():
            raise FileNotFoundError(f"Không tìm thấy content.txt tại {content_path}")

        with open(content_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def save_translated_chapter(self, chapter_dir: Path, content_vi: str):
        """Saves final translated plain text to content_vi.txt."""
        out_path = chapter_dir / "content_vi.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content_vi.strip() + "\n")
        logger.info(f"Đã lưu bản dịch thành công: [green]{out_path}[/green]")

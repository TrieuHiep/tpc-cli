"""
Module đóng gói lại file translated_chapters.zip và đồng bộ ngược lên Google Drive bằng update (ghi đè file ID cũ).
"""
import json
import zipfile
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from auto_translator_daemon.config import VAULT_DRIVE_FOLDERS

class DriveSyncer:
    """Đóng gói và đồng bộ kết quả dịch lên Google Drive riêng (tpc-dw)."""

    def __init__(self, gdrive_service):
        self.gdrive_service = gdrive_service
        self._local = threading.local()

    def _set_last_error(self, msg: Optional[str]):
        self._local.last_error = msg

    def get_last_error(self) -> str:
        return getattr(self._local, "last_error", "") or ""

    def repack_translated_chapters(self, story_dir: Path, expected_total_chapters: Optional[int] = None) -> Optional[Path]:
        """
        Quét toàn bộ thư mục chapters/ và đóng gói tất cả các chương có content_vi.txt
        (bao gồm cả content_vi.txt và bản gốc content.txt) vào translated_chapters.zip.
        Nếu truyền expected_total_chapters, sẽ từ chối đóng gói nếu số lượng file không khớp chính xác.
        """
        chapters_dir = story_dir / "chapters"
        if not chapters_dir.exists():
            print(f"⚠️ Thư mục chapters không tồn tại trong {story_dir}")
            return None

        output_zip = story_dir / "translated_chapters.zip"
        temp_zip = story_dir / "translated_chapters_new.zip"

        count = 0
        try:
            with zipfile.ZipFile(temp_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                # Quét đệ quy tất cả file content_vi.txt để xác định các chương đã dịch
                for vi_file in chapters_dir.rglob("content_vi.txt"):
                    rel_vi = vi_file.relative_to(story_dir)
                    zf.write(vi_file, arcname=str(rel_vi).replace('\\', '/'))
                    count += 1

                    # Kẹp thêm file bản gốc content.txt cùng thư mục chương nếu có
                    raw_file = vi_file.parent / "content.txt"
                    if raw_file.exists():
                        rel_raw = raw_file.relative_to(story_dir)
                        zf.write(raw_file, arcname=str(rel_raw).replace('\\', '/'))

            if count == 0:
                print(f"⚠️ Không tìm thấy file content_vi.txt nào để đóng gói trong {chapters_dir}")
                if temp_zip.exists():
                    temp_zip.unlink()
                return None

            if expected_total_chapters is not None and count != expected_total_chapters:
                print(f"🛑 [DriveSyncer] TỪ CHỐI ĐÓNG GÓI: Số lượng file content_vi.txt ({count}) không khớp kỳ vọng ({expected_total_chapters})!")
                if temp_zip.exists():
                    temp_zip.unlink()
                return None

            # Thay thế file zip cũ bằng file mới
            if output_zip.exists():
                output_zip.unlink()
            temp_zip.rename(output_zip)
            print(f"📦 Đã đóng gói thành công {count} chương dịch (kèm content.txt song song) vào {output_zip.name} (Kích thước: {output_zip.stat().st_size / 1024:.1f} KB)")
            return output_zip

        except Exception as e:
            print(f"❌ Lỗi khi đóng gói translated_chapters.zip: {e}")
            if temp_zip.exists():
                temp_zip.unlink()
            return None

    def update_checkpoint(self, story_dir: Path, last_chapter: int) -> Path:
        """Cập nhật hoặc tạo mới file checkpoints.json ghi nhận mốc chương đã hoàn thành."""
        checkpoint_file = story_dir / "checkpoints.json"
        data = {
            "story_id": story_dir.name,
            "last_translated_chapter": last_chapter,
            "updated_at": datetime.now().isoformat()
        }
        checkpoint_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return checkpoint_file

    def sync_story(
        self,
        story_info: Dict[str, Any],
        story_dir: Path,
        translated_chapters: List[int],
        expected_total_chapters: Optional[int] = None
    ) -> bool:
        """
        Đồng bộ toàn bộ sản phẩm dịch của bộ truyện lên Google Drive riêng (tpc-dw):
        1. Đóng gói lại translated_chapters.zip (kiểm tra khớp tổng chương).
        2. Upload ghi đè (update) translated_chapters.zip lên thư mục Vault tpc-dw.
        3. Cập nhật và upload metadata: checkpoints.json, glossary.json, summary.txt.
        """
        self._set_last_error(None)
        story_id = story_dir.name
        source = story_info.get('source', '')

        # 1. Đóng gói zip mới ở local
        zip_path = self.repack_translated_chapters(story_dir, expected_total_chapters=expected_total_chapters)
        if not zip_path:
            err = f"Không tạo được file translated_chapters.zip ở local (hoặc lệch tổng số chương kỳ vọng {expected_total_chapters})"
            self._set_last_error(err)
            print(f"❌ [{story_id}] {err}!")
            return False

        # 2. Xác định thư mục đích trên Kho Dịch tpc-dw (tuyệt đối không ghi vào raw_folder_id)
        vault_folder_id = story_info.get('vault_folder_id')
        if not vault_folder_id:
            vault_root_id = VAULT_DRIVE_FOLDERS.get(source)
            if not vault_root_id:
                err = f"Thiếu vault_folder_id và không xác định được VAULT_DRIVE_FOLDERS cho nguồn '{source}'"
                self._set_last_error(err)
                print(f"❌ [{story_id}] {err}!")
                return False
            try:
                vault_folder_id = self.gdrive_service.get_or_create_story_folder(vault_root_id, story_id)
                story_info['vault_folder_id'] = vault_folder_id
            except Exception as e:
                err = self.gdrive_service.get_last_error() or f"Lỗi tìm/tạo thư mục trên tpc-dw: {e}"
                self._set_last_error(err)
                print(f"❌ [{story_id}] {err}")
                return False

        print(f"\n☁️ [{story_id}] Bắt đầu đồng bộ dữ liệu lên Kho Dịch tpc-dw (Vault Folder ID: {vault_folder_id})...")

        # 3. Upload ghi đè translated_chapters.zip
        print(f"⬆️ [{story_id}] Đang ghi đè translated_chapters.zip lên Google Drive (tpc-dw)...")
        link = self.gdrive_service.upload_or_update_file(zip_path, vault_folder_id, "translated_chapters.zip")
        if not link:
            err = self.gdrive_service.get_last_error() or "Upload translated_chapters.zip thất bại"
            self._set_last_error(err)
            print(f"❌ [{story_id}] Upload translated_chapters.zip thất bại: {err}")
            return False

        # 4. Cập nhật checkpoint
        if translated_chapters:
            last_chap = max(translated_chapters)
            cp_file = self.update_checkpoint(story_dir, last_chap)
            if not self.gdrive_service.upload_or_update_file(cp_file, vault_folder_id, "checkpoints.json"):
                err = self.gdrive_service.get_last_error() or "Upload checkpoints.json thất bại"
                self._set_last_error(f"Đã upload translated_chapters.zip nhưng lỗi checkpoints.json: {err}")
                print(f"❌ [{story_id}] {self.get_last_error()}")
                return False

        # 5. Upload glossary.json & summary.txt nếu có
        glossary_file = story_dir / "glossary.json"
        if glossary_file.exists():
            if not self.gdrive_service.upload_or_update_file(glossary_file, vault_folder_id, "glossary.json"):
                err = self.gdrive_service.get_last_error() or "Upload glossary.json thất bại"
                self._set_last_error(f"Đã upload translated_chapters.zip nhưng lỗi glossary.json: {err}")
                print(f"❌ [{story_id}] {self.get_last_error()}")
                return False

        summary_file = story_dir / "summary.txt"
        if summary_file.exists():
            if not self.gdrive_service.upload_or_update_file(summary_file, vault_folder_id, "summary.txt"):
                err = self.gdrive_service.get_last_error() or "Upload summary.txt thất bại"
                self._set_last_error(f"Đã upload translated_chapters.zip nhưng lỗi summary.txt: {err}")
                print(f"❌ [{story_id}] {self.get_last_error()}")
                return False

        print(f"🎉 [{story_id}] Đồng bộ toàn bộ dữ liệu lên Kho Dịch tpc-dw THÀNH CÔNG!")
        return True

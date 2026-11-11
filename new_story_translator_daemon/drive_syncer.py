"""
Module đóng gói và đồng bộ kết quả dịch truyện mới lên Google Drive.
Tự động tạo mới file translated_chapters.zip và cập nhật checkpoints.json, glossary.json, summary.txt.
"""
import json
import zipfile
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from new_story_translator_daemon.config import VAULT_DRIVE_FOLDERS

class DriveSyncer:
    """Đóng gói và đồng bộ kết quả dịch truyện mới lên Google Drive riêng (tpc-dw)."""

    def __init__(self, gdrive_service):
        self.gdrive_service = gdrive_service
        self._local = threading.local()

    def _set_last_error(self, msg: Optional[str]):
        self._local.last_error = msg

    def get_last_error(self) -> str:
        return getattr(self._local, "last_error", "") or ""

    def repack_translated_chapters(self, story_dir: Path) -> Optional[Path]:
        """
        Quét toàn bộ thư mục chapters/ và đóng gói tất cả các chương có content_vi.txt
        (bao gồm cả content_vi.txt và bản gốc content.txt) vào translated_chapters.zip.
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
                # Quét đệ quy tất cả file content_vi.txt
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

            # Đổi tên file zip hoàn chỉnh
            if output_zip.exists():
                output_zip.unlink()
            temp_zip.rename(output_zip)
            print(f"📦 Đã đóng gói thành công {count} chương dịch mới vào {output_zip.name} ({output_zip.stat().st_size / 1024:.1f} KB)")
            return output_zip

        except Exception as e:
            print(f"❌ Lỗi khi đóng gói translated_chapters.zip: {e}")
            if temp_zip.exists():
                temp_zip.unlink()
            return None

    def update_checkpoint(self, story_dir: Path, last_chapter: int) -> Path:
        """Cập nhật hoặc tạo mới file checkpoints.json ghi nhận mốc chương hoàn thành đầu tiên."""
        checkpoint_file = story_dir / "checkpoints.json"
        data = {
            "story_id": story_dir.name,
            "last_translated_chapter": last_chapter,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        checkpoint_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return checkpoint_file

    def sync_story(
        self,
        story_info: Dict[str, Any],
        story_dir: Path,
        translated_chapters: List[int]
    ) -> bool:
        """
        Đồng bộ toàn bộ sản phẩm dịch mới của bộ truyện lên Google Drive riêng (tpc-dw):
        1. Đóng gói translated_chapters.zip mới.
        2. Tìm hoặc tạo mới thư mục <story_id> trong VAULT_DRIVE_FOLDERS[source].
        3. Upload translated_chapters.zip và metadata: checkpoints.json, glossary.json, summary.txt.
        """
        self._set_last_error(None)
        story_id = story_dir.name
        source = story_info.get('source', '')

        # 1. Đóng gói zip mới ở local trước khi chạm vào Drive
        zip_path = self.repack_translated_chapters(story_dir)
        if not zip_path:
            err = "Không tạo được file nén translated_chapters.zip ở local"
            self._set_last_error(err)
            print(f"❌ [{story_id}] {err}!")
            return False

        # 2. Xác định (hoặc tạo mới on-demand) thư mục truyện bên Kho Dịch riêng tpc-dw
        vault_folder_id = story_info.get('vault_folder_id')
        if not vault_folder_id:
            vault_root_id = VAULT_DRIVE_FOLDERS.get(source)
            if not vault_root_id:
                err = f"Không tìm thấy cấu hình VAULT_DRIVE_FOLDERS cho nguồn '{source}'"
                self._set_last_error(err)
                print(f"❌ [{story_id}] {err}!")
                return False
            try:
                vault_folder_id = self.gdrive_service.get_or_create_story_folder(vault_root_id, story_id)
                story_info['vault_folder_id'] = vault_folder_id
            except Exception as e:
                err = self.gdrive_service.get_last_error() or f"Lỗi tạo thư mục trên tpc-dw: {e}"
                self._set_last_error(err)
                print(f"❌ [{story_id}] {err}")
                return False

        print(f"\n☁️ [{story_id}] Đang tải dữ liệu bản dịch mới lên Kho Dịch tpc-dw (Vault Folder ID: {vault_folder_id})...")

        # 3. Upload file zip lên tpc-dw (Tự động create nếu chưa có)
        print(f"⬆️ [{story_id}] Đang tải translated_chapters.zip lên Google Drive (tpc-dw)...")
        link = self.gdrive_service.upload_or_update_file(zip_path, vault_folder_id, "translated_chapters.zip")
        if not link:
            err = self.gdrive_service.get_last_error() or "Upload translated_chapters.zip thất bại"
            self._set_last_error(err)
            print(f"❌ [{story_id}] Upload translated_chapters.zip lên tpc-dw thất bại: {err}")
            return False

        # 4. Tạo và upload checkpoints.json
        if translated_chapters:
            last_chap = max(translated_chapters)
            cp_file = self.update_checkpoint(story_dir, last_chap)
            if not self.gdrive_service.upload_or_update_file(cp_file, vault_folder_id, "checkpoints.json"):
                err = self.gdrive_service.get_last_error() or "Upload checkpoints.json thất bại"
                self._set_last_error(f"Đã upload translated_chapters.zip nhưng lỗi checkpoints.json: {err}")
                print(f"❌ [{story_id}] {self.get_last_error()}")
                return False

        # 5. Upload glossary.json & summary.txt (đã được AI khởi tạo)
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

        print(f"🎉 [{story_id}] Tạo mới và đồng bộ bản dịch lên Kho Dịch tpc-dw THÀNH CÔNG!")
        return True

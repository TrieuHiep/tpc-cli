"""
Module đóng gói lại file translated_chapters.zip và đồng bộ ngược lên Google Drive bằng update (ghi đè file ID cũ).
"""
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

class DriveSyncer:
    """Đóng gói và đồng bộ kết quả dịch lên Google Drive."""

    def __init__(self, gdrive_service):
        self.gdrive_service = gdrive_service

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
        translated_chapters: List[int]
    ) -> bool:
        """
        Đồng bộ toàn bộ sản phẩm dịch của bộ truyện lên Google Drive:
        1. Đóng gói lại translated_chapters.zip.
        2. Upload ghi đè (update) translated_chapters.zip lên Drive.
        3. Cập nhật và upload metadata: checkpoints.json, glossary.json, summary.txt.
        """
        story_id = story_dir.name
        story_folder_id = story_info['story_folder_id']

        print(f"\n☁️ [{story_id}] Bắt đầu đồng bộ dữ liệu lên Google Drive (Folder ID: {story_folder_id})...")

        # 1. Đóng gói zip mới
        zip_path = self.repack_translated_chapters(story_dir)
        if not zip_path:
            print(f"❌ [{story_id}] Không tạo được file translated_chapters.zip để đồng bộ!")
            return False

        # 2. Upload ghi đè translated_chapters.zip
        print(f"⬆️ [{story_id}] Đang ghi đè translated_chapters.zip lên Drive...")
        link = self.gdrive_service.upload_or_update_file(zip_path, story_folder_id, "translated_chapters.zip")
        if not link:
            print(f"❌ [{story_id}] Upload translated_chapters.zip thất bại!")
            return False

        # 3. Cập nhật checkpoint
        if translated_chapters:
            last_chap = max(translated_chapters)
            cp_file = self.update_checkpoint(story_dir, last_chap)
            self.gdrive_service.upload_or_update_file(cp_file, story_folder_id, "checkpoints.json")

        # 4. Upload glossary.json & summary.txt nếu có
        glossary_file = story_dir / "glossary.json"
        if glossary_file.exists():
            self.gdrive_service.upload_or_update_file(glossary_file, story_folder_id, "glossary.json")

        summary_file = story_dir / "summary.txt"
        if summary_file.exists():
            self.gdrive_service.upload_or_update_file(summary_file, story_folder_id, "summary.txt")

        print(f"🎉 [{story_id}] Đồng bộ toàn bộ dữ liệu lên Google Drive THÀNH CÔNG!")
        return True

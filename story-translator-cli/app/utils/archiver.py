import os
import zipfile
from pathlib import Path
from typing import Optional
from app.utils.logger import logger

def zip_translated_chapters(dataset_dir: Path) -> Optional[Path]:
    """Scans dataset_dir/chapters for folders containing content_vi.txt and archives them into translated_chapters.zip.
    
    Structure inside zip:
    chapters/
        1/
            content.txt
            content_vi.txt
        2/
            content.txt
            content_vi.txt
    """
    dataset_dir = Path(dataset_dir).resolve()
    chapters_dir = dataset_dir / "chapters"

    if not chapters_dir.exists():
        logger.warning(f"Không tìm thấy thư mục chapters tại: {chapters_dir}")
        return None

    translated_folders = []
    for entry in os.listdir(chapters_dir):
        chap_path = chapters_dir / entry
        if chap_path.is_dir():
            vi_file = chap_path / "content_vi.txt"
            if vi_file.exists():
                translated_folders.append((entry, chap_path))

    if not translated_folders:
        logger.warning("Chưa có chương nào được dịch (chưa có content_vi.txt)! Bỏ qua tạo translated_chapters.zip.")
        return None

    # Sort numerically by chapter number if possible
    translated_folders.sort(key=lambda x: int(x[0]) if x[0].isdigit() else x[0])

    zip_out_path = dataset_dir / "translated_chapters.zip"
    logger.info(f"📦 Đang nén {len(translated_folders)} chương đã dịch thành: [cyan]{zip_out_path.name}[/cyan]...")

    try:
        with zipfile.ZipFile(zip_out_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for chap_name, chap_path in translated_folders:
                # Add all files inside chapter folder (content.txt, content_vi.txt)
                for file_entry in os.listdir(chap_path):
                    file_full_path = chap_path / file_entry
                    if file_full_path.is_file():
                        arcname = f"chapters/{chap_name}/{file_entry}"
                        zipf.write(file_full_path, arcname=arcname)

        logger.info(f"🎉 Đã nén xong [green]{zip_out_path.name}[/green] ({len(translated_folders)} chương).")
        return zip_out_path
    except Exception as e:
        logger.error(f"❌ Lỗi trong quá trình nén translated_chapters.zip: {e}")
        return None

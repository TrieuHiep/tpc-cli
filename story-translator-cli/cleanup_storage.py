import os
import sys
import shutil
import argparse
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from app.utils.logger import logger

def cleanup_stories(storage_dir: Path, repo_type: str = 'all', stories: list = None, exclude: list = None, keep_cover: bool = False):
    storage_dir = storage_dir.resolve()
    keep_names = {'info.json', 'chapters.zip'}

    # Include set
    include_set = set()
    if stories:
        for s in stories:
            for item in str(s).split(','):
                if item.strip():
                    include_set.add(item.strip())

    # Exclude set
    exclude_set = set()
    if exclude:
        for e in exclude:
            for item in str(e).split(','):
                if item.strip():
                    exclude_set.add(item.strip())

    if repo_type.lower() == 'all':
        target_repos = ['ixdzs8', 'truyendichwiki', 'novel543']
    else:
        target_repos = [repo_type.lower()]

    deleted_files = 0
    deleted_dirs = 0
    cleaned_stories = 0

    for repo in target_repos:
        repo_path = storage_dir / repo
        if not repo_path.exists():
            continue

        for story_dir in repo_path.iterdir():
            if not story_dir.is_dir():
                continue
            
            s_name = story_dir.name
            if include_set and s_name not in include_set:
                continue
            if s_name in exclude_set:
                logger.info(f'🛡️ [BẢO LƯU] Bỏ qua không dọn dẹp: [green]{s_name}[/green]')
                continue

            story_had_cleanup = False
            for item in list(story_dir.iterdir()):
                item_name_lower = item.name.lower()
                if item_name_lower in keep_names:
                    continue
                if keep_cover and item.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
                    continue

                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                        deleted_files += 1
                        story_had_cleanup = True
                    elif item.is_dir():
                        shutil.rmtree(item)
                        deleted_dirs += 1
                        story_had_cleanup = True
                except Exception as e:
                    logger.warning(f'Không thể xóa {item}: {e}')

            if story_had_cleanup:
                cleaned_stories += 1

    logger.info(f'\n🎉 [DỌN DẸP HOÀN TẤT]')
    logger.info(f'  - Đã dọn dẹp: [bold green]{cleaned_stories}[/bold green] bộ truyện')
    logger.info(f'  - Đã xóa: [bold cyan]{deleted_files}[/bold cyan] files thừa (.lock, logs, checkpoints, summaries, zips...)')
    logger.info(f'  - Đã xóa: [bold cyan]{deleted_dirs}[/bold cyan] thư mục tạm (chapters/)')
    logger.info(f'  - Trạng thái hiện tại: Chỉ giữ lại nguyên bản [bold yellow]chapters.zip[/bold yellow] và [bold yellow]info.json[/bold yellow].')

def main():
    parser = argparse.ArgumentParser(description='Story Translator CLI - Storage Cleanup Engine')
    parser.add_argument('--type', type=str, default='truyendichwiki', choices=['ixdzs8', 'truyendichwiki', 'novel543', 'all'], help='Kho truyện cần dọn dẹp (Mặc định: truyendichwiki)')
    parser.add_argument('--storage-dir', type=str, default='storage', help='Thư mục storage (Mặc định: storage)')
    parser.add_argument('--stories', nargs='*', default=None, help='Chỉ định dọn dẹp các Story ID cụ thể (phân cách bằng dấu cách hoặc phẩy)')
    parser.add_argument('--exclude', nargs='*', default=['Yee9N1S4CHauW96H'], help='Danh sách Story ID cần BẢO LƯU không dọn dẹp (Mặc định bảo lưu: Yee9N1S4CHauW96H)')
    parser.add_argument('--keep-cover', action='store_true', help='Giữ lại ảnh bìa (*.png, *.jpg) nếu có')

    args = parser.parse_args()

    storage_path = (Path(__file__).resolve().parent.parent / args.storage_dir).resolve()
    cleanup_stories(
        storage_dir=storage_path,
        repo_type=args.type,
        stories=args.stories,
        exclude=args.exclude,
        keep_cover=args.keep_cover
    )

if __name__ == '__main__':
    main()

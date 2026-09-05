import os
import sys
import argparse
from pathlib import Path
from typing import Optional, List, Set

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from app.services.gdrive import GoogleDriveService, DRIVE_FOLDERS
from app.utils.logger import logger, console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

METADATA_FILES = ["summary.txt", "glossary.json", "checkpoints.json"]

def sync_metadata_to_gdrive(
    storage_dir: Path,
    repo_type: str = "all",
    story_ids: Optional[List[str]] = None,
    dry_run: bool = False,
    force: bool = False
):
    """Scans local storage directories and uploads metadata files (summary.txt, glossary.json, checkpoints.json) to Google Drive."""
    storage_dir = storage_dir.resolve()
    target_info = f" [Mã truyện: {', '.join(story_ids)}]" if story_ids else ""
    dry_info = " [CHẾ ĐỘ CHẠY THỬ DRY-RUN]" if dry_run else ""
    logger.info(f"🚀 Bắt đầu quét & đồng bộ metadata lên Google Drive{target_info}{dry_info}...")

    gdrive_service = None
    if not dry_run:
        try:
            gdrive_service = GoogleDriveService()
        except Exception as e:
            logger.error(f"❌ Không thể khởi tạo Google Drive Service: {e}")
            return

    if repo_type.lower() == "all":
        target_repos = list(DRIVE_FOLDERS.keys())
    elif repo_type.lower() in DRIVE_FOLDERS:
        target_repos = [repo_type.lower()]
    else:
        logger.error(f"Kho truyện không hợp lệ: {repo_type}. Chọn trong: {list(DRIVE_FOLDERS.keys()) + ['all']}")
        return

    story_filter: Optional[Set[str]] = None
    if story_ids:
        story_filter = {s.strip() for s in story_ids if s.strip()}

    total_stories_found = 0
    total_files_planned = 0
    results = []

    for repo_key in target_repos:
        repo_dir = storage_dir / repo_key
        root_folder_id = DRIVE_FOLDERS[repo_key]

        if not repo_dir.exists():
            logger.warning(f"Thư mục kho local không tồn tại: {repo_dir}")
            continue

        stories = [d for d in repo_dir.iterdir() if d.is_dir()]
        stories.sort(key=lambda x: x.name)

        for story_dir in stories:
            s_name = story_dir.name
            if story_filter and s_name not in story_filter:
                continue

            available_files = []
            for fname in METADATA_FILES:
                fpath = story_dir / fname
                if fpath.exists() and fpath.stat().st_size > 0:
                    available_files.append((fname, fpath))

            if not available_files:
                continue

            total_stories_found += 1
            total_files_planned += len(available_files)
            results.append({
                "repo": repo_key,
                "story_id": s_name,
                "story_dir": story_dir,
                "root_folder_id": root_folder_id,
                "files": available_files
            })

    logger.info(f"📊 Tìm thấy [bold cyan]{len(results)}[/bold cyan] bộ truyện có metadata sẵn sàng đồng bộ (tổng cộng [bold green]{total_files_planned}[/bold green] files).")

    if dry_run:
        logger.info("\n--- DANH SÁCH CHI TIẾT (DRY-RUN) ---")
        table = Table(title="Danh Sách Files Metadata Sẽ Đồng Bộ Lên Drive (DRY-RUN)", style="bold cyan")
        table.add_column("Kho", style="yellow")
        table.add_column("Mã Truyện", style="bold green")
        table.add_column("Files Metadata", style="white")

        for item in results:
            files_str = ", ".join([f"{fname} ({fpath.stat().st_size:,} bytes)" for fname, fpath in item["files"]])
            table.add_row(item["repo"], item["story_id"], files_str)

        console.print(table)
        logger.info("\n💡 Chạy lệnh bỏ cờ --dry-run để thực hiện upload thực tế lên Google Drive.")
        return

    uploaded_stories = 0
    uploaded_files_count = 0
    failed_files_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Đang đồng bộ metadata lên Google Drive...", total=len(results))

        for item in results:
            s_name = item["story_id"]
            repo_key = item["repo"]
            root_folder_id = item["root_folder_id"]
            files = item["files"]

            progress.update(task, description=f"[cyan]Đang xử lý: [yellow]{repo_key}/{s_name}[/yellow]")

            try:
                story_folder_id = gdrive_service.get_or_create_story_folder(root_folder_id, s_name)
                story_has_success = False

                for fname, fpath in files:
                    link = gdrive_service.upload_or_update_file(fpath, story_folder_id, fname)
                    if link:
                        uploaded_files_count += 1
                        story_has_success = True
                    else:
                        failed_files_count += 1

                if story_has_success:
                    uploaded_stories += 1

            except Exception as e:
                logger.error(f"❌ Lỗi đồng bộ truyện {repo_key}/{s_name}: {e}")
                failed_files_count += len(files)

            progress.advance(task)

    logger.info("\n==================================================")
    logger.info("🎉 [HOÀN THÀNH ĐỒNG BỘ METADATA LÊN GOOGLE DRIVE]")
    logger.info(f"  - Số bộ truyện đã đồng bộ: [bold green]{uploaded_stories} / {len(results)}[/bold green]")
    logger.info(f"  - Tổng số file upload thành công: [bold green]{uploaded_files_count}[/bold green]")
    if failed_files_count > 0:
        logger.warning(f"  - Số file thất bại: [bold red]{failed_files_count}[/bold red]")
    logger.info("==================================================\n")

def main():
    parser = argparse.ArgumentParser(description="Story Translator CLI - Sync Metadata to Google Drive Engine")
    parser.add_argument("--type", type=str, default="all", choices=["truyendichwiki", "novel543", "all"], help="Kho truyện cần đồng bộ (Mặc định: all)")
    parser.add_argument("--storage-dir", type=str, default="storage", help="Thư mục storage chứa các kho (Mặc định: storage)")
    parser.add_argument("--story-id", nargs="*", default=None, help="Chỉ định 1 hoặc nhiều Story ID cụ thể (phân cách bằng dấu cách hoặc phẩy)")
    parser.add_argument("--dry-run", action="store_true", help="Chạy kiểm tra thử danh sách file cần upload mà không thực sự ghi lên Drive")
    parser.add_argument("--force", action="store_true", help="Cưỡng bức ghi đè tất cả các file")

    args = parser.parse_args()

    target_story_ids = []
    if args.story_id:
        for s in args.story_id:
            for item in str(s).split(","):
                if item.strip():
                    target_story_ids.append(item.strip())

    root_dir = (Path(__file__).resolve().parent.parent / args.storage_dir).resolve()
    if not root_dir.exists():
        root_dir = (Path(__file__).resolve().parent / args.storage_dir).resolve()

    sync_metadata_to_gdrive(
        storage_dir=root_dir,
        repo_type=args.type,
        story_ids=target_story_ids if target_story_ids else None,
        dry_run=args.dry_run,
        force=args.force
    )

if __name__ == "__main__":
    main()

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from app.utils.logger import logger, console

import zipfile
import re

ZOMBIE_LOCK_TIMEOUT_SECONDS = 12 * 3600  # 12 hours

def extract_chapter_nums_helper(zip_path: Path, dir_path: Path, filename: str) -> int:
    """Helper counting unique chapters containing filename from zip (in-memory) or directory."""
    if zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                chaps = set()
                for name in z.namelist():
                    if name.endswith(filename):
                        parts = Path(name).parts
                        for part in parts:
                            if part.isdigit():
                                chaps.add(int(part))
                                break
                return len(chaps)
        except Exception:
            pass
    if dir_path.exists():
        chaps = [d for d in dir_path.iterdir() if d.is_dir() and (d / filename).exists()]
        return len(chaps)
    return 0

def get_chapter_counts(story_dir: Path):
    """Returns (translated_count, total_raw_count) using fast in-memory zip inspection or dir inspection."""
    raw_count = extract_chapter_nums_helper(story_dir / "chapters.zip", story_dir / "chapters", "content.txt")
    trans_count = extract_chapter_nums_helper(story_dir / "translated_chapters.zip", story_dir / "chapters", "content_vi.txt")
    return trans_count, raw_count

def is_pid_running(pid: int) -> bool:
    """Checks if a process ID is currently running on Windows or Unix."""
    if pid <= 0:
        return False
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
        if process:
            kernel32.CloseHandle(process)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

def acquire_lock(story_dir: Path) -> bool:
    """Attempts to acquire atomic file lock .lock inside story_dir. Cleans zombie locks if stale or PID dead."""
    lock_file = story_dir / ".lock"

    if lock_file.exists():
        # Kiểm tra xem PID ghi trong lock còn đang chạy hay không
        try:
            content = lock_file.read_text(encoding="utf-8")
            lock_pid = None
            if "PID:" in content:
                lock_pid = int(content.split("PID:")[1].split("|")[0].strip())
            
            # Nếu PID đã chết (tiến trình cũ đã tắt/sập) -> Dọn lock ngay lập tức!
            if lock_pid and not is_pid_running(lock_pid):
                logger.warning(f"⚠️ Phát hiện Zombie lock của tiến trình đã tắt (PID {lock_pid}) tại [yellow]{story_dir.name}[/yellow]. Mở khóa tự động...")
                lock_file.unlink()
            else:
                mtime = lock_file.stat().st_mtime
                if time.time() - mtime > ZOMBIE_LOCK_TIMEOUT_SECONDS:
                    logger.warning(f"⚠️ Phát hiện Zombie lock già (>12h) tại [yellow]{story_dir.name}[/yellow]. Mở khóa tự động...")
                    lock_file.unlink()
                else:
                    return False
        except Exception:
            return False

    try:
        with open(lock_file, "x", encoding="utf-8") as f:
            f.write(f"PID: {os.getpid()} | Time: {datetime.now().isoformat()}")
        return True
    except FileExistsError:
        return False

def release_lock(story_dir: Path):
    """Releases file lock .lock inside story_dir."""
    lock_file = story_dir / ".lock"
    if lock_file.exists():
        try:
            lock_file.unlink()
        except Exception as e:
            logger.warning(f"Không thể xóa file .lock tại {story_dir.name}: {e}")

def process_single_story(story_dir: Path, mode: str, target_chapters: int, upload_gdrive: bool, sync_first: bool = False, raw_only: bool = False) -> bool:
    """Processes a single story using main.py if eligible. Returns True if processed."""
    translated_count, total_raw = get_chapter_counts(story_dir)
    cmd_mode_flag = None

    # 1. Mode NEW: Chưa từng có bản dịch (0 chap dịch) -> Dịch target_chapters đầu!
    if mode == "new":
        if translated_count > 0:
            return False
        chapters_arg = target_chapters
        cmd_mode_flag = None

    # 2. Mode RESUME: Đã có bản dịch dở và vẫn còn chương thô -> Dịch tiếp!
    elif mode == "resume":
        if translated_count == 0:
            return False
        if total_raw > 0 and translated_count >= total_raw:
            return False  # Đã hoàn thành 100%
        chapters_arg = target_chapters if target_chapters > 0 else 0
        cmd_mode_flag = "--resume"

    # 3. Mode RETRANSLATE: Dịch lại từ đầu từ Chương 1!
    elif mode == "retranslate":
        chapters_arg = target_chapters if target_chapters > 0 else 0
        cmd_mode_flag = "--retranslate"

    # 4. Mode ALL: Bất kỳ truyện nào chưa hoàn thành 100%
    elif mode == "all":
        if total_raw > 0 and translated_count >= total_raw:
            return False
        chapters_arg = target_chapters if target_chapters > 0 else 0
        cmd_mode_flag = "--resume" if translated_count > 0 else None

    else:
        return False

    # Thử lấy lock nguyên tử
    if not acquire_lock(story_dir):
        return False

    worker_name = threading.current_thread().name

    # Nếu bật --sync-first: Worker tự động kéo data mới nhất của ĐÚNG BỘ TRUYỆN NÀY từ Drive về trước khi dịch!
    if sync_first:
        try:
            from sync_from_gdrive import sync_gdrive_to_local
            logger.info(f"🔄 [{worker_name}] Đang kéo data mới nhất từ Drive cho bộ truyện: [cyan]{story_dir.name}[/cyan]...")
            sync_gdrive_to_local(
                storage_dir=story_dir.parent.parent,
                repo_type=story_dir.parent.name,
                story_id=story_dir.name,
                raw_only=raw_only
            )
        except Exception as e:
            logger.warning(f"⚠️ [{worker_name}] Lỗi khi sync Drive cho truyện {story_dir.name}: {e}")

    log_file_path = story_dir / "translation.log"
    logger.info(f"🚀 [{worker_name}] Bắt đầu xử lý [{mode.upper()}]: [bold cyan]{story_dir.name}[/bold cyan] (Log chi tiết: [dim]{log_file_path}[/dim])")

    try:
        cmd = [
            sys.executable, "main.py",
            "--source", str(story_dir),
            "--chapters", str(chapters_arg)
        ]
        if cmd_mode_flag:
            cmd.append(cmd_mode_flag)
        if upload_gdrive:
            cmd.append("--upload-gdrive")

        # Ghi log chi tiết của từng chap/LLM vào file translation.log trong chính thư mục truyện
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n=== BẮT ĐẦU TRANSLATION BATCH: {datetime.now().isoformat()} ===\n")
            res = subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT)

        if res.returncode != 0:
            logger.error(f"❌ [{worker_name}] Lỗi khi dịch {story_dir.name} (main.py thoát với mã lỗi {res.returncode})")
            return False

        logger.info(f"🎉 [{worker_name}] Hoàn thành xử lý truyện: [bold green]{story_dir.name}[/bold green]")
        return True
    except Exception as e:
        logger.error(f"❌ [{worker_name}] Lỗi khi dịch {story_dir.name} (Xem chi tiết tại {log_file_path}): {e}")
        return False
    finally:
        release_lock(story_dir)

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def run_batch(storage_dir: Path, repo_type: str, mode: str, target_chapters: int, max_stories: int, workers: int, upload_gdrive: bool, sync_first: bool = False, loop: bool = False, exclude: list = None, exclude_file: str = None, raw_only: bool = False, sort_by: str = "name", stories: list = None, stories_file: str = None):
    """Scans storage_dir and dispatches stories to process in batch, supporting multithreading parallel workers, inclusion/exclusion lists, and chapter-based sorting."""
    storage_dir = storage_dir.resolve()
    limit_info = f" | Giới hạn: {max_stories} truyện" if max_stories > 0 else ""
    worker_info = f" | Multithread: {workers} Workers song song" if workers > 1 else ""
    sync_info = f" | Per-Story Drive Sync: BẬT{' (Raw Only)' if raw_only else ''}" if sync_first else ""
    sort_info = f" | Sắp xếp: {sort_by.upper()}" if sort_by != "name" else ""

    # Xây dựng tập hợp các Story ID được chỉ định dịch (Include Set)
    include_set = set()
    if stories:
        for item in stories:
            for sub_item in str(item).split(","):
                if sub_item.strip():
                    include_set.add(sub_item.strip())

    if stories_file:
        inc_path = Path(stories_file).resolve()
        if inc_path.exists():
            with open(inc_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        include_set.add(line)
        else:
            logger.warning(f"⚠️ File stories không tồn tại: {stories_file}")

    # Xây dựng tập hợp các Story ID cần loại trừ (Exclude Set)
    exclude_set = set()
    if exclude:
        for item in exclude:
            for sub_item in item.split(","):
                if sub_item.strip():
                    exclude_set.add(sub_item.strip())

    if exclude_file:
        ex_path = Path(exclude_file).resolve()
        if ex_path.exists():
            with open(ex_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        exclude_set.add(line)
        else:
            logger.warning(f"⚠️ File exclude không tồn tại: {exclude_file}")

    include_info = f" | Chỉ định: {len(include_set)} truyện" if include_set else ""
    exclude_info = f" | Loại trừ: {len(exclude_set)} truyện" if exclude_set else ""
    logger.info(f"🚜 Khởi chạy Batch Runner [PID: {os.getpid()}] | Kho: [bold gold1]{repo_type.upper()}[/bold gold1] | Mode: [bold cyan]{mode.upper()}[/bold cyan]{limit_info}{worker_info}{sync_info}{sort_info}{include_info}{exclude_info}")
    if include_set:
        logger.info(f"   🎯 Chỉ xử lý các truyện: {', '.join(sorted(list(include_set))[:8])}{'...' if len(include_set) > 8 else ''}")
    if exclude_set:
        logger.info(f"   🚫 Bỏ qua các truyện: {', '.join(sorted(list(exclude_set))[:8])}{'...' if len(exclude_set) > 8 else ''}")

    total_processed_count = 0
    count_lock = threading.Lock()

    def task_wrapper(story_dir: Path) -> bool:
        nonlocal total_processed_count
        with count_lock:
            if max_stories > 0 and total_processed_count >= max_stories:
                return False

        did_run = process_single_story(story_dir, mode, target_chapters, upload_gdrive, sync_first=sync_first, raw_only=raw_only)
        if did_run:
            with count_lock:
                total_processed_count += 1
                logger.info(f"📊 Tiến độ: Đã hoàn thành [bold green]{total_processed_count}[/bold green]" + (f"/{max_stories}" if max_stories > 0 else "") + " bộ truyện.")
            return True
        return False

    if repo_type.lower() == "all":
        target_repos = ["truyendichwiki", "novel543"]
    else:
        target_repos = [repo_type.lower()]

    while True:
        story_dirs = []
        for repo in target_repos:
            repo_path = storage_dir / repo
            if repo_path.exists():
                for sub in repo_path.iterdir():
                    if sub.is_dir():
                        if include_set and sub.name not in include_set:
                            continue
                        if sub.name in exclude_set:
                            continue
                        story_dirs.append(sub)

        # Quét và lọc trước các truyện đủ điều kiện
        eligible_stories = []
        for sd in story_dirs:
            if (sd / ".lock").exists():
                continue
            translated_count, total_raw = get_chapter_counts(sd)
            if mode == "new" and translated_count == 0:
                eligible_stories.append((sd, total_raw, translated_count))
            elif mode == "resume" and translated_count > 0:
                if total_raw > 0 and translated_count < total_raw:
                    eligible_stories.append((sd, total_raw, translated_count))
            elif mode == "retranslate":
                eligible_stories.append((sd, total_raw, translated_count))
            elif mode == "all":
                if total_raw > 0 and translated_count < total_raw:
                    eligible_stories.append((sd, total_raw, translated_count))

        # Sắp xếp danh sách truyện đủ điều kiện
        if sort_by == "shortest":
            eligible_stories.sort(key=lambda item: (item[1] if item[1] > 0 else 999999, item[0].name))
        elif sort_by == "longest":
            eligible_stories.sort(key=lambda item: (item[1], item[0].name), reverse=True)
        else:
            eligible_stories.sort(key=lambda item: item[0].name)

        if max_stories > 0:
            to_process_list = [item[0] for item in eligible_stories[:max_stories]]
        else:
            to_process_list = [item[0] for item in eligible_stories]

        if to_process_list:
            sort_desc = " (Ưu tiên truyện ít chương nhất)" if sort_by == "shortest" else (" (Ưu tiên truyện nhiều chương nhất)" if sort_by == "longest" else "")
            logger.info(f"\n📋 [Batch Scan Result] Tìm thấy [bold gold1]{len(eligible_stories)}[/bold gold1] bộ truyện đủ điều kiện{sort_desc}. Sẽ thực hiện [bold cyan]{len(to_process_list)}[/bold cyan] bộ truyện:")
            for idx, sd in enumerate(to_process_list, 1):
                trans, total = get_chapter_counts(sd)
                logger.info(f"   {idx}. [cyan]{sd.name}[/cyan] ({total} chaps) - Kho: {sd.parent.name}")
            logger.info("--------------------------------------------------\n")
        else:
            logger.info(f"ℹ️ Không tìm thấy bộ truyện nào đủ điều kiện dịch [{mode.upper()}] trong kho {repo_type.upper()}.")

        processed_any = False

        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="Worker") as executor:
                futures = [executor.submit(task_wrapper, sd) for sd in to_process_list]
                for future in as_completed(futures):
                    try:
                        if future.result():
                            processed_any = True
                    except Exception as err:
                        logger.error(f"⚠️ Một Worker gặp lỗi ngoài ý muốn nhưng các Worker khác vẫn tiếp tục bình thường: {err}")
        else:
            for story_dir in to_process_list:
                with count_lock:
                    if max_stories > 0 and total_processed_count >= max_stories:
                        break
                if task_wrapper(story_dir):
                    processed_any = True

        if max_stories > 0 and total_processed_count >= max_stories:
            logger.info(f"🛑 Đã hoàn thành đủ giới hạn [bold gold1]{max_stories}[/bold gold1] bộ truyện. Dừng Batch Runner!")
            return

        if not loop:
            logger.info("🏁 [Batch Runner] Đã hoàn tất lượt quét kho dataset!")
            break

        if not processed_any:
            logger.info("💤 Không có bộ truyện nào cần xử lý. Tạm nghỉ 30 giây trước khi quét lại...")
            time.sleep(30)

def main():
    parser = argparse.ArgumentParser(description="Story Translator CLI - Batch Runner Multi-Worker Coordinator")
    parser.add_argument("--type", type=str, required=True, choices=["truyendichwiki", "novel543", "all"], help="BẮT BUỘC: Nhóm kho dataset để thực hiện dịch ('truyendichwiki', 'novel543' hoặc 'all')")
    parser.add_argument("--mode", type=str, choices=["new", "resume", "retranslate", "all"], default="new", help="Mode hoạt động: 'new' (dịch 200 chap đầu truyện mới), 'resume' (dịch nốt các chap còn lại), 'retranslate' (dịch lại từ đầu) hoặc 'all'")
    parser.add_argument("--storage-dir", type=str, default="storage", help="Đường dẫn thư mục chứa kho dataset local (Mặc định: storage)")
    parser.add_argument("--target-chapters", type=int, default=200, help="Số chương mục tiêu cho Mode new (Mặc định: 200)")
    parser.add_argument("--max-stories", type=int, default=0, help="Số lượng bộ truyện tối đa cần dịch trong đợt này (Mặc định: 0 - Không giới hạn)")
    parser.add_argument("--workers", type=int, default=1, help="Số lượng Worker/Thread chạy song song trong 1 lệnh duy nhất (Mặc định: 1)")
    parser.add_argument("--upload-gdrive", action="store_true", help="Tự động nén và tải bản dịch lên Google Drive sau khi dịch xong")
    parser.add_argument("--sync-first", action="store_true", help="Tùy chọn: Tự động chạy kéo dữ liệu mới từ Google Drive về cho từng truyện ngay trước khi dịch")
    parser.add_argument("--raw-only", action="store_true", help="Khi dùng --sync-first, chỉ kéo đúng info.json và chapters.zip, không kéo ảnh bìa hay translated_chapters.zip")
    parser.add_argument("--sort-by", type=str, choices=["name", "shortest", "longest"], default="name", help="Tiêu chí sắp xếp: 'shortest' (ưu tiên truyện ngắn/ít chương nhất trước), 'longest' (nhiều chương trước), hoặc 'name' (theo tên ID. Mặc định: name)")
    parser.add_argument("--sort-shortest", action="store_true", help="Phím tắt: Ưu tiên truyện ngắn / ít chương nhất lên dịch trước")
    parser.add_argument("--exclude", nargs="*", default=None, help="Danh sách Story ID cần bỏ qua (loại trừ không dịch), phân cách bằng dấu phẩy hoặc khoảng trắng. Ví dụ: --exclude X7Yb6VS4CDNFzfcB WOqruu8h7AsKxRYh")
    parser.add_argument("--exclude-file", type=str, default=None, help="Đường dẫn tới file text chứa danh sách Story ID cần loại trừ (mỗi ID một dòng)")
    parser.add_argument("--stories", nargs="*", default=None, help="Danh sách Story ID cụ thể CẦN DỊCH (phân cách bằng dấu phẩy hoặc khoảng trắng). Ví dụ: --stories YPire1S4CAhlFVsL YM06B1S4CH1RVTQP")
    parser.add_argument("--stories-file", type=str, default=None, help="Đường dẫn tới file text chứa danh sách Story ID CẦN DỊCH (mỗi ID một dòng)")
    parser.add_argument("--loop", action="store_true", help="Bật chế độ quét lặp ngầm liên tục trên Server")

    args = parser.parse_args()

    sort_strategy = "shortest" if args.sort_shortest else args.sort_by

    storage_path = (Path(__file__).resolve().parent.parent / args.storage_dir).resolve()
    storage_path.mkdir(parents=True, exist_ok=True)

    run_batch(
        storage_dir=storage_path,
        repo_type=args.type,
        mode=args.mode,
        target_chapters=args.target_chapters,
        max_stories=args.max_stories,
        workers=args.workers,
        upload_gdrive=args.upload_gdrive,
        sync_first=args.sync_first,
        loop=args.loop,
        exclude=args.exclude,
        exclude_file=args.exclude_file,
        raw_only=args.raw_only,
        sort_by=sort_strategy,
        stories=args.stories,
        stories_file=args.stories_file
    )

if __name__ == "__main__":
    main()

import os
import sys
import time
import argparse
import asyncio
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from app.services.pipeline import TranslationPipeline
from app.utils.logger import logger
try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
    console = Console(force_terminal=True)
except ImportError:
    HAS_RICH = False

def print_report_table(results: list):
    """Prints beautiful summary report table formatted with step timing breakdowns."""
    if not results:
        return

    if HAS_RICH:
        table = Table(title="📊 BÁO CÁO KẾT QUẢ THẨM ĐỊNH & THỜI GIAN CHẠY PIPELINE", show_header=True, header_style="bold magenta")
        table.add_column("Chương", style="cyan", width=12)
        table.add_column("Tiêu đề Tiếng Việt", style="white")
        table.add_column("Điểm QC", justify="center", style="green", width=12)
        table.add_column("Thời gian (Dịch / QC / Tổng)", justify="center", style="yellow", width=30)
        table.add_column("Trạng Thái", justify="center", width=14)

        for res in results:
            timing_str = f"{res.get('time_trans', '-')} | {res.get('time_qc', '-')} | {res.get('time_total', '-')}"
            table.add_row(res["chapter"], res["title"], res["qc_score"], timing_str, res["status"])

        console.print("\n")
        console.print(table)
        console.print("\n")
    else:
        print("\n" + "=" * 90)
        print("📊 BÁO CÁO KẾT QUẢ THẨM ĐỊNH & THỜI GIAN CHẠY PIPELINE")
        print("=" * 90)
        for res in results:
            timing_str = f"{res.get('time_trans', '-')} | {res.get('time_qc', '-')} | {res.get('time_total', '-')}"
            print(f"[{res['chapter']}] {res['title']} | QC: {res['qc_score']} | Time: {timing_str} | Status: {res['status']}")
        print("=" * 90 + "\n")

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

def parse_chapters_arg(items: list) -> set:
    """Parses arbitrary chapter strings (e.g. ['1', '5', '12', '34'] or ['1-5', '10', '20,22']) into a set of integer chapter numbers."""
    if not items:
        return set()
    result = set()
    for item in items:
        parts = str(item).split(',')
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if '-' in p:
                sub_parts = p.split('-')
                if len(sub_parts) == 2 and sub_parts[0].strip().isdigit() and sub_parts[1].strip().isdigit():
                    start_c = int(sub_parts[0].strip())
                    end_c = int(sub_parts[1].strip())
                    for c in range(min(start_c, end_c), max(start_c, end_c) + 1):
                        result.add(c)
            elif p.isdigit():
                result.add(int(p))
    return result

async def async_main():
    parser = argparse.ArgumentParser(description="Story Translator CLI - Dịch & Biên tập truyện tự động qua OpenRouter API")
    parser.add_argument("--source", type=str, required=True, help="Đường dẫn thư mục Local Dataset (chứa info.json và chapters/)")
    parser.add_argument("--chapters", type=int, default=5, help="Số lượng chương tối đa cần dịch theo thứ tự (Nhập 0 để dịch TOÀN BỘ các chương còn lại. Mặc định: 5)")
    parser.add_argument("--upload-gdrive", action="store_true", help="Tự động nén và tải/ghi đè bản dịch (translated_chapters.zip) lên Google Drive sau khi dịch xong")

    # Các tùy chọn chỉ định chương cụ thể
    parser.add_argument("--chapter", type=int, default=None, help="Chỉ định dịch chính xác DUY NHẤT 1 số chương cụ thể (Ví dụ: --chapter 34)")
    parser.add_argument("--chapter-range", nargs=2, type=int, default=None, metavar=("START", "END"), help="Chỉ định dịch một khoảng chương cụ thể [Start End] (Ví dụ: --chapter-range 10 20)")
    parser.add_argument("--chapters-list", nargs="*", default=None, help="Chỉ định danh sách các chương bất kỳ (Ví dụ: --chapters-list 1 5 12 34 hoặc --chapters-list 1-5 10 20-25)")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--resume", action="store_true", help="Bật chế độ khôi phục chạy tiếp các chương còn thiếu từ checkpoint")
    mode_group.add_argument("--retranslate", action="store_true", help="Bật chế độ dịch lại từ đầu (Retranslate): Xóa sạch toàn bộ bản dịch cũ và dịch mới 100%% từ Chương 1")

    args = parser.parse_args()

    selected_chapters = None
    if args.chapter is not None:
        selected_chapters = {args.chapter}
    elif args.chapter_range is not None:
        start_c, end_c = args.chapter_range
        selected_chapters = set(range(min(start_c, end_c), max(start_c, end_c) + 1))
    elif args.chapters_list:
        selected_chapters = parse_chapters_arg(args.chapters_list)

    if selected_chapters:
        sorted_preview = sorted(list(selected_chapters))
        preview_str = ", ".join(str(c) for c in sorted_preview[:10]) + ("..." if len(sorted_preview) > 10 else "")
        logger.info(f"🎯 Đã chỉ định dịch [bold cyan]{len(selected_chapters)}[/bold cyan] chương: [yellow]{preview_str}[/yellow]")

    source_path = Path(args.source).resolve()
    lock_file = source_path / ".lock"
    created_lock_here = False

    # Kiểm tra khóa nguyên tử .lock để tránh 2 tiến trình cùng dịch 1 bộ truyện
    if lock_file.exists():
        lock_pid = None
        try:
            content = lock_file.read_text(encoding="utf-8")
            if "PID:" in content:
                lock_pid = int(content.split("PID:")[1].split("|")[0].strip())
        except Exception:
            pass

        current_pid = os.getpid()
        parent_pid = os.getppid()

        # Nếu PID tạo lock không phải là tiến trình hiện tại VÀ không phải là tiến trình cha (batch_runner.py)
        if lock_pid and lock_pid not in (current_pid, parent_pid):
            # Nếu PID đã tắt/chết -> Tự động giải phóng lock ngay lập tức
            if not is_pid_running(lock_pid):
                logger.warning(f"⚠️ Phát hiện Zombie lock của tiến trình đã tắt (PID {lock_pid}) tại {source_path.name}. Tiến hành tự dọn dẹp...")
                try:
                    lock_file.unlink()
                except Exception:
                    pass
            else:
                lock_mtime = lock_file.stat().st_mtime
                if time.time() - lock_mtime > 12 * 3600:
                    logger.warning(f"⚠️ Phát hiện file .lock cũ quá 12 giờ tại {source_path.name}. Tiến hành tự dọn dẹp...")
                    try:
                        lock_file.unlink()
                    except Exception:
                        pass
                else:
                    logger.error(f"⛔ [LOCK ERROR] Bộ truyện {source_path.name} đang được 1 tiến trình/Worker khác (PID {lock_pid}) xử lý (Đã tồn tại file .lock). Dừng thực thi để tránh xung đột!")
                    sys.exit(1)
    else:
        # Nếu chưa có lock, main.py tự tạo lock cho chính nó
        try:
            with open(lock_file, "x", encoding="utf-8") as f:
                f.write(f"PID: {os.getpid()} | Time: {datetime.now().isoformat()}")
            created_lock_here = True
        except Exception as e:
            logger.warning(f"⚠️ Không thể tạo file .lock tại {source_path.name}: {e}")

    pipeline = None
    try:
        pipeline = TranslationPipeline(dataset_path=str(source_path), retranslate=args.retranslate)
        results = await pipeline.run(
            max_chapters=args.chapters if selected_chapters is None else 0,
            resume=args.resume,
            upload_gdrive=args.upload_gdrive,
            selected_chapters=selected_chapters
        )

        if results:
            print_report_table(results)
            logger.info("🎉 [HOÀN THÀNH] Đã hoàn thành toàn bộ công việc dịch và thẩm định!")
    finally:
        if pipeline:
            try:
                await pipeline.close()
            except Exception:
                pass
        # Chỉ giải phóng .lock nếu do chính main.py này trực tiếp tạo ra (không xóa lock của cha batch_runner)
        if created_lock_here and lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass

def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

import os
import sys
import json
import csv
import re
import zipfile
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Check if rich is available, otherwise use elegant ANSI colors
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False

# ANSI Color constants for pure Python fallback
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def extract_chapter_nums_from_zip(zip_path: Path, target_filename: str) -> Set[int]:
    """Reads zip file in memory and extracts unique chapter numbers containing target_filename."""
    if not zip_path.exists():
        return set()
    
    chapter_nums = set()
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                # Match patterns like "1/content.txt", "chapters/1/content.txt", "001/content_vi.txt"
                if name.endswith(target_filename):
                    parts = Path(name).parts
                    for part in parts:
                        if part.isdigit():
                            chapter_nums.add(int(part))
                            break
    except Exception as e:
        print(f"❌ Lỗi đọc file zip {zip_path.name}: {e}")
    return chapter_nums

def extract_chapter_nums_from_dir(chapters_dir: Path, target_filename: str) -> Set[int]:
    """Scans extracted chapters directory for target_filename."""
    if not chapters_dir.exists():
        return set()
    
    chapter_nums = set()
    for entry in os.listdir(chapters_dir):
        chap_dir = chapters_dir / entry
        if chap_dir.is_dir() and entry.isdigit():
            if (chap_dir / target_filename).exists():
                chapter_nums.add(int(entry))
    return chapter_nums

def scan_story_directory(story_dir: Path) -> Dict[str, Any]:
    """Scans a single story folder in memory and returns its translation status."""
    story_id = story_dir.name
    info_path = story_dir / "info.json"
    
    # 1. Đọc metadata từ info.json
    title = story_id
    author = "Chưa rõ"
    if info_path.exists():
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info_data = json.load(f)
                title = info_data.get("title") or story_id
                author = info_data.get("author") or "Chưa rõ"
        except Exception:
            pass

    # 2. Đếm số chương thô (raw chapters)
    raw_zip = story_dir / "chapters.zip"
    raw_dir = story_dir / "chapters"
    raw_chaps = extract_chapter_nums_from_zip(raw_zip, "content.txt")
    if not raw_chaps and raw_dir.exists():
        raw_chaps = extract_chapter_nums_from_dir(raw_dir, "content.txt")
    
    raw_count = len(raw_chaps)

    # 3. Đếm số chương đã dịch (translated chapters)
    trans_zip = story_dir / "translated_chapters.zip"
    trans_chaps = extract_chapter_nums_from_zip(trans_zip, "content_vi.txt")
    if not trans_chaps and raw_dir.exists():
        trans_chaps = extract_chapter_nums_from_dir(raw_dir, "content_vi.txt")
    
    trans_count = len(trans_chaps)

    # 4. Phân loại trạng thái
    if raw_count == 0:
        status = "NO_RAW_DATA"
        status_label = "🔴 THIẾU DỮ LIỆU"
        pct = 0.0
    elif trans_count >= raw_count:
        status = "FULL_TRANSLATED"
        status_label = "🟢 FULL (100%)"
        pct = 100.0
    elif trans_count > 0:
        status = "PARTIAL"
        pct = (trans_count / raw_count) * 100
        status_label = f"🟡 DỊCH DỞ ({pct:.1f}%)"
    else:
        status = "NOT_STARTED"
        status_label = "⚪ CHƯA DỊCH"
        pct = 0.0

    return {
        "story_id": story_id,
        "title": title,
        "author": author,
        "raw_count": raw_count,
        "trans_count": trans_count,
        "pct": pct,
        "status": status,
        "status_label": status_label,
        "has_chapters_zip": raw_zip.exists(),
        "has_trans_zip": trans_zip.exists(),
        "path": str(story_dir.resolve())
    }

def print_pure_table(filtered_results: List[Dict[str, Any]], results: List[Dict[str, Any]]):
    """Fallback printer using pure Python standard formatting."""
    print("=" * 115)
    print(f"{'#':<4} | {'Mã Truyện':<18} | {'Tên Truyện':<38} | {'Tiến Độ (Dịch/Thô)':<20} | {'Tỷ Lệ':<8} | {'Trạng Thái':<18}")
    print("-" * 115)
    
    for idx, r in enumerate(filtered_results, start=1):
        title_str = r['title'][:35] + ("..." if len(r['title']) > 35 else "")
        prog_str = f"{r['trans_count']} / {r['raw_count']} chaps"
        pct_str = f"{r['pct']:.1f}%"
        
        # Colorize
        if r["status"] == "FULL_TRANSLATED":
            stat_color = f"{Colors.OKGREEN}{r['status_label']}{Colors.ENDC}"
        elif r["status"] == "PARTIAL":
            stat_color = f"{Colors.WARNING}{r['status_label']}{Colors.ENDC}"
        elif r["status"] == "NO_RAW_DATA":
            stat_color = f"{Colors.FAIL}{r['status_label']}{Colors.ENDC}"
        else:
            stat_color = f"{Colors.DIM}{r['status_label']}{Colors.ENDC}"
            
        print(f"{idx:<4} | {r['story_id']:<18} | {title_str:<38} | {prog_str:<20} | {pct_str:<8} | {stat_color}")
    print("=" * 115)

    full_count = sum(1 for r in results if r["status"] == "FULL_TRANSLATED")
    partial_count = sum(1 for r in results if r["status"] == "PARTIAL")
    not_started_count = sum(1 for r in results if r["status"] == "NOT_STARTED")
    error_count = sum(1 for r in results if r["status"] == "NO_RAW_DATA")
    total_raw_chapters = sum(r["raw_count"] for r in results)
    total_trans_chapters = sum(r["trans_count"] for r in results)
    total_pct = (total_trans_chapters / total_raw_chapters * 100) if total_raw_chapters else 0

    print(f"\n📈 {Colors.BOLD}TỔNG KẾT DATASET ({len(results)} Bộ Truyện):{Colors.ENDC}")
    print(f"├─ {Colors.OKGREEN}🟢 Đã Dịch Full (100%):{Colors.ENDC} {full_count} truyện")
    print(f"├─ {Colors.WARNING}🟡 Đang Dịch Dở (Cần chạy tiếp):{Colors.ENDC} {partial_count} truyện")
    print(f"├─ {Colors.DIM}⚪ Chưa Dịch (0%):{Colors.ENDC} {not_started_count} truyện")
    print(f"├─ {Colors.FAIL}🔴 Thiếu Dữ Liệu Thô:{Colors.ENDC} {error_count} truyện")
    print(f"└─ 📊 Tổng Số Chương Đã Dịch: {Colors.OKCYAN}{total_trans_chapters:,} / {total_raw_chapters:,} chương ({total_pct:.2f}%){Colors.ENDC}\n")

def main():
    parser = argparse.ArgumentParser(description="Tiện ích Quét & Báo Cáo Tiến Độ Dịch Truyện Từ File Zip")
    parser.add_argument("--root_dir", "-d", type=str, default="../storage/truyendichwiki", help="Thư mục gốc chứa các bộ truyện")
    parser.add_argument("--filter", "-f", type=str, choices=["all", "full", "partial", "not_started", "error"], default="all", help="Lọc theo trạng thái")
    parser.add_argument("--export", "-e", type=str, default="", help="Đường dẫn xuất file báo cáo (.json hoặc .csv)")
    args = parser.parse_args()

    root_path = Path(args.root_dir).resolve()
    if not root_path.exists():
        print(f"❌ Không tìm thấy thư mục gốc: {root_path}")
        sys.exit(1)

    story_dirs = [d for d in root_path.iterdir() if d.is_dir()]
    if not story_dirs:
        print(f"⚠️ Thư mục {root_path} không chứa thư mục truyện con nào!")
        sys.exit(0)

    print(f"\n🔍 BẮT ĐẦU QUÉT TIẾN ĐỘ DỊCH TRUYỆN")
    print(f"📂 Thư mục: {root_path}")
    print(f"📚 Tổng số thư mục truyện: {len(story_dirs)}\n")

    results = []
    for s_dir in story_dirs:
        res = scan_story_directory(s_dir)
        results.append(res)

    # Sắp xếp: Đang dịch dở (cần tiếp tục) -> Chưa dịch -> Đã full
    status_order = {"PARTIAL": 0, "NOT_STARTED": 1, "FULL_TRANSLATED": 2, "NO_RAW_DATA": 3}
    results.sort(key=lambda x: (status_order.get(x["status"], 99), -x["pct"], x["title"]))

    # Bộ lọc
    filtered_results = []
    for r in results:
        if args.filter == "all":
            filtered_results.append(r)
        elif args.filter == "full" and r["status"] == "FULL_TRANSLATED":
            filtered_results.append(r)
        elif args.filter == "partial" and r["status"] == "PARTIAL":
            filtered_results.append(r)
        elif args.filter == "not_started" and r["status"] == "NOT_STARTED":
            filtered_results.append(r)
        elif args.filter == "error" and r["status"] == "NO_RAW_DATA":
            filtered_results.append(r)

    if HAS_RICH:
        table = Table(title=f"📊 BẢNG TIẾN ĐỘ DỊCH TRUYỆN ({len(filtered_results)}/{len(results)} Bộ Truyện)", show_lines=True)
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Mã Truyện", style="cyan", width=18)
        table.add_column("Tên Truyện", style="bold white", width=36)
        table.add_column("Tiến Độ (Đã Dịch / Tổng)", justify="center", width=22)
        table.add_column("Tỷ Lệ", justify="right", width=8)
        table.add_column("Trạng Thái", justify="center", width=24)

        full_count = sum(1 for r in results if r["status"] == "FULL_TRANSLATED")
        partial_count = sum(1 for r in results if r["status"] == "PARTIAL")
        not_started_count = sum(1 for r in results if r["status"] == "NOT_STARTED")
        error_count = sum(1 for r in results if r["status"] == "NO_RAW_DATA")
        total_raw_chapters = sum(r["raw_count"] for r in results)
        total_trans_chapters = sum(r["trans_count"] for r in results)

        for idx, r in enumerate(filtered_results, start=1):
            progress_str = f"[green]{r['trans_count']}[/green] / [bold]{r['raw_count']}[/bold] chaps"
            pct_str = f"{r['pct']:.1f}%"
            
            if r["status"] == "FULL_TRANSLATED":
                status_rich = f"[bold green]{r['status_label']}[/bold green]"
            elif r["status"] == "PARTIAL":
                status_rich = f"[bold yellow]{r['status_label']}[/bold yellow]"
            elif r["status"] == "NO_RAW_DATA":
                status_rich = f"[bold red]{r['status_label']}[/bold red]"
            else:
                status_rich = f"[dim white]{r['status_label']}[/dim white]"
                
            table.add_row(
                str(idx),
                r["story_id"],
                r["title"][:34] + ("..." if len(r["title"]) > 34 else ""),
                progress_str,
                pct_str,
                status_rich
            )

        console.print(table)

        summary_panel = Panel(
            f"📈 [bold]TỔNG KẾT TOÀN BỘ DATASET ({len(results)} Bộ Truyện):[/bold]\n"
            f"├─ 🟢 [bold green]Đã Dịch Full (100%):[/bold green] {full_count} truyện\n"
            f"├─ 🟡 [bold yellow]Đang Dịch Dở (Cần chạy tiếp):[/bold yellow] {partial_count} truyện\n"
            f"├─ ⚪ [dim white]Chưa Dịch (0%):[/dim white] {not_started_count} truyện\n"
            f"├─ 🔴 [bold red]Thiếu Dữ Liệu Thô:[/bold red] {error_count} truyện\n"
            f"└─ 📊 [cyan]Tổng Số Chương Đã Dịch:[/cyan] [bold green]{total_trans_chapters:,}[/bold green] / [bold]{total_raw_chapters:,}[/bold] chương "
            f"([bold cyan]{(total_trans_chapters / total_raw_chapters * 100 if total_raw_chapters else 0):.2f}%[/bold cyan])",
            title="[bold gold1]TỔNG QUAN HỆ THỐNG[/bold gold1]",
            border_style="gold1"
        )
        console.print(summary_panel)
    else:
        print_pure_table(filtered_results, results)

    # Xuất file nếu có yêu cầu
    if args.export:
        export_path = Path(args.export)
        if export_path.suffix.lower() == ".csv":
            with open(export_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["story_id", "title", "author", "raw_count", "trans_count", "pct", "status", "path"])
                writer.writeheader()
                for r in results:
                    writer.writerow({k: r[k] for k in ["story_id", "title", "author", "raw_count", "trans_count", "pct", "status", "path"]})
            print(f"✅ Đã xuất báo cáo CSV thành công: {export_path}")
        else:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"✅ Đã xuất báo cáo JSON thành công: {export_path}")

if __name__ == "__main__":
    main()

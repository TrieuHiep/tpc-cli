import sys
import json
import asyncio
import time
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from app.services.local_loader import LocalLoaderService
from app.services.qc_auditor import QCAuditorService
from app.core.openrouter import OpenRouterClient
from app.utils.logger import logger, console
from app.utils.text_cleaner import clean_plain_text, extract_and_strip_chinese
from rich.table import Table

async def run_targeted_audit(dataset_path: str):
    loader = LocalLoaderService(dataset_path)
    report_json_path = loader.dataset_dir / "manual_audit_report.json"
    report_txt_path = loader.dataset_dir / "manual_audit_report.txt"

    if not report_json_path.exists():
        logger.info("🎉 Không tìm thấy file manual_audit_report.json — Không có chương nào cần Audit thủ công!")
        return

    with open(report_json_path, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    if not audit_data:
        logger.info("🎉 Danh sách manual_audit_report.json rỗng — Không có chương nào cần Audit!")
        return

    logger.info(f"🔍 [Targeted Audit] Bắt đầu rà soát QC chuyên sâu cho {len(audit_data)} chương trong danh sách Audit...")

    llm_client = OpenRouterClient()
    qc_auditor = QCAuditorService(llm_client)

    audit_results = []
    fixed_chapters = []

    for key, item in list(audit_data.items()):
        # Extract chapter number from key e.g. "Chương 08" -> 8
        chap_num_match = Path(item["chapter"]).name
        import re
        num_search = re.search(r'\d+', chap_num_match)
        if not num_search:
            continue
        chap_num = int(num_search.group())

        chap_dir = loader.chapters_dir / str(chap_num)
        if not chap_dir.exists():
            logger.warning(f"Không tìm thấy thư mục chương {chap_num} tại {chap_dir}")
            continue

        raw_text = loader.load_raw_chapter_content(chap_dir)
        vi_path = chap_dir / "content_vi.txt"
        if not vi_path.exists():
            logger.warning(f"Không tìm thấy content_vi.txt tại {vi_path}")
            continue

        with open(vi_path, "r", encoding="utf-8") as f:
            full_vi = f.read().strip().split("\n\n", 1)

        translated_title = full_vi[0] if len(full_vi) > 0 else ""
        translated_text = full_vi[1] if len(full_vi) > 1 else full_vi[0]

        logger.info(f"\n──────────────────────────────────────────────────")
        logger.info(f"🛠️  Đang chạy QC Chuyên sâu cho [bold cyan]{item['chapter']}[/bold cyan]...")

        t_start = time.time()
        qc_out, final_title, final_content, citation_mismatch = await qc_auditor.audit_translation(
            chapter_num=chap_num,
            raw_text=raw_text,
            translated_title=translated_title,
            translated_text=translated_text
        )

        # Hard sanitation check
        final_content, stripped_content_chars = extract_and_strip_chinese(final_content)
        final_title, stripped_title_chars = extract_and_strip_chinese(final_title)
        all_stripped = list(set(stripped_content_chars + stripped_title_chars))

        t_duration = time.time() - t_start

        if not citation_mismatch and not all_stripped:
            # Audit successful & clean!
            final_file_text = f"{final_title}\n\n{final_content}"
            loader.save_translated_chapter(chap_dir, final_file_text)

            fixed_chapters.append(key)
            audit_results.append({
                "chapter": item["chapter"],
                "status": "FIXED & PASSED ✅",
                "qc_score": f"{qc_out.qc_score}/10.0",
                "detail": "Đã khớp exact-match và sửa mượt câu thành công."
            })
            logger.info(f"✅ [{item['chapter']}] Audit thành công & đã sửa file: Điểm {qc_out.qc_score}/10.0 ({t_duration:.1f}s)")
        else:
            audit_results.append({
                "chapter": item["chapter"],
                "status": "RETAINED STAGE 1 ⚠️",
                "qc_score": f"{qc_out.qc_score}/10.0",
                "detail": "Vẫn còn chệch trích dẫn. Đã bảo toàn 100% bản dịch Stage 1."
            })
            logger.warning(f"⚠️ [{item['chapter']}] Chưa match được trích dẫn -> Bảo toàn bản dịch Stage 1 ({t_duration:.1f}s)")

    # Update manual_audit_report.json and txt removing fixed chapters
    for key in fixed_chapters:
        if key in audit_data:
            del audit_data[key]

    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)

    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write("⚠️ BÁO CÁO CÁC CHƯƠNG CẦN AUDIT THỦ CÔNG ⚠️\n")
        f.write("==================================================\n\n")
        if audit_data:
            for k in sorted(audit_data.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else x):
                it = audit_data[k]
                f.write(f"[{it['chapter']}] Lý do: {it['reason']}\n")
                f.write(f"   ├─ Chi tiết: {it['detail']}\n\n")
        else:
            f.write("🎉 Tất cả các chương đã được Audit và làm sạch 100%!\n")

    # Display report table
    table = Table(title="📊 KẾT QUẢ RÀ SOÁT QC CHUYÊN SÂU (TARGETED AUDIT)", show_header=True, header_style="bold magenta")
    table.add_column("Chương", style="cyan", width=12)
    table.add_column("Điểm QC", justify="center", style="green", width=12)
    table.add_column("Trạng thái Audit", justify="center", width=20)
    table.add_column("Chi tiết", style="white")

    for res in audit_results:
        table.add_row(res["chapter"], res["qc_score"], res["status"], res["detail"])

    console.print("\n")
    console.print(table)
    console.print("\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Targeted QC Audit Runner - Chạy rà soát QC cho danh sách Manual Audit")
    parser.add_argument("--source", type=str, required=True, help="Đường dẫn thư mục Local Dataset")
    args = parser.parse_args()

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_targeted_audit(args.source))

if __name__ == "__main__":
    main()

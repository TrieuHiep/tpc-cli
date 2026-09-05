import time
import json
import re
from pathlib import Path
from typing import Dict, Any, List

from app.config import config
from app.core.openrouter import OpenRouterClient
from app.services.local_loader import LocalLoaderService
from app.services.glossary import GlossaryService
from app.services.checkpoint import CheckpointManager
from app.services.translator import TranslatorService
from app.services.qc_auditor import QCAuditorService
from app.services.gdrive import GoogleDriveService
from app.utils.archiver import zip_translated_chapters
from app.utils.text_cleaner import clean_plain_text, contains_chinese, extract_and_strip_chinese
from app.utils.logger import logger, console
from rich.table import Table

MAX_CHINESE_CLEANUP_RETRIES = 2

class TranslationPipeline:
    """Master Pipeline executing the 5-step translation workflow with Step Timing & Checkpoint Recovery."""

    def __init__(self, dataset_path: str, retranslate: bool = False):
        self.loader = LocalLoaderService(dataset_path, retranslate=retranslate)
        self.glossary_service = GlossaryService(self.loader.dataset_dir)
        self.checkpoint = CheckpointManager(self.loader.dataset_dir)
        
        self.llm_client = OpenRouterClient()
        self.translator = TranslatorService(self.llm_client)
        self.qc_auditor = QCAuditorService(self.llm_client)

    async def close(self):
        """Closes LLM client connections cleanly."""
        if hasattr(self, 'llm_client') and self.llm_client:
            await self.llm_client.close()

    async def run(self, max_chapters: int = 5, resume: bool = False, upload_gdrive: bool = False, cleanup_after: bool = True, selected_chapters: set = None) -> List[Dict[str, Any]]:
        """Executes the pipeline for available chapters with detailed step timing, supporting selected chapters filtering."""
        info = self.loader.load_info()
        novel_title = info.get("title", self.loader.dataset_dir.name)
        raw_genre = info.get("genre") or info.get("genres") or info.get("category") or ""
        if isinstance(raw_genre, list):
            novel_genre = ", ".join(str(g) for g in raw_genre)
        else:
            novel_genre = str(raw_genre).strip()
        novel_tags = info.get("tags") or []
        if isinstance(novel_tags, str):
            novel_tags = [t.strip() for t in novel_tags.split(",") if t.strip()]
        
        logger.info(f"🚀 Bắt đầu Pipeline Dịch Truyện: [bold gold1]{novel_title}[/bold gold1]")
        if novel_genre:
            logger.info(f"🎭 Thể loại: [cyan]{novel_genre}[/cyan] | Tags: [cyan]{novel_tags}[/cyan]")
        chapters = self.loader.get_available_chapters()

        if not chapters:
            logger.error("Không tìm thấy chương nào trong thư mục chapters!")
            return []

        processed_chapters = 0
        results = []
        manual_audit_list = []

        for chap_num, chap_dir in chapters:
            # Nếu người dùng chỉ định danh sách chương cụ thể: Bỏ qua các chương không nằm trong danh sách
            if selected_chapters is not None and chap_num not in selected_chapters:
                continue

            if max_chapters > 0 and processed_chapters >= max_chapters:
                logger.info(f"Đã đạt giới hạn max_chapters={max_chapters}, tạm dừng pipeline.")
                break

            # Chỉ áp dụng skip check tự động khi chạy tuần tự thông thường (không chỉ định đích danh selected_chapters)
            if selected_chapters is None:
                if (resume and self.checkpoint.is_step_completed(chap_num, "COMMITTED")) or self.loader.is_chapter_translated(chap_dir):
                    logger.info(f"⏩ Chương {chap_num:02d} đã hoàn thành trước đó (đã có content_vi.txt), tự động bỏ qua.")
                    continue

            chap_start_time = time.time()
            logger.info(f"\n==================================================")
            logger.info(f"📖 BẮT ĐẦU XỬ LÝ CHƯƠNG {chap_num:02d}")
            logger.info(f"==================================================")

            try:
                # BƯỚC 1: Nạp Dữ Liệu Đầu Vào
                t0 = time.time()
                raw_text = self.loader.load_raw_chapter_content(chap_dir)
                self.checkpoint.update_checkpoint(chap_num, "INGESTED")
                t1 = time.time()
                logger.info(f"⏱️  [Bước 1] Nạp dữ liệu thô: [green]{(t1 - t0):.3f}s[/green] ({len(raw_text)} chars)")

                # BƯỚC 2: Dynamic Glossary Filtering & Context (Lọc bối cảnh diễn ra trước chương hiện tại)
                filtered_glossary = self.glossary_service.filter_glossary_for_text(raw_text)
                summary_context = self.glossary_service.load_summary(last_n=config.SUMMARY_LAST_N, before_chapter=chap_num)
                self.checkpoint.update_checkpoint(chap_num, "GLOSSARY_SLOTTED")
                t2 = time.time()
                logger.info(f"⏱️  [Bước 2] Lọc Glossary ({len(filtered_glossary)} terms): [green]{(t2 - t1):.3f}s[/green]")

                # BƯỚC 3: Dịch thuật & Biên tập Mượt (Stage 1 LLM Call)
                t_trans_start = time.time()
                trans_out = await self.translator.translate_chapter(
                    chapter_num=chap_num,
                    raw_text=raw_text,
                    filtered_glossary=filtered_glossary,
                    previous_summary=summary_context,
                    genre=novel_genre,
                    tags=novel_tags
                )
                t_trans_end = time.time()
                duration_trans = t_trans_end - t_trans_start
                self.checkpoint.update_checkpoint(chap_num, "TRANSLATED", trans_out.chapter_title_vi)
                logger.info(f"⏱️  [Bước 3] Dịch LLM Stage 1: [bold cyan]{duration_trans:.2f}s[/bold cyan]")

                # BƯỚC 4: QC Thẩm định & Làm sạch (Tùy chọn via ENABLE_QC_AUDITOR)
                if config.ENABLE_QC_AUDITOR:
                    t_qc_start = time.time()
                    qc_out, final_title, final_content, citation_mismatch = await self.qc_auditor.audit_translation(
                        chapter_num=chap_num,
                        raw_text=raw_text,
                        translated_title=trans_out.chapter_title_vi,
                        translated_text=trans_out.translated_content
                    )
                    t_qc_end = time.time()
                    duration_qc = t_qc_end - t_qc_start
                    self.checkpoint.update_checkpoint(chap_num, "QC_AUDITED", final_title)
                    logger.info(f"⏱️  [Bước 4] QC Audit Stage 2: [bold cyan]{duration_qc:.2f}s[/bold cyan]")

                    if citation_mismatch:
                        manual_audit_list.append({
                            "chapter": f"Chương {chap_num:02d}",
                            "reason": "QC Citation Mismatch",
                            "detail": "Trích dẫn không khớp exact-match. Đã fallback bảo toàn 100% bản dịch Stage 1."
                        })
                else:
                    # Chế độ Fast Industrial Mode: Bỏ qua LLM QC Auditor, dùng Python Sanitizer siêu tốc
                    final_title = clean_plain_text(trans_out.chapter_title_vi)
                    final_content = clean_plain_text(trans_out.translated_content)
                    duration_qc = 0.0
                    qc_out = None
                    citation_mismatch = False
                    self.checkpoint.update_checkpoint(chap_num, "QC_AUDITED", final_title)
                    logger.info(f"⏩ [Bước 4] Fast Mode: Bỏ qua LLM QC Auditor, Python Regex làm sạch trong 0.001s.")

                # BƯỚC 4.5: Auto-Retry Chinese Cleanup (nếu phát hiện còn sót chữ Hán)
                cleanup_retries = 0
                while contains_chinese(final_content) or contains_chinese(final_title):
                    cleanup_retries += 1
                    if cleanup_retries > MAX_CHINESE_CLEANUP_RETRIES:
                        logger.error(
                            f"🚨 [CRITICAL] Chương {chap_num} vẫn còn chữ Hán sau {MAX_CHINESE_CLEANUP_RETRIES} lần retry! "
                            f"Kích hoạt Hard Sanitation (Regex)..."
                        )
                        break

                    logger.warning(
                        f"⚠️ [Auto-Retry {cleanup_retries}/{MAX_CHINESE_CLEANUP_RETRIES}] "
                        f"Chương {chap_num} còn sót chữ Hán — Gửi LLM dọn sạch..."
                    )
                    cleanup_result = await self.translator.fix_remaining_chinese(
                        chapter_num=chap_num,
                        title=final_title,
                        content=final_content,
                        filtered_glossary=filtered_glossary
                    )
                    final_title = clean_plain_text(cleanup_result.cleaned_title)
                    final_content = clean_plain_text(cleanup_result.cleaned_content)

                    if not contains_chinese(final_content) and not contains_chinese(final_title):
                        logger.info(
                            f"✅ [Auto-Retry] Chương {chap_num} đã sạch 100% chữ Hán sau {cleanup_retries} lần retry."
                        )

                # BƯỚC 4.6: HARD SANITATION (Lưới lọc Python Regex dọn Hán tự cứng ở bước chốt hạ)
                final_content, stripped_content_chars = extract_and_strip_chinese(final_content)
                final_title, stripped_title_chars = extract_and_strip_chinese(final_title)
                all_stripped_chars = list(set(stripped_content_chars + stripped_title_chars))

                if all_stripped_chars:
                    logger.warning(
                        f"🛡️ [Hard Sanitation] Chương {chap_num}: Python Regex đã xóa cứng {len(all_stripped_chars)} chữ Hán: "
                        f"{all_stripped_chars}"
                    )
                    manual_audit_list.append({
                        "chapter": f"Chương {chap_num:02d}",
                        "reason": "Hard-stripped Chinese Chars",
                        "detail": f"Regex đã xóa cứng các ký tự Hán: {all_stripped_chars}"
                    })

                # BƯỚC 5: Commit Sản Phẩm & Cập nhật State
                t5_start = time.time()
                final_text = f"{final_title}\n\n{final_content}"
                self.loader.save_translated_chapter(chap_dir, final_text)

                if trans_out.extracted_new_terms:
                    self.glossary_service.update_glossary(trans_out.extracted_new_terms)
                    logger.info(f"📚 Đã cập nhật [cyan]{len(trans_out.extracted_new_terms)}[/cyan] thuật ngữ mới từ Chương {chap_num}: {trans_out.extracted_new_terms}")
                if trans_out.chapter_summary:
                    self.glossary_service.append_summary(chap_num, trans_out.chapter_summary)

                self.checkpoint.update_checkpoint(chap_num, "COMMITTED", final_title)
                t5_end = time.time()
                logger.info(f"⏱️  [Bước 5] Ghi file & Commit State: [green]{(t5_end - t5_start):.3f}s[/green]")

                chap_total_duration = time.time() - chap_start_time
                retry_info = f" (+ {cleanup_retries} cleanup retries)" if cleanup_retries > 0 else ""
                logger.info(
                    f"🎉 [Hoàn thành Chương {chap_num:02d}] Tổng thời gian: [bold magenta]{chap_total_duration:.2f}s[/bold magenta] "
                    f"(Dịch: {duration_trans:.1f}s | QC: {duration_qc:.1f}s{retry_info})"
                )

                status_str = "PASSED ✅"
                if citation_mismatch or all_stripped_chars:
                    status_str = "AUDIT NEEDED ⚠️"
                elif qc_out and qc_out.status != "PASSED":
                    status_str = "WARNING ⚠️"

                qc_score_display = f"{qc_out.qc_score} / 10.0" if qc_out else "Cleaned (Regex)"

                results.append({
                    "chapter": f"Chương {chap_num:02d}",
                    "title": final_title,
                    "qc_score": qc_score_display,
                    "status": status_str,
                    "time_trans": f"{duration_trans:.1f}s",
                    "time_qc": f"{duration_qc:.1f}s",
                    "time_total": f"{chap_total_duration:.1f}s"
                })
                processed_chapters += 1

            except Exception as e:
                logger.error(f"❌ Lỗi xử lý Chương {chap_num}: {e}", exc_info=True)
                break

        # In Bảng Báo cáo Audit Thủ công và ghi ra file nếu có chương bị dính cờ
        if manual_audit_list:
            audit_report_json = self.loader.dataset_dir / "manual_audit_report.json"
            audit_report_txt = self.loader.dataset_dir / "manual_audit_report.txt"

            # Load existing audit records if present
            existing_audit = {}
            if audit_report_json.exists():
                try:
                    with open(audit_report_json, "r", encoding="utf-8") as f:
                        existing_audit = json.load(f)
                except Exception:
                    existing_audit = {}

            for item in manual_audit_list:
                existing_audit[item["chapter"]] = item

            # Save updated json report
            with open(audit_report_json, "w", encoding="utf-8") as f:
                json.dump(existing_audit, f, ensure_ascii=False, indent=2)

            # Save updated human-readable txt report
            with open(audit_report_txt, "w", encoding="utf-8") as f:
                f.write("==================================================\n")
                f.write("⚠️ BÁO CÁO CÁC CHƯƠNG CẦN AUDIT THỦ CÔNG ⚠️\n")
                f.write("==================================================\n\n")
                for k in sorted(existing_audit.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else x):
                    item = existing_audit[k]
                    f.write(f"[{item['chapter']}] Lý do: {item['reason']}\n")
                    f.write(f"   ├─ Chi tiết: {item['detail']}\n\n")

            logger.info(f"📌 Đã cập nhật Báo cáo Audit Thủ công tại: [yellow]{audit_report_json}[/yellow]")

            audit_table = Table(title="⚠️ BÁO CÁO CÁC CHƯƠNG CẦN AUDIT THỦ CÔNG ⚠️", style="bold yellow")
            audit_table.add_column("Chương", style="cyan", justify="center")
            audit_table.add_column("Lý do Audit", style="bold red")
            audit_table.add_column("Chi tiết", style="white")

            for item in manual_audit_list:
                audit_table.add_row(item["chapter"], item["reason"], item["detail"])

            console.print("\n")
            console.print(audit_table)
            console.print("\n")

        # BƯỚC CHỐT HẠ: Gom nén tất cả các chương đã dịch thành translated_chapters.zip
        zip_path = zip_translated_chapters(self.loader.dataset_dir)

        # Tải / Ghi đè file nén và metadata lên Google Drive nếu được yêu cầu
        if upload_gdrive:
            try:
                logger.info("\n🚀 Bắt đầu quá trình tải/ghi đè bản dịch và metadata lên Google Drive...")
                gdrive_service = GoogleDriveService()
                repo_key, story_id, root_folder_id = gdrive_service.detect_repo_info(self.loader.dataset_dir)
                story_folder_id = gdrive_service.get_or_create_story_folder(root_folder_id, story_id)
                
                # 1. Upload file nén bản dịch nếu có
                if zip_path:
                    drive_link = gdrive_service.upload_or_update_file(zip_path, story_folder_id, "translated_chapters.zip")
                    if drive_link:
                        logger.info(f"🌐 [Google Drive Link] Bản dịch đã được cập nhật thành công tại:\n[bold green]{drive_link}[/bold green]\n")
                
                # 2. Upload các file metadata (summary.txt, glossary.json, checkpoints.json)
                meta_links = gdrive_service.upload_story_metadata(self.loader.dataset_dir, story_folder_id)
                if meta_links:
                    logger.info(f"📚 Đã đồng bộ {len(meta_links)} files metadata lên Google Drive cho truyện [cyan]{story_id}[/cyan].")
            except Exception as e:
                logger.error(f"❌ Lỗi khi tải dữ liệu lên Google Drive: {e}", exc_info=True)

        # Tự động dọn dẹp thư mục chapters/ giải nén để giữ ổ cứng luôn gọn gàng
        if cleanup_after:
            self.loader.cleanup_extracted_chapters()

        return results



from typing import Tuple, List
from app.core.openrouter import OpenRouterClient
from app.core.prompts import QC_AUDITOR_SYSTEM_PROMPT
from app.models.schema import QCOutput
from app.config import config
from app.utils.text_cleaner import clean_plain_text, contains_chinese
from app.utils.logger import logger

class QCAuditorService:
    """Service wrapping Stage 2 QC Audit & Targeted Sentence Auto-Fixing."""

    def __init__(self, llm_client: OpenRouterClient):
        self.llm_client = llm_client

    async def audit_translation(
        self,
        chapter_num: int,
        raw_text: str,
        translated_title: str,
        translated_text: str
    ) -> Tuple[QCOutput, str, str, bool]:
        """Executes lightweight LLM QC Audit Call and applies targeted sentence fixes.
        Returns: (QCOutput, final_clean_title, final_clean_content, citation_mismatch)
        """
        logger.info(f"🔍 [Stage 2] Bắt đầu Thẩm định QC & Rà soát Hán tự/HTML Chương {chapter_num}...")

        base_prompt = f"""DƯỚI ĐÂY LÀ BẢN THÔ VÀ BẢN DỊCH CHƯƠNG {chapter_num}:

--- BẢN THÔ TIẾNG TRUNG ---
{raw_text}

--- BẢN DỊCH TIẾNG VIỆT (CẦN KIỂM ĐỊNH QC) ---
Tiêu đề: {translated_title}

{translated_text}
"""

        user_prompt = base_prompt
        max_qc_retries = 2
        attempt = 0
        citation_mismatch = False

        while attempt <= max_qc_retries:
            attempt += 1
            step_label = f"QC Audit Stage 2 (Chương {chapter_num})"
            if attempt > 1:
                step_label += f" - Retry {attempt - 1}"

            try:
                qc_res = await self.llm_client.call_llm_json(
                    system_prompt=QC_AUDITOR_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=QCOutput,
                    temperature=config.TEMPERATURE_QC,
                    step_name=step_label
                )
            except Exception as qc_err:
                logger.warning(
                    f"⚠️ [QC Graceful Fallback] Chương {chapter_num}: Không thể chạy QC Audit do lỗi API/JSON ({qc_err}). "
                    f"Tự động bảo toàn 100% bản dịch mượt Stage 1 và đánh dấu AUDIT NEEDED."
                )
                fallback_qc = QCOutput(
                    qc_score=8.5,
                    status="PASSED_FALLBACK",
                    has_chinese_characters=False,
                    has_html_tags=False,
                    issues=[]
                )
                final_title = clean_plain_text(translated_title)
                final_content = clean_plain_text(translated_text)
                return fallback_qc, final_title, final_content, True

            if not qc_res.issues:
                # Không có lỗi nào được phát hiện -> PASSED
                final_title = clean_plain_text(translated_title)
                final_content = clean_plain_text(translated_text)
                return qc_res, final_title, final_content, False

            # Kiểm tra exact match cho từng issue
            unmatched_issues = []
            for issue in qc_res.issues:
                orig = issue.original_sentence.strip() if issue.original_sentence else ""
                if not orig:
                    continue
                if (orig not in translated_text) and (orig not in translated_title):
                    unmatched_issues.append(orig)

            if not unmatched_issues:
                # Tất cả trích dẫn đều match exact match 100%
                final_content = translated_text
                final_title = translated_title
                for issue in qc_res.issues:
                    orig = issue.original_sentence.strip()
                    corr = issue.corrected_sentence.strip() if issue.corrected_sentence else ""
                    # Chỉ thay thế khi câu trích dẫn đủ dài (ít nhất 4 từ) để tránh thay thế nhầm cụm từ ngắn
                    if len(orig.split()) >= 4:
                        if orig in final_content:
                            final_content = final_content.replace(orig, corr, 1)
                        elif orig in final_title:
                            final_title = final_title.replace(orig, corr, 1)
                    else:
                        logger.warning(f"⚠️ [QC Skip] Trích dẫn '{orig}' quá ngắn (< 4 từ), bỏ qua để tránh lỗi ngữ cảnh.")

                final_content = clean_plain_text(final_content)
                final_title = clean_plain_text(final_title)

                has_chinese = contains_chinese(final_content) or contains_chinese(final_title)
                qc_res.has_chinese_characters = has_chinese
                qc_res.has_html_tags = False

                logger.info(
                    f"📊 [QC Result] Chương {chapter_num} | Điểm QC: [bold green]{qc_res.qc_score}/10.0[/bold green] | "
                    f"Trạng thái: [bold yellow]{qc_res.status}[/bold yellow] (Exact Match Success)"
                )
                return qc_res, final_title, final_content, False

            # Nếu có trích dẫn không khớp exact match
            logger.warning(
                f"⚠️ [QC Citation Mismatch] Lần {attempt}/{max_qc_retries + 1}: phát hiện {len(unmatched_issues)} trích dẫn "
                f"không khớp exact match trong bản dịch gốc: {unmatched_issues[:2]}"
            )

            if attempt <= max_qc_retries:
                # Chuẩn bị prompt nhắc nhở LLM trích dẫn chính xác
                feedback_msg = (
                    f"\n\n🚨 [LỖI TRÍCH DẪN Ở LẦN THỬ TRƯỚC]:\n"
                    f"Các câu trích dẫn `original_sentence` sau đây CỦA BẠN KHÔNG KHỚP EXACT MATCH 100% trong bản dịch gốc:\n"
                    + "\n".join(f"- \"{s}\"" for s in unmatched_issues) +
                    f"\n\nYÊU CẦU LÀM LẠI: Chỉ trích dẫn đúng 1 câu đơn (dưới 20 từ) CÓ SẴN NGUYÊN VĂN trong bản dịch."
                )
                user_prompt = base_prompt + feedback_msg
            else:
                # Đã thử hết số lần retry nhưng vẫn không match exact -> FALLBACK về bản dịch gốc Stage 1
                logger.error(
                    f"🚨 [QC Fallback] Chương {chapter_num}: Sau {max_qc_retries} lần retry, QC vẫn không khớp exact match. "
                    f"Bảo toàn 100% bản dịch gốc Stage 1 và đánh dấu MANUAL AUDIT."
                )
                citation_mismatch = True
                final_title = clean_plain_text(translated_title)
                final_content = clean_plain_text(translated_text)
                return qc_res, final_title, final_content, True

        final_title = clean_plain_text(translated_title)
        final_content = clean_plain_text(translated_text)
        return qc_res, final_title, final_content, True


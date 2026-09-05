import json
from typing import Dict, List, Optional

from app.core.openrouter import OpenRouterClient
from app.core.prompts import TRANSLATOR_SYSTEM_PROMPT, CHINESE_CLEANUP_SYSTEM_PROMPT
from app.models.schema import TranslationOutput, ChineseCleanupOutput
from app.config import config
from app.utils.logger import logger

class TranslatorService:
    """Service wrapping Stage 1 Translation & Smoothing LLM Call."""

    def __init__(self, llm_client: OpenRouterClient):
        self.llm_client = llm_client

    async def translate_chapter(
        self,
        chapter_num: int,
        raw_text: str,
        filtered_glossary: Dict[str, str],
        previous_summary: str,
        genre: str = "",
        tags: Optional[List[str]] = None
    ) -> TranslationOutput:
        """Executes LLM Translation Call with Genre-Adaptive Tone Guidance & Fallback."""
        logger.info(f"⚡ [Stage 1] Bắt đầu Dịch & Biên tập mượt Chương {chapter_num} via {config.MODEL_NAME}...")
        
        genre_info = genre.strip() if genre else "Chưa xác định (Áp dụng văn phong trung hòa: Giữ Hán Việt cho thuật ngữ/xưng hô, thuần Việt cho lời thoại & hành động)"
        tags_info = ", ".join(tags) if tags else "Không có"

        user_prompt = f"""DƯỚI ĐÂY LÀ NỘI DUNG VÀ NGỮ CẢNH CHƯƠNG {chapter_num}:

--- THÔNG TIN THỂ LOẠI & ĐỊNH HƯỚNG VĂN PHONG ---
Thể loại: {genre_info}
Tags: {tags_info}

--- BẢNG THUẬT NGỮ GLOSSARY THAM CHIẾU ---
{json.dumps(filtered_glossary, ensure_ascii=False, indent=2)}

--- TÓM TẮT DIỄN BIẾN CÁC CHƯƠNG TRƯỚC ---
{previous_summary if previous_summary else "Chưa có tóm tắt trước đó (Chương đầu tiên)."}

--- NỘI DUNG CHƯƠNG THÔ TIẾNG TRUNG/CONVERT ---
{raw_text}
"""
        
        result = await self.llm_client.call_llm_json(
            system_prompt=TRANSLATOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=TranslationOutput,
            temperature=config.TEMPERATURE_TRANSLATOR,
            step_name=f"Dịch Stage 1 (Chương {chapter_num})"
        )
        
        logger.info(f"✅ [Stage 1] Đã dịch xong Chương {chapter_num}: [bold cyan]{result.chapter_title_vi}[/bold cyan]")
        return result

    async def fix_remaining_chinese(
        self,
        chapter_num: int,
        title: str,
        content: str,
        filtered_glossary: Dict[str, str]
    ) -> ChineseCleanupOutput:
        """Targeted LLM call to translate any remaining Chinese characters in an already-translated text."""
        logger.info(f"🔄 [Chinese Cleanup] Chương {chapter_num} — Gửi LLM dọn sạch chữ Hán còn sót...")

        user_prompt = f"""DƯỚI ĐÂY LÀ BẢN DỊCH TIẾNG VIỆT CỦA CHƯƠNG {chapter_num} CÒN SÓT CHỮ HÁN:

--- BẢNG THUẬT NGỮ THAM CHIẾU ---
{json.dumps(filtered_glossary, ensure_ascii=False, indent=2)}

--- TIÊU ĐỀ ---
{title}

--- NỘI DUNG BẢN DỊCH (CÒN SÓT CHỮ HÁN) ---
{content}
"""

        result = await self.llm_client.call_llm_json(
            system_prompt=CHINESE_CLEANUP_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ChineseCleanupOutput,
            temperature=config.TEMPERATURE_QC,
            step_name=f"Dọn Hán Tự (Chương {chapter_num})"
        )

        logger.info(f"✅ [Chinese Cleanup] Chương {chapter_num} — Đã hoàn tất dọn sạch chữ Hán.")
        return result


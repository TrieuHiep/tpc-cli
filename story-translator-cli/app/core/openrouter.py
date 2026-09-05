import json
import re
import sys
import time
import asyncio
from typing import Dict, Any, Type, TypeVar
from pydantic import BaseModel
from openai import AsyncOpenAI

from app.config import config
from app.utils.logger import logger, console

T = TypeVar("T", bound=BaseModel)

from json_repair import repair_json

def truncate_text(text: str, max_len: int = 150) -> str:
    """Helper to clean newlines and truncate long text with ..."""
    if not text:
        return ""
    clean = " ".join(text.split())
    if len(clean) > max_len:
        return clean[:max_len] + "..."
    return clean

def sanitize_json_text(text: str) -> str:
    """Cleans control characters and extracts json block from LLM output."""
    if not text:
        return "{}"
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text.strip())
    
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
        
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text

class OpenRouterClient:
    def __init__(self, override_model: str = None):
        if not config.OPENROUTER_API_KEY or "YOUR_OPENROUTER_API_KEY" in config.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY chưa được cấu hình trong file .env!")
        
        self.client = AsyncOpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://github.com/antigravity",
                "X-Title": "Story Translator CLI"
            }
        )
        self.model = override_model if override_model else config.MODEL_NAME

    async def close(self):
        """Closes the underlying AsyncOpenAI httpx/httpcore connection pool cleanly."""
        if hasattr(self, 'client') and self.client:
            try:
                await self.client.close()
            except Exception:
                pass

    async def call_llm_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: float = 0.3,
        max_retries: int = 3,
        step_name: str = "LLM"
    ) -> T:
        """Call OpenRouter API with max_tokens & max_completion_tokens for 100% API spec compliance."""
        sys_snippet = truncate_text(system_prompt, 100)
        user_snippet = truncate_text(user_prompt, 140)

        extra_body = {
            "reasoning": {
                "enabled": config.REASONING_ENABLED
            }
        }
        if config.PREFERRED_PROVIDER:
            extra_body["provider"] = {
                "order": [config.PREFERRED_PROVIDER],
                "allow_fallbacks": True
            }

        logger.info(f"📤 [{step_name}] Requesting {self.model} (temp={temperature})...")
        logger.info(f"   ├─ Prompt: {user_snippet}")

        retries = 0
        current_temp = temperature
        while retries < max_retries:
            start_time = time.time()
            last_log_time = start_time
            chunks = []
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=current_temp,
                    max_tokens=config.MAX_TOKENS,
                    stream=True,
                    timeout=180.0,
                    extra_body=extra_body if extra_body else None
                )

                try:
                    if sys.stdout.isatty():
                        with console.status(f"[bold cyan]⏳ [{step_name}] Đang xử lý...[/bold cyan]") as status:
                            async for chunk in response:
                                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                    delta = chunk.choices[0].delta.content
                                    chunks.append(delta)
                                    now = time.time()
                                    if now - last_log_time >= 3.0:
                                        last_log_time = now
                                        total_chars = sum(len(c) for c in chunks)
                                        elapsed_current = now - start_time
                                        status.update(
                                            f"[bold cyan]⏳ [{step_name}] Đang sinh phản hồi...[/bold cyan] | "
                                            f"Đã sinh: [bold yellow]{total_chars:,} chars[/bold yellow] | "
                                            f"Thời gian: [bold green]{elapsed_current:.1f}s[/bold green]"
                                        )
                    else:
                        async for chunk in response:
                            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                delta = chunk.choices[0].delta.content
                                chunks.append(delta)
                                now = time.time()
                                if now - last_log_time >= 10.0:
                                    last_log_time = now
                                    total_chars = sum(len(c) for c in chunks)
                                    elapsed_current = now - start_time
                                    logger.info(
                                        f"⏳ [{step_name}] Đang sinh phản hồi... ({total_chars:,} chars | {elapsed_current:.1f}s)"
                                    )
                finally:
                    try:
                        await response.close()
                    except Exception:
                        pass

                raw_content = "".join(chunks)
                elapsed = time.time() - start_time

                if not raw_content.strip():
                    raise ValueError("Nội dung phản hồi từ LLM rỗng (None).")

                out_snippet = truncate_text(raw_content, 180)
                logger.info(
                    f"📥 [LLM Response Complete] Thời gian: [bold green]{elapsed:.2f}s[/bold green] | "
                    f"Kích thước: [yellow]{len(raw_content)} chars[/yellow]"
                )
                logger.info(f"   └─ [Output Preview]: {out_snippet}")

                clean_raw = sanitize_json_text(raw_content)

                data_dict = None
                try:
                    data_dict = json.loads(clean_raw)
                except Exception:
                    try:
                        data_dict = json.loads(clean_raw, strict=False)
                    except Exception:
                        logger.warning(f"🔧 [{step_name}] JSON Decode tiêu chuẩn thất bại -> Kích hoạt json_repair vá cú pháp...")
                        repaired = repair_json(clean_raw, return_objects=True)
                        if isinstance(repaired, dict):
                            data_dict = repaired
                        elif isinstance(repaired, str):
                            data_dict = json.loads(repaired)

                if not data_dict or not isinstance(data_dict, dict):
                    repaired_raw = repair_json(raw_content, return_objects=True)
                    if isinstance(repaired_raw, dict):
                        data_dict = repaired_raw
                    else:
                        raise ValueError("Không thể parse JSON từ phản hồi LLM dù đã thử json_repair.")

                return response_model.model_validate(data_dict)

            except Exception as e:
                elapsed = time.time() - start_time
                retries += 1
                logger.warning(f"⚠️ [OpenRouter Warning] Lỗi ({elapsed:.2f}s) Thử lại ({retries}/{max_retries}) - {e}")
                if retries >= max_retries:
                    raise e
                current_temp = 0.0  # Giảm temperature về 0.0 để LLM sinh JSON chắc chắn hơn ở đợt thử tiếp theo
                await asyncio.sleep(0.5)

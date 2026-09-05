import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    MODEL_NAME: str = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
    PREFERRED_PROVIDER: str = os.getenv("PREFERRED_PROVIDER", "StreamLake")
    TEMPERATURE_TRANSLATOR: float = float(os.getenv("TEMPERATURE_TRANSLATOR", "0.3"))
    TEMPERATURE_QC: float = float(os.getenv("TEMPERATURE_QC", "0.1"))
    MAX_TOKENS: Optional[int] = int(os.getenv("MAX_TOKENS")) if os.getenv("MAX_TOKENS") else 65536
    REASONING_ENABLED: bool = os.getenv("REASONING_ENABLED", "false").lower() == "true"
    ENABLE_QC_AUDITOR: bool = os.getenv("ENABLE_QC_AUDITOR", "false").lower() == "true"
    SUMMARY_LAST_N: int = int(os.getenv("SUMMARY_LAST_N", "15"))

config = Config()

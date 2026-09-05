"""
Configuration module for AGY Monitor Service.
Đọc cấu hình từ file .env ở thư mục gốc của dự án.
"""
import os
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent

# Thư mục chứa Brain của Antigravity CLI (cross-platform)
BRAIN_DIR = Path.home() / ".gemini" / "antigravity-cli" / "brain"

# Thư mục tạm của daemon dịch (nếu có)
TEMP_DIR = BASE_DIR / "storage" / "temp"

# Thư mục log
LOGS_DIR = BASE_DIR / "logs"


def _load_env_file() -> dict:
    env_file = BASE_DIR / ".env"
    env_vars = {}
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return env_vars


_env = _load_env_file()

# Telegram Credentials
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or _env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or _env.get("TELEGRAM_CHAT_ID", "")

# Topic chuyên biệt dành cho AGY Monitoring
_topic_str = (
    os.environ.get("TELEGRAM_MONITOR_TOPIC_ID")
    or _env.get("TELEGRAM_MONITOR_TOPIC_ID")
    or os.environ.get("TELEGRAM_TOPIC_ID")
    or _env.get("TELEGRAM_TOPIC_ID")
    or ""
)
TELEGRAM_MONITOR_TOPIC_ID = int(_topic_str) if _topic_str.isdigit() else None


def _find_agy_binary() -> str:
    """Tự động tìm kiếm đường dẫn thực thi của Antigravity CLI (agy)."""
    import shutil

    # 1. Ưu tiên biến môi trường hoặc .env
    custom = os.environ.get("AGY_BIN_PATH") or _env.get("AGY_BIN_PATH", "")
    if custom:
        expanded = Path(custom).expanduser()
        if expanded.exists():
            return str(expanded)
        return custom

    # 2. Tìm trong PATH hiện tại
    which_path = shutil.which("agy")
    if which_path:
        return which_path

    # 3. Quét các vị trí mặc định thông dụng (Linux, macOS, Windows)
    home = Path.home()
    candidates = [
        home / ".local" / "bin" / "agy",
        home / "bin" / "agy",
        home / ".npm-global" / "bin" / "agy",
        home / ".cargo" / "bin" / "agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
        home / "AppData" / "Roaming" / "npm" / "agy.cmd",
        home / ".local" / "bin" / "agy.exe",
    ]
    for c in candidates:
        if c.exists() and (os.access(c, os.X_OK) or os.name == "nt"):
            return str(c)

    return "agy"


AGY_BIN = _find_agy_binary()


"""
Configuration module for Auto Translator Daemon.
"""
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent

# Đọc cấu hình từ file .env (nếu có)
def _load_env_file():
    env_file = BASE_DIR / ".env"
    env_vars = {}
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8', errors='ignore').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars

_env = _load_env_file()

# Thư mục lưu trữ dữ liệu truyện cục bộ
STORAGE_DIR = BASE_DIR / "storage"

# Thư mục chứa log từng phiên dịch
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Thư mục lưu trữ các truyện lỗi để phục vụ kiểm tra/debug
TEMP_FAILED_DIR = STORAGE_DIR / "temp_failed"
TEMP_FAILED_DIR.mkdir(parents=True, exist_ok=True)

# Thư mục chứa file xác thực Google Drive
CONF_DIR = BASE_DIR / "story-translator-cli" / "conf"

# ID thư mục gốc của các nguồn trên Google Drive
DRIVE_FOLDERS = {
    "ixdzs8": "1biCwkUl5IT1R0C-CrZsRpgQkFAX-vE3c",
    "truyendichwiki": "1c1W2OYlO8s06DVK3PkLPbi8hkdynGLrc",
    "novel543": "1sulNp0yvLx8G04Uod0KAYPemGSNOsEBP"
}

# Cấu hình danh sách các Tab trên Google Sheet và Độ Ưu Tiên (Priority Ranking):
# - priority: Số càng nhỏ thì càng được ưu tiên dịch trước (1 = cao nhất, 2, 3...)
#   (Lưu ý: Nguồn ixdzs8 bypass whitelist và được gán mặc định Priority 2)
# - badge: Nhãn hiển thị trực quan trên Telegram và Terminal
# - gid: ID của từng tab trên Google Sheet
WHITELIST_TABS_CONFIG = {
    "gay": {
        "gid": "1466391364",
        "priority": 1,          # Ưu tiên số 1: Đam mỹ được đưa lên đầu hàng đợi Chặng 2
        "badge": "🌈 [ĐAM MỸ]",
        "default_source": "truyendichwiki"
    },
    "truyendichwiki": {
        "gid": "428851671",
        "priority": 3,          # Ưu tiên số 3 (sau ixdzs8 - Priority 2)
        "badge": "",
        "default_source": "truyendichwiki"
    },
    "novel543": {
        "gid": "2049787905",
        "priority": 4,          # Ưu tiên số 4
        "badge": "",
        "default_source": "novel543"
    }
}

# Thứ tự ưu tiên xử lý nguồn truyện (ixdzs8 ưu tiên cao nhất trong các kho Drive)
SOURCE_PRIORITY = ["ixdzs8", "truyendichwiki", "novel543"]

# Hạn mức tối đa số chương dịch trong 1 ngày (tránh cạn quota AGY)
DAILY_CHAPTER_LIMIT = 100

# Số chương tối đa phân bổ cho một bộ truyện trong một phiên chạy (tránh 1 bộ nuốt trọn quota)
# Giá trị 0 = không giới hạn per-story
MAX_CHAPTERS_PER_STORY = int(_env.get("MAX_CHAPTERS_PER_STORY", 25))

# Kích thước batch mặc định khi gọi skill dịch
DEFAULT_BATCH_SIZE = 10

# Thời gian timeout cho mỗi mẻ AGY CLI tính theo GIỜ (linh hoạt điều chỉnh)
TIMEOUT_HOURS = 18.0


def get_agy_timeout_str(hours: float = TIMEOUT_HOURS) -> str:
    """Chuyển đổi số giờ timeout thành chuỗi định dạng cho AGY CLI (ví dụ: '180m')."""
    return f"{int(hours * 60)}m"


# Chiến lược xử lý khi chạm trần DAILY_CHAPTER_LIMIT:
# - "ATOMIC": Chỉ nhận truyện nếu toàn bộ số chương mới <= quota còn lại (không dịch dở dang).
# - "SPLIT": Cắt đúng trần quota, chấp nhận dịch một phần chương của truyện cuối.
BOUNDARY_STRATEGY = "SPLIT"

# Ngưỡng tỷ lệ ký tự tối thiểu giữa bản dịch tiếng Việt và bản gốc tiếng Trung (kiểm tra chống cắt gọt/tóm tắt)
MIN_TRANSLATION_RATIO = 0.85

# Số lần thử lại tối đa khi AGY hoặc mạng gặp sự cố
MAX_RETRIES = 2



# Cấu hình Telegram Notification (Topic Group)
TELEGRAM_BOT_TOKEN = _env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _env.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_TOPIC_ID = int(_env.get("TELEGRAM_TOPIC_ID", 0)) if _env.get("TELEGRAM_TOPIC_ID") else None

# Cấu hình API truyện ưu tiên từ Web (Thịnh Phong Các)
WEB_PRIORITY_API_URL = _env.get(
    "WEB_PRIORITY_API_URL",
    "http://api.thinhphongcac.vn/api/v1/integration/stories/auto-translate"
)
WEB_PRIORITY_API_KEY = _env.get(
    "WEB_PRIORITY_API_KEY",
    ""
)


def _find_agy_binary() -> str:
    """Tự động tìm kiếm đường dẫn thực thi của Antigravity CLI (agy)."""
    import os
    import shutil

    custom = os.environ.get("AGY_BIN_PATH") or _env.get("AGY_BIN_PATH", "")
    if custom:
        expanded = Path(custom).expanduser()
        if expanded.exists():
            return str(expanded)
        return custom

    which_path = shutil.which("agy")
    if which_path:
        return which_path

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


"""
Configuration module for New Story Translator Daemon.
Chứa các thông số cấu hình riêng biệt phục vụ dịch mới truyện 100 chương đầu.
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

# Thư mục tạm riêng cho luồng dịch mới (độc lập với temp của auto_translator_daemon)
TEMP_NEW_DIR = STORAGE_DIR / "temp_new"
TEMP_NEW_DIR.mkdir(parents=True, exist_ok=True)

# Thư mục lưu trữ các truyện lỗi để phục vụ kiểm tra/debug
TEMP_FAILED_DIR = STORAGE_DIR / "temp_failed"
TEMP_FAILED_DIR.mkdir(parents=True, exist_ok=True)

# Thư mục chứa log từng phiên dịch mới
LOGS_DIR = BASE_DIR / "logs" / "new_stories"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Thư mục chứa file xác thực Google Drive
CONF_DIR = BASE_DIR / "story-translator-cli" / "conf"

# ID thư mục gốc của các nguồn trên Google Drive
DRIVE_FOLDERS = {
    "ixdzs8": "1biCwkUl5IT1R0C-CrZsRpgQkFAX-vE3c",
    "biquge": "1AsGs4ORz6pKR2kYLxInOkOsF0jqcvm9J",
    "truyendichwiki": "1c1W2OYlO8s06DVK3PkLPbi8hkdynGLrc",
    "novel543": "1sulNp0yvLx8G04Uod0KAYPemGSNOsEBP"
}

# Cấu hình danh sách các Tab trên Google Sheet và Độ Ưu Tiên (Priority Ranking):
# - priority: Số càng nhỏ thì càng được ưu tiên dịch trước (1 = cao nhất, 2, 3...)
#   (Lưu ý: Nguồn ixdzs8 và biquge bypass whitelist, được gán mặc định Priority 2 và 3)
# - badge: Nhãn hiển thị trực quan trên Telegram và Terminal
# - gid: ID của từng tab trên Google Sheet
WHITELIST_TABS_CONFIG = {
    "gay": {
        "gid": "1466391364",
        "priority": 1,          # Ưu tiên số 1: Đam mỹ được đưa lên đầu hàng đợi
        "badge": "🌈 [ĐAM MỸ]",
        "default_source": "truyendichwiki"
    },
    "truyendichwiki": {
        "gid": "428851671",
        "priority": 4,          # Ưu tiên số 4 (sau ixdzs8 - P2 và biquge - P3)
        "badge": "",
        "default_source": "truyendichwiki"
    },
    "novel543": {
        "gid": "2049787905",
        "priority": 5,          # Ưu tiên số 5
        "badge": "",
        "default_source": "novel543"
    }
}

# Thứ tự ưu tiên xử lý nguồn truyện (ixdzs8 -> biquge -> truyendichwiki -> novel543)
SOURCE_PRIORITY = ["ixdzs8", "biquge", "truyendichwiki", "novel543"]

# Số chương dịch cho mỗi truyện mới (chương 1 -> 100)
TARGET_CHAPTERS_PER_STORY = 100

# Kích thước hàng đợi mẻ dịch mới (10 bộ truyện)
TARGET_STORY_QUEUE_SIZE = 20

# Số worker chạy song song cùng lúc (mặc định 2 để an toàn Rate Limit)
MAX_PARALLEL_WORKERS = 2

# Kích thước batch mặc định khi gọi skill dịch (10 chương/session theo AGENTS.md)
DEFAULT_BATCH_SIZE = 10

# Thời gian timeout cho mỗi mẻ AGY CLI tính theo GIỜ
TIMEOUT_HOURS = 18.0


def get_agy_timeout_str(hours: float = TIMEOUT_HOURS) -> str:
    """Chuyển đổi số giờ timeout thành chuỗi định dạng cho AGY CLI (ví dụ: '1080m')."""
    return f"{int(hours * 60)}m"


# Ngưỡng tỷ lệ ký tự tối thiểu giữa bản dịch tiếng Việt và bản gốc tiếng Trung
MIN_TRANSLATION_RATIO = 0.85

# Số lần thử lại tối đa khi AGY hoặc mạng gặp sự cố
MAX_RETRIES = 2

# Bật/tắt bước Prompt Chaining tổng rà soát sau khi dịch xong
ENABLE_FINAL_REVIEW = bool(int(_env.get("ENABLE_FINAL_REVIEW", 1)))


# Thời gian timeout cho bước tổng rà soát tính theo GIỜ (mặc định 2 giờ)
REVIEW_TIMEOUT_HOURS = float(_env.get("REVIEW_TIMEOUT_HOURS", 2.0))


def get_agy_review_timeout_str(hours: float = REVIEW_TIMEOUT_HOURS) -> str:
    """Chuyển đổi số giờ timeout rà soát thành chuỗi định dạng cho AGY CLI (ví dụ: '120m')."""
    return f"{int(hours * 60)}m"


# Cấu hình Telegram Notification (Topic Group chuyên cho Dịch Mới Truyện)
TELEGRAM_BOT_TOKEN = _env.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _env.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_NEW_STORY_TOPIC_ID = (
    int(_env.get("TELEGRAM_NEW_STORY_TOPIC_ID", 0))
    if _env.get("TELEGRAM_NEW_STORY_TOPIC_ID")
    else (int(_env.get("TELEGRAM_TOPIC_ID", 0)) if _env.get("TELEGRAM_TOPIC_ID") else None)
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

    # Đường dẫn dự phòng trên Windows
    win_local_appdata = os.environ.get("LOCALAPPDATA", "")
    if win_local_appdata:
        win_path = Path(win_local_appdata) / "Programs" / "antigravity" / "agy.exe"
        if win_path.exists():
            return str(win_path)

    win_userprofile = os.environ.get("USERPROFILE", "")
    if win_userprofile:
        win_path2 = Path(win_userprofile) / ".gemini" / "antigravity" / "bin" / "agy.exe"
        if win_path2.exists():
            return str(win_path2)

    return "agy"


AGY_BIN = _find_agy_binary()


def format_chapter_ranges(chapters: list, arrow: str = "->", max_segments: int = 4) -> str:
    """
    Định dạng danh sách số chương thành chuỗi khoảng dễ đọc, tự động gom nhóm dải liên tục:
    - Rỗng: ""
    - 1 chương: "chap 74"
    - Liên tục: "101 -> 150"
    - Ngắt quãng/vá lỗ hổng: "chap 274, 287" hoặc "chap 173, 202 -> 224, 226 -> 248"
    """
    if not chapters:
        return ""
    sorted_nums = sorted(list(set(chapters)))
    if len(sorted_nums) == 1:
        return f"chap {sorted_nums[0]}"

    ranges = []
    start = sorted_nums[0]
    prev = sorted_nums[0]

    for num in sorted_nums[1:]:
        if num == prev + 1:
            prev = num
        else:
            ranges.append((start, prev))
            start = num
            prev = num
    ranges.append((start, prev))

    if all(s == e for s, e in ranges):
        if len(ranges) > 5:
            items = ", ".join(str(s) for s, _ in ranges[:4])
            return f"chap {items}, ... (+{len(ranges) - 4} chaps)"
        return f"chap {', '.join(str(s) for s, _ in ranges)}"

    parts = []
    for s, e in ranges:
        if s == e:
            parts.append(f"chap {s}")
        else:
            parts.append(f"{s} {arrow} {e}")

    if len(parts) > max_segments:
        return ", ".join(parts[:max_segments - 1]) + f", ... (+{len(parts) - (max_segments - 1)} dải)"

    return ", ".join(parts)

import sys
import logging
import re

STRIP_MARKUP_REGEX = re.compile(r'\[/?[a-zA-Z0-9_ =#\-]+\]')

def strip_markup(text: str) -> str:
    """Removes all Rich markup tags like [cyan], [/cyan], [bold green] from text."""
    if not isinstance(text, str):
        return str(text)
    return STRIP_MARKUP_REGEX.sub('', text)

class CleanPlainFormatter(logging.Formatter):
    """Strips Rich markup tags when logging on server/non-tty to keep text 100% clean."""
    def format(self, record):
        original_msg = record.msg
        if isinstance(record.msg, str):
            record.msg = strip_markup(record.msg)
        formatted = super().format(record)
        record.msg = original_msg
        return formatted

try:
    from rich.logging import RichHandler
    from rich.console import Console
    is_tty = sys.stdout.isatty()
    
    if is_tty:
        # Khi chạy trên Terminal tương tác: Bật markup=True để hiển thị màu sắc đẹp và soft_wrap chống co góc
        console = Console(force_terminal=True, soft_wrap=True)
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=False,
            markup=True,
            show_time=True,
            omit_repeated_times=False
        )
    else:
        # Khi chạy trên Server / Non-TTY / Redirect file: Dùng StreamHandler sạch, không co góc, xóa sạch thẻ markup
        console = Console(force_terminal=False, no_color=True)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(CleanPlainFormatter("[%(asctime)s] %(levelname)-5s %(message)s", datefmt="%H:%M:%S"))

except ImportError:
    class DummyConsole:
        def print(self, *args, **kwargs):
            cleaned = [strip_markup(str(a)) for a in args]
            print(*cleaned)
    console = DummyConsole()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CleanPlainFormatter("[%(asctime)s] %(levelname)-5s %(message)s", datefmt="%H:%M:%S"))

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[handler],
    force=True
)

logger = logging.getLogger("story_translator")
logger.setLevel(logging.INFO)


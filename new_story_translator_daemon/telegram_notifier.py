"""
Module gửi thông báo tự động qua Telegram Group Topic chuyên cho luồng Dịch Mới Truyện.
Sử dụng topic TELEGRAM_NEW_STORY_TOPIC_ID từ file .env.
Định dạng tin nhắn chuẩn hóa tương tự auto_translator_daemon.
"""
import json
import html
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from new_story_translator_daemon.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_NEW_STORY_TOPIC_ID,
    format_chapter_ranges
)

class TelegramNotifier:
    """Gửi các mốc sự kiện quan trọng trong ca dịch mới truyện vào Telegram Topic chỉ định."""

    def __init__(
        self,
        bot_token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
        topic_id: Optional[int] = TELEGRAM_NEW_STORY_TOPIC_ID
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.topic_id = topic_id

    def is_configured(self) -> bool:
        """Kiểm tra xem đã cấu hình bot token và chat id chưa."""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str) -> bool:
        """Gửi 1 tin nhắn định dạng HTML vào Topic chỉ định."""
        if not self.is_configured():
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if self.topic_id is not None:
            payload["message_thread_id"] = self.topic_id

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data.get('ok', False)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            print(f"⚠️ [Telegram Error {e.code}]: {err_body}")
            return False
        except Exception as e:
            print(f"⚠️ [Telegram Error]: {e}")
            return False

    def notify_warning(self, title: str, message: str):
        """Thông báo cảnh báo lỗi không nghiêm trọng."""
        if not self.is_configured():
            return
        msg = (
            f"⚠️ <b>[CẢNH BÁO HỆ THỐNG]</b>\n\n"
            f"📌 <b>Vấn đề:</b> {title}\n"
            f"📝 <b>Chi tiết:</b> {message}\n"
            f"ℹ️ <i>Hệ thống vẫn tiếp tục phiên chạy với các dữ liệu còn lại.</i>"
        )
        self.send_message(msg)

    def notify_session_start(
        self,
        queue: List[Dict[str, Any]],
        workers: int,
        sort_by: str = "recent",
        chapters_per_story: int = 100,
        skipped_stories: Optional[List[Dict[str, Any]]] = None
    ):
        """Thông báo khi ca dịch mới truyện bắt đầu."""
        if not self.is_configured():
            return

        total_planned_chaps = sum(len(item['chapters_to_translate']) for item in queue)
        story_lines = []
        for idx, item in enumerate(queue, 1):
            chaps = item['chapters_to_translate']
            raw_total = item.get('raw_total')
            total_str = f" / {raw_total} chaps" if raw_total else ""
            sheet_meta = item.get('sheet_meta') or {}
            title = sheet_meta.get('title') or item['story_id']
            badge = item.get('badge') or sheet_meta.get('badge') or ""
            badge_str = f" {badge}" if badge else ""
            story_lines.append(f"  <b>{idx}.</b> [{item['source']}]{badge_str} <code>{item['story_id']}</code>: {len(chaps)} chaps ({format_chapter_ranges(chaps, arrow='➔')}{total_str}) | <i>{title}</i>")

        skipped_section = ""
        if skipped_stories:
            skip_lines = []
            for item in skipped_stories[:6]:
                src = item.get('source', '')
                sid = item.get('story_id', '')
                reason = html.escape(str(item.get('reason', '')))
                badge = f" {item.get('badge')}" if item.get('badge') else ""
                title = item.get('title')
                title_str = f" | <i>{html.escape(str(title))}</i>" if title and title != sid else ""
                skip_lines.append(f"  • [{src}]{badge} <code>{sid}</code>: {reason}{title_str}")
            if len(skipped_stories) > 6:
                skip_lines.append(f"  • <i>... và {len(skipped_stories) - 6} truyện khác</i>")
            skipped_section = (
                f"\n\n⚠️ <b>[CẢNH BÁO: LOẠI BỎ DO NHẢY CÓC]</b>\n"
                f"Đã loại bỏ {len(skipped_stories)} bộ truyện mới bị khuyết chương:\n"
                + "\n".join(skip_lines) + "\n"
                f"ℹ️ <i>Đã tự động lấy các truyện kế tiếp trong Whitelist để bù đủ quota!</i>"
            )

        msg = (
            f"🚀 <b>[BẮT ĐẦU CA DỊCH MỚI TỰ ĐỘNG]</b>\n\n"
            f"📊 <b>Tổng số chương dự kiến:</b> {total_planned_chaps} chaps ({len(queue)} truyện mới)\n"
            f"⚡ <b>Số worker song song:</b> {workers} workers\n"
            f"⚙️ <b>Tiêu chí sắp xếp:</b> <code>{sort_by}</code>\n"
            f"📋 <b>Danh sách hàng đợi:</b>\n"
            + "\n".join(story_lines)
            + skipped_section
        )
        self.send_message(msg)

    def notify_story_success(
        self,
        story_id: str,
        chapters_count: int,
        chaps_range: str,
        duration_str: str,
        uploaded: bool = True,
        total_raw: Optional[int] = None
    ):
        """Thông báo khi 1 bộ truyện mới dịch xong 100 chương, đạt QC và tạo mới trên Drive thành công."""
        if not self.is_configured():
            return

        total_str = f" / {total_raw} chaps" if total_raw else ""
        drive_msg = "Đã tạo mới translated_chapters.zip thành công! 🎉" if uploaded else "Đã bỏ qua upload (Chế độ thử nghiệm --no-upload) ⚠️"

        msg = (
            f"✅ <b>[HOÀN THÀNH BỘ TRUYỆN MỚI]</b>\n\n"
            f"📖 <b>Mã truyện:</b> <code>{story_id}</code>\n"
            f"📊 <b>Số chương khởi tạo:</b> {chapters_count} chương ({chaps_range}{total_str})\n"
            f"⏱ <b>Thời gian xử lý:</b> {duration_str}\n"
            f"🕵️ <b>Hậu kiểm QC:</b> 100% PASSED (Không chữ Hán, sạch HTML)\n"
            f"☁️ <b>Google Drive:</b> {drive_msg}\n"
            f"🤝 <i>Đã sẵn sàng bàn giao cho daemon dịch tiếp từ chương {chapters_count + 1}!</i>"
        )
        self.send_message(msg)

    def notify_story_failed(
        self,
        story_id: str,
        chapters_count: int,
        reason: str,
        isolated_path: Optional[str] = None,
        failed_details: Optional[List[Dict[str, Any]]] = None
    ):
        """Thông báo cảnh báo khi một bộ truyện mới gặp sự cố, bao gồm chi tiết các chương lỗi QC."""
        if not self.is_configured():
            return

        details_section = ""
        if failed_details:
            lines = []
            for fd in failed_details[:8]:
                chap = fd.get('chapter', '?')
                r = html.escape(str(fd.get('reason', '')))
                lines.append(f"  • <b>Chương {chap}:</b> {r}")
            if len(failed_details) > 8:
                lines.append(f"  • <i>... và {len(failed_details) - 8} chương lỗi khác</i>")
            details_section = "\n🔍 <b>Chi tiết chương lỗi:</b>\n" + "\n".join(lines) + "\n"

        isolate_line = f"\n📦 <b>Thư mục cách ly (Debug):</b> <code>{isolated_path}</code>\n" if isolated_path else ""

        msg = (
            f"🚨 <b>[CẢNH BÁO: LỖI TIẾN TRÌNH]</b>\n\n"
            f"📖 <b>Mã truyện:</b> <code>{story_id}</code>\n"
            f"📊 <b>Số chương:</b> {chapters_count} chương\n"
            f"❌ <b>Nguyên nhân:</b> {reason}\n"
            f"{details_section}"
            f"{isolate_line}"
            f"⚠️ <i>Tiến trình đã bỏ qua bộ này và tiếp tục xử lý các truyện tiếp theo.</i>"
        )
        self.send_message(msg)

    def notify_session_end(self, results: List[Dict[str, Any]], duration_str: str):
        """Thông báo tổng kết kết thúc ca dịch mới trong ngày."""
        if not self.is_configured():
            return

        def is_successful(r):
            agy_ok = 'SUCCESS' in r.get('agy_status', '')
            qc_ok = 'PASSED' in r.get('qc_status', '')
            sync_ok = ('SUCCESS' in r.get('sync_status', '')) or ('SKIPPED' in r.get('sync_status', ''))
            return agy_ok and qc_ok and sync_ok

        success_count = sum(1 for r in results if is_successful(r))
        total_chaps = sum(r.get('chapters', 0) for r in results if is_successful(r))

        msg = (
            f"🏁 <b>[TỔNG KẾT CA DỊCH MỚI HÔM NAY]</b>\n\n"
            f"⏱ <b>Tổng thời gian:</b> {duration_str}\n"
            f"🎉 <b>Khởi tạo thành công:</b> {total_chaps} chương ({success_count}/{len(results)} truyện mới)\n"
            f"🧹 <b>Dung lượng máy chủ:</b> Đã dọn dẹp sạch sẽ thư mục tạm (0 byte dư thừa) ✨"
        )
        self.send_message(msg)

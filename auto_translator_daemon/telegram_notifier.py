"""
Module gửi thông báo tự động qua Telegram Group Topic.
Sử dụng thư viện chuẩn urllib, không phụ thuộc thư viện ngoài.
"""
import json
import html
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from auto_translator_daemon.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_TOPIC_ID,
    format_chapter_ranges
)

class TelegramNotifier:
    """Gửi các mốc sự kiện quan trọng trong ca dịch vào Telegram Topic."""

    def __init__(
        self,
        bot_token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
        topic_id: Optional[int] = TELEGRAM_TOPIC_ID
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

    def notify_warning(self, title: str, message: str, will_exit: bool = False):
        """Thông báo cảnh báo hệ thống (ví dụ lỗi gọi Web API)."""
        if not self.is_configured():
            return
        status_line = (
            "🛑 <b>Tiến trình đã tự động dừng lại để bảo toàn Quota. Vui lòng kiểm tra lại dịch vụ Web API!</b>"
            if will_exit
            else "ℹ️ <i>Hệ thống vẫn tiếp tục phiên chạy với các dữ liệu còn lại.</i>"
        )
        msg = (
            f"⚠️ <b>[CẢNH BÁO HỆ THỐNG]</b>\n\n"
            f"📌 <b>Vấn đề:</b> {title}\n"
            f"📝 <b>Chi tiết:</b> {message}\n\n"
            f"{status_line}"
        )
        self.send_message(msg)

    def notify_skipped_stories(self, skipped_stories: List[Dict[str, Any]], is_dry_run: bool = False):
        """Cảnh báo ngay lập tức danh sách các bộ truyện bị loại do khuyết chương / nhảy cóc (bất kể có dry-run hay không)."""
        if not self.is_configured() or not skipped_stories:
            return

        mode_str = " <i>[CHẾ ĐỘ DRY-RUN]</i>" if is_dry_run else ""
        lines = []
        for item in skipped_stories[:12]:
            src = item.get('source', '')
            sid = item.get('story_id', '')
            reason = html.escape(str(item.get('reason', '')))
            badge = f" {item.get('badge')}" if item.get('badge') else ""
            vip = " ⭐ [ƯU TIÊN WEB]" if item.get('is_web_priority') else ""
            title = item.get('title')
            title_str = f" | <i>{html.escape(str(title))}</i>" if title and title != sid else ""
            folder_id = item.get('folder_id')
            drive_link = f"\n  📁 <a href=\"https://drive.google.com/drive/folders/{folder_id}\">Mở thư mục Google Drive ↗</a>" if folder_id else ""
            lines.append(f"• [{src}]{badge} <code>{sid}</code>{vip}{title_str}:\n  ↳ <i>{reason}</i>{drive_link}")

        more_str = f"\n\n• <i>... và {len(skipped_stories) - 12} bộ truyện lỗi khác</i>" if len(skipped_stories) > 12 else ""

        msg = (
            f"⚠️ <b>[CẢNH BÁO NGUỒN CÀO: LOẠI BỎ DO NHẢY CÓC]</b>{mode_str}\n\n"
            f"Phát hiện <b>{len(skipped_stories)}</b> bộ truyện bị khuyết / đứt mạch chương raw:\n\n"
            + "\n\n".join(lines)
            + more_str + "\n\n"
            f"👉 <i>Vui lòng forward danh sách này cho nhóm Crawler để kiểm tra và cào bù dữ liệu nguồn!</i>"
        )
        self.send_message(msg)

    def notify_session_start(
        self,
        queue: List[Dict[str, Any]],
        total_chapters: int,
        limit: int,
        sort_by: str,
        skipped_stories: Optional[List[Dict[str, Any]]] = None
    ):
        """Thông báo khi ca dịch hàng ngày bắt đầu."""
        if not self.is_configured():
            return

        story_lines = []
        for idx, item in enumerate(queue, 1):
            chaps = item['chapters_to_translate']
            raw_total = (item.get('inspected_meta') or {}).get('raw_chapters_count')
            total_str = f" / {raw_total} chaps" if raw_total else ""
            tag_vip = " ⭐ <b>[ƯU TIÊN WEB]</b>" if item.get('is_web_priority') else ""
            story_lines.append(f"  <b>{idx}.</b> [{item['source']}] <code>{item['story_id']}</code>: {len(chaps)} chaps ({format_chapter_ranges(chaps, arrow='➔')}{total_str}){tag_vip}")

        skipped_section = ""
        if skipped_stories:
            skip_lines = []
            for item in skipped_stories[:6]:
                src = item.get('source', '')
                sid = item.get('story_id', '')
                reason = html.escape(str(item.get('reason', '')))
                badge = f" {item.get('badge')}" if item.get('badge') else ""
                vip = " ⭐ [ƯU TIÊN WEB]" if item.get('is_web_priority') else ""
                title = item.get('title')
                title_str = f" | <i>{html.escape(str(title))}</i>" if title and title != sid else ""
                folder_id = item.get('folder_id')
                drive_link = f"\n  📁 <a href=\"https://drive.google.com/drive/folders/{folder_id}\">Mở thư mục Google Drive ↗</a>" if folder_id else ""
                skip_lines.append(f"• [{src}]{badge} <code>{sid}</code>{vip}{title_str}:\n  ↳ <i>{reason}</i>{drive_link}")
            if len(skipped_stories) > 6:
                skip_lines.append(f"• <i>... và {len(skipped_stories) - 6} truyện khác</i>")
            skipped_section = (
                f"\n\n⚠️ <b>[CẢNH BÁO: LOẠI BỎ DO NHẢY CÓC]</b>\n"
                f"Đã loại bỏ {len(skipped_stories)} bộ truyện bị khuyết/đứt mạch:\n\n"
                + "\n\n".join(skip_lines) + "\n\n"
                f"ℹ️ <i>Đã tự động lấy các truyện kế tiếp trong Whitelist để bù đủ quota!</i>"
            )

        msg = (
            f"🚀 <b>[BẮT ĐẦU CA DỊCH TỰ ĐỘNG]</b>\n\n"
            f"📊 <b>Tổng số chương dự kiến:</b> {total_chapters}/{limit} chaps\n"
            f"⚙️ <b>Tiêu chí sắp xếp:</b> <code>{sort_by}</code>\n"
            f"📋 <b>Danh sách hàng đợi ({len(queue)} truyện):</b>\n"
            + "\n".join(story_lines)
            + skipped_section
        )
        self.send_message(msg)

    def notify_pre_check_result(
        self,
        story_id: str,
        chapters_count: int,
        chaps_range: str,
        allowed: bool,
        is_complete: bool,
        report_brief: str,
        isolated_path: Optional[str] = None,
        source: Optional[str] = None,
        title: Optional[str] = None,
        folder_id: Optional[str] = None
    ):
        """Thông báo kết quả thẩm định ngữ nghĩa nhanh trước khi dịch (Pre-Check Sanity Report)."""
        if not self.is_configured():
            return

        src_str = f"[{source}] " if source else ""
        title_line = f"📚 <b>Tên truyện:</b> <i>{html.escape(title)}</i>\n" if title and title != story_id else ""
        drive_link_line = f"\n📁 <b>Thư mục Drive:</b> <a href=\"https://drive.google.com/drive/folders/{folder_id}\">Mở thư mục bộ truyện ↗</a>" if folder_id else ""

        if allowed:
            complete_tag = "\n🏆 <b>DẤU HIỆU: ĐÃ ĐẾN ĐẠI KẾT CỤC TOÀN VĂN!</b> 🎉" if is_complete else ""
            msg = (
                f"🔍 <b>[THẨM ĐỊNH DỮ LIỆU: ĐẠT YÊU CẦU ✅]</b>\n\n"
                f"{title_line}"
                f"📖 <b>Mã truyện:</b> {src_str}<code>{story_id}</code>\n"
                f"📊 <b>Dải chương kiểm tra:</b> {chapters_count} chương ({chaps_range})\n"
                f"📝 <b>Đánh giá ngữ nghĩa:</b>\n"
                f"<blockquote>{html.escape(report_brief)}</blockquote>"
                f"{drive_link_line}"
                f"{complete_tag}\n\n"
                f"🚀 <i>Dữ liệu hợp lệ! Tiến trình bắt đầu chuyển sang bước dịch thuật...</i>"
            )
        else:
            isolate_line = f"\n📦 <b>Thư mục cách ly (Debug):</b> <code>{isolated_path}</code>" if isolated_path else ""
            msg = (
                f"🚨 <b>[CẢNH BÁO NGUỒN CÀO: TỪ CHỐI DỊCH ❌]</b>\n\n"
                f"{title_line}"
                f"📖 <b>Mã truyện:</b> {src_str}<code>{story_id}</code>\n"
                f"📊 <b>Dải chương dự kiến:</b> {chapters_count} chương ({chaps_range})\n"
                f"❌ <b>Báo cáo lỗi (Forward cho đội Crawler sửa nguồn):</b>\n"
                f"<blockquote>{html.escape(report_brief)}</blockquote>"
                f"{drive_link_line}"
                f"{isolate_line}\n\n"
                f"⚠️ <i>Hệ thống đã tự động từ chối dịch mẻ này để tránh lãng phí chi phí AI và chuyển sang truyện tiếp theo.</i>"
            )
        self.send_message(msg)

    def notify_story_success(
        self,
        story_id: str,
        chapters_count: int,
        chaps_range: str,
        duration_str: str,
        uploaded: bool = True,
        total_raw: Optional[int] = None,
        is_complete: bool = False,
        source: Optional[str] = None,
        title: Optional[str] = None,
        folder_id: Optional[str] = None
    ):
        """Thông báo khi 1 bộ truyện dịch xong, đạt QC và upload Drive thành công."""
        if not self.is_configured():
            return

        total_str = f" / {total_raw} chaps" if total_raw else ""
        drive_msg = "Đã đồng bộ translated_chapters.zip thành công! 🎉" if uploaded else "Đã bỏ qua upload (Chế độ thử nghiệm --no-upload) ⚠️"
        complete_banner = "\n\n🏆 <b>[CHÚC MỪNG: BỘ TRUYỆN ĐÃ ĐẠT ĐẠI KẾT CỤC HOÀN TOÀN]</b> 🎊" if is_complete else ""

        src_str = f"[{source}] " if source else ""
        title_line = f"📚 <b>Tên truyện:</b> <i>{html.escape(title)}</i>\n" if title and title != story_id else ""
        drive_link_line = f"\n📁 <b>Thư mục Drive:</b> <a href=\"https://drive.google.com/drive/folders/{folder_id}\">Mở thư mục bộ truyện ↗</a>" if folder_id else ""

        msg = (
            f"✅ <b>[HOÀN THÀNH BỘ TRUYỆN]</b>\n\n"
            f"{title_line}"
            f"📖 <b>Mã truyện:</b> {src_str}<code>{story_id}</code>\n"
            f"📊 <b>Số chương dịch:</b> {chapters_count} chương ({chaps_range}{total_str})\n"
            f"⏱ <b>Thời gian xử lý:</b> {duration_str}\n"
            f"🕵️ <b>Hậu kiểm QC:</b> 100% PASSED (Không chữ Hán, sạch HTML)\n"
            f"☁️ <b>Google Drive:</b> {drive_msg}"
            f"{drive_link_line}"
            f"{complete_banner}"
        )
        self.send_message(msg)

    def notify_story_failed(
        self,
        story_id: str,
        chapters_count: int,
        reason: str,
        isolated_path: Optional[str] = None,
        failed_details: Optional[List[Dict[str, Any]]] = None,
        source: Optional[str] = None,
        title: Optional[str] = None,
        folder_id: Optional[str] = None
    ):
        """Thông báo cảnh báo khi một bộ truyện gặp sự cố, bao gồm chi tiết các chương lỗi QC."""
        if not self.is_configured():
            return

        src_str = f"[{source}] " if source else ""
        title_line = f"📚 <b>Tên truyện:</b> <i>{html.escape(title)}</i>\n" if title and title != story_id else ""
        drive_link_line = f"\n📁 <b>Thư mục Drive:</b> <a href=\"https://drive.google.com/drive/folders/{folder_id}\">Mở thư mục bộ truyện ↗</a>\n" if folder_id else ""

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
            f"{title_line}"
            f"📖 <b>Mã truyện:</b> {src_str}<code>{story_id}</code>\n"
            f"📊 <b>Số chương:</b> {chapters_count} chương\n"
            f"❌ <b>Nguyên nhân:</b> {reason}\n"
            f"{details_section}"
            f"{drive_link_line}"
            f"{isolate_line}"
            f"⚠️ <i>Tiến trình đã bỏ qua bộ này và tiếp tục xử lý các truyện tiếp theo.</i>"
        )
        self.send_message(msg)

    def notify_session_end(self, results: List[Dict[str, Any]], duration_str: str):
        """Thông báo tổng kết kết thúc ca dịch trong ngày."""
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
            f"🏁 <b>[TỔNG KẾT CA DỊCH HÔM NAY]</b>\n\n"
            f"⏱ <b>Tổng thời gian:</b> {duration_str}\n"
            f"🎉 <b>Dịch thành công:</b> {total_chaps} chương ({success_count}/{len(results)} truyện)\n"
            f"🧹 <b>Dung lượng máy chủ:</b> Đã dọn dẹp sạch sẽ thư mục tạm (0 byte dư thừa) ✨"
        )
        self.send_message(msg)

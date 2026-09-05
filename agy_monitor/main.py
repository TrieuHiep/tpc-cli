"""
Telegram AGY Monitor & AI Chatbot Service (Main Entrypoint).
Chạy vòng lặp Long-Polling độc lập 24/7 kết hợp:
1. Giám sát & Điều khiển: /status, /quota, /tasks, /kill
2. AI Chatbot thông minh: Chat trực tiếp với Gemini 3.8 Flash, Multi-turn context
3. Quản lý phiên hội thoại: /newchat (Tạo mới), /chats (Lịch sử & Resume bằng nút bấm)
4. Tự động chia nhỏ tin nhắn dài (Smart Chunking <= 4000 ký tự) & Hiệu ứng Typing
"""
import os
import sys
import json
import time
import signal
import threading
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, Optional, List

# Đảm bảo console UTF-8 trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from agy_monitor.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_MONITOR_TOPIC_ID
)
from agy_monitor.core import (
    check_liveness,
    get_model_quota,
    get_active_tasks,
    kill_agy,
    smart_split_message,
    send_chat_to_agy
)
from agy_monitor.session_manager import SessionManager

# Biến cờ kiểm soát vòng lặp
_running = True


def _signal_handler(sig, frame):
    global _running
    print("\n🛑 [Monitor] Đang dừng dịch vụ AGY Monitor & Chatbot...", flush=True)
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)



class AGYTelegramBot:
    """Bot quản trị & AI Chatbot qua Telegram Topic."""

    def __init__(
        self,
        token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
        topic_id: Optional[int] = TELEGRAM_MONITOR_TOPIC_ID
    ):
        self.token = token
        self.chat_id = chat_id
        self.topic_id = topic_id
        self.last_update_id = 0
        self.last_dashboard_cmd = "cmd_ping"
        self.session_mgr = SessionManager()
        self.bot_username = "thinhphongcac_auto_trans_bot"
        self._fetch_bot_info()

    def _fetch_bot_info(self):
        """Lấy thông tin username của Bot từ Telegram API."""
        try:
            url = f"https://api.telegram.org/bot{self.token}/getMe"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    self.bot_username = data["result"].get("username", self.bot_username)
        except Exception:
            pass

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_typing(self):
        """Gửi trạng thái 'Bot is typing...' trên Telegram."""
        if not self.is_configured():
            return
        url = f"https://api.telegram.org/bot{self.token}/sendChatAction"
        payload = {"chat_id": self.chat_id, "action": "typing"}
        if self.topic_id is not None:
            payload["message_thread_id"] = self.topic_id
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=4):
                pass
        except Exception:
            pass

    def send_message(
        self,
        text: str,
        reply_to_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Gửi tin nhắn HTML vào đúng Topic."""
        if not self.is_configured():
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if self.topic_id is not None:
            payload["message_thread_id"] = self.topic_id
        if reply_to_id:
            payload["reply_to_message_id"] = reply_to_id
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("ok", False)
        except Exception as e:
            # Nếu gặp lỗi thẻ HTML parse_mode, thử gửi lại dạng text thuần
            try:
                payload["parse_mode"] = None
                req2 = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    data2 = json.loads(resp2.read().decode("utf-8"))
                    return data2.get("ok", False)
            except Exception:
                print(f"⚠️ [Telegram Send Error]: {e}", flush=True)
                return False

    def edit_message(
        self,
        chat_id: Any,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Cập nhật nội dung tin nhắn tại chỗ (In-place update)."""
        if not self.is_configured():
            return False

        url = f"https://api.telegram.org/bot{self.token}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("ok", False)
        except Exception:
            return False

    def answer_callback(self, callback_id: str, text: Optional[str] = None):
        """Phản hồi callback_query để tắt loading."""
        url = f"https://api.telegram.org/bot{self.token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=4):
                pass
        except Exception:
            pass

    # ==================== CÁC BỘ XỬ LÝ LỆNH QUẢN TRỊ ====================

    def handle_ping(self) -> str:
        self.last_dashboard_cmd = "cmd_ping"
        live = check_liveness()
        status_icon = "🟢" if live["is_alive"] else "🔴"
        status_text = "ĐANG HOẠT ĐỘNG (RUNNING)" if live["is_alive"] else "ĐÃ DỪNG / KHÔNG CHẠY"

        lines = [
            f"{status_icon} <b>[AGY LIVENESS REPORT]</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"⚙️ <b>Hệ điều hành:</b> <code>{live['os']}</code>",
            f"📡 <b>Trạng thái:</b> <b>{status_text}</b>",
            f"🔢 <b>Số tiến trình agy:</b> <code>{live['count']}</code>"
        ]

        if live["is_alive"]:
            lines.append("\n📋 <b>Chi tiết tiến trình:</b>")
            for p in live["processes"]:
                lines.append(f"  • <b>PID:</b> <code>{p['pid']}</code> | <b>RAM:</b> <code>{p['memory_mb']} MB</code> ({p['name']})")
        else:
            lines.append("\n💡 <i>Không phát hiện tiến trình agy nào đang chạy trên máy chủ.</i>")

        lines.append(f"\n⏰ <i>Cập nhật: {datetime.now().strftime('%H:%M:%S - %d/%m/%Y')}</i>")
        return "\n".join(lines)

    def handle_quota(self) -> str:
        self.last_dashboard_cmd = "cmd_quota"
        res = get_model_quota()
        if not res.get("success"):
            return f"⚠️ <b>Lỗi truy vấn Quota:</b> <code>{res.get('error')}</code>"

        data = res["data"]
        cached_hint = " <i>(Dữ liệu đệm cache)</i>" if res.get("cached") else ""

        lines = [
            f"📊 <b>[QUOTA TOKEN ANTIGRAVITY]</b>{cached_hint}",
            f"━━━━━━━━━━━━━━━━━━━━"
        ]

        for g in data.get("groups", []):
            lines.append(f"\n🔹 <b>{g['name'].upper()}</b>")
            for b in g.get("buckets", []):
                lines.append(f"  • <b>{b['name']}:</b>")
                lines.append(f"    <code>{b['bar']}</code>")
                if b.get("description"):
                    lines.append(f"    ⏳ <i>{b['description']}</i>")

        lines.append(f"\n⏰ <i>Cập nhật: {data.get('fetched_at')}</i>")
        return "\n".join(lines)

    def handle_tasks(self) -> str:
        self.last_dashboard_cmd = "cmd_tasks"
        tasks = get_active_tasks()
        live = check_liveness()

        lines = [
            f"📋 <b>[DANH SÁCH TÁC VỤ ANTIGRAVITY]</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"⚙️ <b>Tiến trình AGY:</b> {'🟢 Running' if live['is_alive'] else '⚪ Idle'}"
        ]

        if not tasks.get("active") or not tasks.get("sessions"):
            lines.append("\n💤 <i>Hiện không có tác vụ hoặc subagent nào đang hoạt động gần đây.</i>")
        else:
            lines.append(f"\n🎯 <b>Phiên làm việc gần nhất ({len(tasks['sessions'])} session):</b>")
            for idx, s in enumerate(tasks["sessions"], 1):
                cid_short = s["conversation_id"][:8]
                sub_str = ", ".join(s["subagents"]) if s["subagents"] else "Main Agent (Planner)"
                lines.append(f"\n<b>{idx}. Session <code>{cid_short}</code>:</b>")
                lines.append(f"  • <b>Subagent:</b> <code>{sub_str}</code>")
                lines.append(f"  • <b>Thao tác cuối:</b> <i>{s['current_action']}</i>")
                lines.append(f"  • <b>Hoạt động gần nhất:</b> {s['last_updated_sec_ago']}s trước")
                if s.get("story_hint"):
                    lines.append(f"  • <b>Ngữ cảnh:</b> <i>{s['story_hint']}...</i>")

        lines.append(f"\n⏰ <i>Cập nhật: {datetime.now().strftime('%H:%M:%S')}</i>")
        return "\n".join(lines)

    def handle_kill(self) -> str:
        res = kill_agy()
        if res.get("killed_any"):
            msg = (
                f"🛑 <b>[ĐÃ DỪNG KHẨN CẤP TIẾN TRÌNH]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Đã gửi tín hiệu terminate dừng toàn bộ tiến trình <code>agy</code> thành công!\n"
            )
            if res.get("temp_cleaned"):
                msg += "🧹 Đã dọn dẹp thư mục tạm <code>storage/temp/</code> an toàn.\n"
            msg += f"\n⏰ <i>Thực hiện lúc: {datetime.now().strftime('%H:%M:%S')}</i>"
            return msg
        else:
            return (
                f"ℹ️ <b>[THÔNG BÁO]</b>\n"
                f"Không tìm thấy tiến trình <code>agy</code> nào đang chạy trên máy chủ để tắt.\n"
                f"\n⏰ <i>Kiểm tra lúc: {datetime.now().strftime('%H:%M:%S')}</i>"
            )

    # ==================== CÁC BỘ XỬ LÝ CHAT & RESUME ====================

    def handle_new_chat(self) -> str:
        """Bắt đầu phiên chat mới (/newchat)."""
        self.session_mgr.start_new_session()
        return (
            f"✨ <b>[PHIÊN TRÒ CHUYỆN MỚI]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Đã làm mới cuộc hội thoại! AI đã quên ngữ cảnh cũ.\n"
            f"Bạn có thể bắt đầu nhắn tin hỏi đáp về chủ đề mới ngay bây giờ."
        )

    def handle_chats_list(self) -> str:
        """Hiển thị danh sách các phiên chat gần đây để người dùng chọn khôi phục (Resume)."""
        sessions = self.session_mgr.get_recent_sessions(limit=5)
        active_id = self.session_mgr.get_active_session_id()

        lines = [
            f"🗂️ <b>[LỊCH SỬ CÁC CUỘC HỘI THOẠI]</b>",
            f"━━━━━━━━━━━━━━━━━━━━"
        ]

        if not sessions:
            lines.append("<i>Chưa có cuộc hội thoại nào được lưu gần đây.</i>")
            lines.append("\n💡 Gõ <code>/newchat</code> để bắt đầu trò chuyện mới!")
        else:
            lines.append("Chạm vào lệnh tương ứng bên dưới để tiếp tục trò chuyện:\n")
            for idx, s in enumerate(sessions, 1):
                sid = s["id"]
                title = s.get("title", "Hội thoại")
                is_active = (sid == active_id)
                tag = " 🟢 <i>(Đang chọn)</i>" if is_active else ""
                time_str = s.get("updated_at", "")[11:16] # HH:MM
                count = s.get("message_count", 1)

                lines.append(f"<b>{idx}. {title}</b> ({time_str} - {count} tin){tag}")
                lines.append(f"   👉 Khôi phục: /resume_{idx}\n")

            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("💡 Gõ <code>/newchat</code> để bắt đầu chủ đề mới tinh.")

        return "\n".join(lines)

    def handle_resume_session(self, session_id: str) -> str:
        """Kích hoạt lại phiên chat cũ theo session_id."""
        self.session_mgr.set_active_session(session_id)
        info = self.session_mgr.get_session_info(session_id)
        title = info.get("title", "Cuộc trò chuyện") if info else session_id[:8]
        count = info.get("message_count", 0) if info else 1

        return (
            f"🔄 <b>[ĐÃ KHÔI PHỤC CUỘC HỘI THOẠI]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Chủ đề:</b> <i>{title}</i>\n"
            f"🔢 <b>Số lượt chat:</b> <code>{count}</code> lượt\n"
            f"🆔 <b>Session ID:</b> <code>{session_id[:8]}...</code>\n\n"
            f"🧠 AI đã nạp lại toàn bộ trí nhớ của phiên này! Bạn có thể tiếp tục trò chuyện."
        )

    def handle_help(self) -> str:
        active_id = self.session_mgr.get_active_session_id()
        session_hint = f"<code>{active_id[:8]}...</code>" if active_id else "<i>(Mới tinh)</i>"

        return (
            f"🛠️ <b>[DANH SÁCH LỆNH & TRỢ LÝ AI]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>Mẹo:</b> Gõ dấu <code>/</code> để mở menu chọn lệnh nhanh, hoặc nhắn tin bất kỳ để chat trực tiếp với AI.\n"
            f"📍 <b>Phiên chat hiện tại:</b> {session_hint}\n\n"
            f"<b>Các câu lệnh:</b>\n"
            f"• 🟢 <code>/status</code>: Kiểm tra AGY còn sống không, PID, RAM.\n"
            f"• 📊 <code>/quota</code>: Xem % Quota Gemini & Claude.\n"
            f"• 📋 <code>/tasks</code>: Xem các Subagent đang hoạt động.\n"
            f"• ➕ <code>/newchat</code>: Bắt đầu cuộc trò chuyện mới.\n"
            f"• 🗂️ <code>/chats</code>: Xem lịch sử & chọn phiên để tiếp tục chat.\n"
            f"• 🛑 <code>/kill</code>: Dừng khẩn cấp tiến trình nếu bị treo.\n"
            f"• ℹ️ <code>/help</code>: Xem lại danh sách lệnh này.\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    # ==================== XỬ LÝ CHAT TIN NHẮN TỰ DO ====================

    def process_user_chat(self, user_prompt: str, reply_to_msg_id: int):
        """Xử lý câu hỏi tự do của người dùng tới AGY (Chạy trong thread riêng)."""
        # 1. Bật hiệu ứng typing
        self.send_typing()

        active_id = self.session_mgr.get_active_session_id()
        print(f"🤖 [AI Chat] Đang xử lý prompt ({len(user_prompt)} chars) | Session: {active_id or 'NEW'}", flush=True)

        # 2. Gọi AGY suy luận
        start_t = time.time()
        res = send_chat_to_agy(prompt=user_prompt, conversation_id=active_id, timeout_sec=180)
        elapsed = round(time.time() - start_t, 1)

        if not res.get("success"):
            err_msg = (
                f"⚠️ <b>Lỗi xử lý câu hỏi:</b>\n"
                f"<code>{res.get('error', 'Không xác định')}</code>\n\n"
                f"💡 Gợi ý: Kiểm tra lại lệnh hoặc thử gõ <code>/newchat</code> để làm mới phiên."
            )
            self.send_message(err_msg, reply_to_id=reply_to_msg_id)
            return

        response_text = res.get("response", "").strip()
        new_conv_id = res.get("conversation_id")

        if not response_text:
            response_text = "*(AI không trả về nội dung nào)*"

        # 3. Ghi nhận lượt chat vào SessionManager
        if new_conv_id:
            self.session_mgr.record_turn(new_conv_id, user_prompt)

        # 4. Cắt văn bản thông minh nếu vượt quá 4000 ký tự (Tránh lỗi Telegram 400)
        chunks = smart_split_message(response_text, max_chars=3900)

        for idx, chunk in enumerate(chunks):
            # Nếu có nhiều chunk, đánh số (1/3), (2/3)...
            chunk_header = ""
            if len(chunks) > 1:
                chunk_header = f"<i>[Phần {idx + 1}/{len(chunks)}]</i>\n"

            # Đính kèm thời gian thực thi ở chunk cuối cùng
            chunk_footer = ""
            if idx == len(chunks) - 1:
                chunk_footer = f"\n\n⏱️ <i>({elapsed}s)</i>"

            final_text = f"{chunk_header}{chunk}{chunk_footer}"
            # Chỉ reply message đầu tiên vào tin nhắn của user
            reply_id = reply_to_msg_id if idx == 0 else None
            self.send_message(final_text, reply_to_id=reply_id, reply_markup=None)

    # ==================== VÒNG LẶP LONG POLLING ====================

    def poll_updates(self):
        url = f"https://api.telegram.org/bot{self.token}/getUpdates?offset={self.last_update_id + 1}&timeout=20"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AGYMonitor/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("ok"):
                    return

                for update in data.get("result", []):
                    self.last_update_id = max(self.last_update_id, update.get("update_id", 0))

                    # 1. XỬ LÝ TIN NHẮN VĂN BẢN (TEXT MESSAGE)
                    msg = update.get("message") or update.get("channel_post")
                    if not msg:
                        continue

                    chat = msg.get("chat", {})
                    chat_id_str = str(chat.get("id"))
                    if chat_id_str != str(self.chat_id):
                        continue

                    thread_id = msg.get("message_thread_id")
                    if self.topic_id is not None and thread_id != self.topic_id:
                        continue

                    text = (msg.get("text") or "").strip()
                    msg_id = msg.get("message_id")
                    if not text:
                        continue

                    # PHÂN NHÁNH 1: CÂU LỆNH BẮT ĐẦU BẰNG DẤU GẠCH CHÉO '/'
                    if text.startswith("/"):
                        parts = text.split()
                        cmd = parts[0].lower().split("@")[0]
                        print(f"📥 [Command] Lệnh: {cmd} (Topic: {thread_id})", flush=True)

                        reply_text = None

                        if cmd in ("/ask", "/chat", "/ai"):
                            user_prompt = text.split(maxsplit=1)[1].strip() if len(parts) > 1 else ""
                            if not user_prompt:
                                self.send_message("💡 <b>Cách dùng:</b> <code>/ask [câu hỏi]</code>\nVí dụ: <code>/ask thủ đô của Việt Nam là gì?</code>", reply_to_id=msg_id)
                            else:
                                print(f"💬 [User Chat via /ask] '{user_prompt[:60]}...' (Topic: {thread_id})", flush=True)
                                t = threading.Thread(target=self.process_user_chat, args=(user_prompt, msg_id), daemon=True)
                                t.start()
                            continue
                        elif cmd in ("/ping", "/status"):
                            reply_text = self.handle_ping()
                        elif cmd in ("/quota", "/usage"):
                            reply_text = self.handle_quota()
                        elif cmd in ("/tasks", "/task"):
                            reply_text = self.handle_tasks()
                        elif cmd == "/kill":
                            reply_text = self.handle_kill()
                        elif cmd in ("/newchat", "/reset"):
                            reply_text = self.handle_new_chat()
                        elif cmd in ("/chats", "/history"):
                            reply_text = self.handle_chats_list()
                        elif cmd.startswith("/resume_") or cmd == "/resume":
                            target_session_id = None
                            if cmd.startswith("/resume_"):
                                arg = cmd.replace("/resume_", "").strip()
                            elif len(parts) > 1:
                                arg = parts[1].strip()
                            else:
                                arg = ""

                            if arg.isdigit():
                                target_session_id = self.session_mgr.get_session_id_by_index(int(arg))
                            elif arg:
                                target_session_id = arg

                            if target_session_id:
                                reply_text = self.handle_resume_session(target_session_id)
                            else:
                                reply_text = self.handle_chats_list()
                        else:
                            reply_text = self.handle_help()

                        if reply_text:
                            self.send_message(reply_text, reply_to_id=msg_id)

                    # PHÂN NHÁNH 2: TIN NHẮN CHAT TỰ DO VỚI AI
                    else:
                        clean_text = text.replace(f"@{self.bot_username}", "").strip()
                        if not clean_text:
                            clean_text = text
                        print(f"💬 [User Chat] '{clean_text[:60]}...' (Topic: {thread_id})", flush=True)
                        t = threading.Thread(target=self.process_user_chat, args=(clean_text, msg_id), daemon=True)
                        t.start()

        except urllib.error.URLError:
            time.sleep(3)
        except Exception as e:
            print(f"⚠️ [Poll Error]: {e}", flush=True)
            time.sleep(3)

    def register_commands(self):
        """Đăng ký danh sách lệnh gợi ý khi gõ '/' trong Telegram."""
        url = f"https://api.telegram.org/bot{self.token}/setMyCommands"
        commands = [
            {"command": "ask", "description": "Hỏi đáp với AI (VD: /ask thủ đô của VN?)"},
            {"command": "status", "description": "Kiểm tra AGY còn sống không, PID, RAM"},
            {"command": "quota", "description": "Xem % Quota token model Gemini & Claude"},
            {"command": "tasks", "description": "Xem các task và subagent đang hoạt động"},
            {"command": "newchat", "description": "Bắt đầu cuộc trò chuyện mới với AI"},
            {"command": "chats", "description": "Lịch sử các cuộc hội thoại cũ để Resume"},
            {"command": "kill", "description": "Dừng khẩn cấp tiến trình AGY nếu bị treo"},
            {"command": "help", "description": "Hướng dẫn các câu lệnh"}
        ]
        for scope in [None, {"type": "chat", "chat_id": self.chat_id}]:
            payload = {"commands": commands}
            if scope:
                payload["scope"] = scope
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10):
                    pass
            except Exception:
                pass

    def start(self):
        """Khởi động bot."""
        if not self.is_configured():
            print("❌ [Monitor] Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong .env!", flush=True)
            return

        self.register_commands()

        topic_label = f"Topic #{self.topic_id}" if self.topic_id else "Main Chat"
        print(f"🚀 [Monitor & Chatbot] Bot đã khởi động!", flush=True)
        print(f"   • Chat ID: {self.chat_id}", flush=True)
        print(f"   • Mục tiêu lắng nghe: {topic_label}", flush=True)
        print(f"   • Tính năng: Liveness, Quota, Tasks, Kill, AI Chatbot, Resume Chat (Pure Slash Commands)", flush=True)

        startup_msg = (
            f"🤖 <b>[TRỢ LÝ AI & GIÁM SÁT ANTIGRAVITY ĐÃ ONLINE]</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Trò chuyện:</b> Nhắn bất kỳ câu hỏi nào để chat trực tiếp với AI.\n"
            f"• <b>Quản trị:</b> Gõ <code>/</code> để chọn các lệnh giám sát & quản lý."
        )
        self.send_message(startup_msg)

        while _running:
            self.poll_updates()
            time.sleep(1)

        print("👋 [Monitor] Dịch vụ đã kết thúc an toàn.", flush=True)


if __name__ == "__main__":
    bot = AGYTelegramBot()
    bot.start()

"""
Session manager for AI Chatbot conversations.
Quản lý trạng thái và lịch sử hội thoại (Active session, New chat, Resume chat).
Lưu trữ tại: storage/chat_sessions.json
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from agy_monitor.config import BASE_DIR

SESSIONS_FILE = BASE_DIR / "storage" / "chat_sessions.json"


class SessionManager:
    """Quản lý các phiên trò chuyện đa lượt (Multi-turn sessions)."""

    def __init__(self, file_path: Path = SESSIONS_FILE):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """Đọc file lưu trữ phiên trò chuyện."""
        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    return json.loads(content)
            except Exception:
                pass
        return {
            "active_session_id": None,
            "sessions": []
        }

    def _save(self):
        """Ghi dữ liệu nguyên tử (Atomic write)."""
        tmp_file = self.file_path.with_suffix(".tmp")
        try:
            tmp_file.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_file.replace(self.file_path)
        except Exception as e:
            print(f"⚠️ [SessionManager Save Error]: {e}", flush=True)

    def get_active_session_id(self) -> Optional[str]:
        """Lấy conversation_id của phiên đang chat hiện tại."""
        return self._data.get("active_session_id")

    def set_active_session(self, session_id: Optional[str]):
        """Chuyển đổi phiên chat đang active (Resume)."""
        self._data["active_session_id"] = session_id
        self._save()

    def start_new_session(self):
        """Bắt đầu phiên chat mới (/newchat). Đặt active_session = None để AGY tạo ID mới."""
        self._data["active_session_id"] = None
        self._save()

    def record_turn(self, session_id: str, user_prompt: str):
        """Ghi nhận lượt chat vào session_id."""
        if not session_id:
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sessions = self._data.get("sessions", [])

        # Tìm session đã tồn tại
        found = False
        for s in sessions:
            if s.get("id") == session_id:
                s["updated_at"] = now_str
                s["message_count"] = s.get("message_count", 0) + 1
                found = True
                break

        if not found:
            # Tạo tiêu đề tóm tắt từ câu chat đầu tiên
            clean_title = " ".join(user_prompt.split())
            if len(clean_title) > 35:
                clean_title = clean_title[:35] + "..."
            if not clean_title:
                clean_title = "Cuộc trò chuyện mới"

            new_entry = {
                "id": session_id,
                "title": clean_title,
                "created_at": now_str,
                "updated_at": now_str,
                "message_count": 1
            }
            # Thêm vào đầu danh sách
            sessions.insert(0, new_entry)
            # Giới hạn lưu tối đa 20 phiên gần nhất
            self._data["sessions"] = sessions[:20]

        self._data["active_session_id"] = session_id
        self._save()

    def get_recent_sessions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Lấy danh sách các phiên gần đây nhất để hiển thị nút bấm Resume."""
        sessions = self._data.get("sessions", [])
        return sessions[:limit]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết của 1 session."""
        for s in self._data.get("sessions", []):
            if s.get("id") == session_id:
                return s
        return None

    def get_session_id_by_index(self, index: int, limit: int = 5) -> Optional[str]:
        """Lấy session_id theo số thứ tự 1..limit."""
        sessions = self.get_recent_sessions(limit=limit)
        if 1 <= index <= len(sessions):
            return sessions[index - 1]["id"]
        return None

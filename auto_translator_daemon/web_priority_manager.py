"""
Module quản lý danh sách truyện ưu tiên cao nhất (Exception / Web Priority) từ Web API Thịnh Phong Các.
Các truyện trong danh sách này:
- BẮT BUỘC được phép dịch mà KHÔNG CẦN nằm trong Google Sheet Whitelist (Bypass Whitelist).
- Có độ ưu tiên cao nhất: được đưa lên đầu hàng đợi dịch trong ngày.
- Không cần cache cục bộ; nếu lỗi kết nối sẽ ghi nhận lỗi để gửi thông báo cảnh báo qua Telegram.
"""
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Set

from auto_translator_daemon.config import WEB_PRIORITY_API_URL, WEB_PRIORITY_API_KEY


class WebPriorityManager:
    """Tải và quản lý danh sách truyện ưu tiên từ Web API Thịnh Phong Các."""

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = api_url or WEB_PRIORITY_API_URL
        self.api_key = api_key or WEB_PRIORITY_API_KEY
        self.priority_stories: Dict[str, Dict[str, Any]] = {}
        self.last_error: Optional[str] = None
        self.load_priority_stories()

    def fetch_from_api(self) -> Dict[str, Dict[str, Any]]:
        """
        Gọi REST API lấy danh sách truyện ưu tiên (hỗ trợ phân trang).
        Trả về dict: {story_id: story_meta}
        """
        stories = {}
        page = 0
        page_size = 100

        while True:
            # Xây dựng URL phân trang
            separator = "&" if "?" in self.api_url else "?"
            paged_url = f"{self.api_url}{separator}page={page}&size={page_size}"

            req = urllib.request.Request(
                paged_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (AutoTranslatorDaemon/1.0)',
                    'X-API-KEY': self.api_key
                }
            )

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw_data = resp.read().decode('utf-8')
                    data = json.loads(raw_data)

                if data.get('result') != 1 and data.get('code') != 200:
                    raise ValueError(f"API trả về mã lỗi: {data.get('code')} - {data.get('message')}")

                payload = data.get('data', {})
                items = payload.get('content', [])

                for item in items:
                    story_id = (item.get('internalId') or item.get('internal_id') or '').strip()
                    drive_folder_id = (item.get('driveUrl') or item.get('drive_url') or '').strip()
                    if story_id:
                        stories[story_id] = {
                            'story_id': story_id,
                            'title': item.get('title', ''),
                            'slug': item.get('slug', ''),
                            'drive_folder_id': drive_folder_id,
                            'status': item.get('status', ''),
                            'source': item.get('source', ''),
                            'total_chapters': item.get('totalChapters', 0),
                            'is_web_priority': True
                        }

                total_pages = payload.get('totalPages', 1)
                page += 1
                if page >= total_pages:
                    break

            except Exception as e:
                self.last_error = f"Lỗi gọi API Web Priority ({paged_url}): {e}"
                print(f"⚠️ {self.last_error}")
                break

        return stories

    def load_priority_stories(self) -> Dict[str, Dict[str, Any]]:
        """Nạp danh sách truyện ưu tiên từ Web API."""
        print(f"🌐 Đang đồng bộ danh sách truyện ưu tiên từ Web API ({self.api_url})...")
        self.last_error = None
        try:
            self.priority_stories = self.fetch_from_api()
            if self.last_error:
                print(f"⚠️ Đã có lỗi xảy ra khi nạp từ Web API: {self.last_error}")
            else:
                print(f"⭐ Đã nạp thành công {len(self.priority_stories)} bộ truyện [ƯU TIÊN WEB] từ Thịnh Phong Các.")
        except Exception as e:
            self.last_error = f"Lỗi không xác định khi nạp Web Priority: {e}"
            print(f"❌ {self.last_error}")

        return self.priority_stories

    def is_priority(self, story_id: str) -> bool:
        """Kiểm tra một bộ truyện có thuộc danh sách ưu tiên cao nhất từ Web hay không."""
        return story_id.strip() in self.priority_stories

    def get_story_info(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin metadata của bộ truyện ưu tiên."""
        return self.priority_stories.get(story_id.strip())

    def get_priority_ids(self) -> Set[str]:
        """Lấy tập hợp tất cả story_id được ưu tiên."""
        return set(self.priority_stories.keys())

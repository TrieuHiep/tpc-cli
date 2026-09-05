"""
Module quản lý hàng đợi Lazy Queue Builder:
Quét cuốn chiếu từng truyện một qua RAM, đủ trần 300 chương thì DỪNG LẬP TỨC (Early Stop).
"""
from typing import List, Dict, Any
from auto_translator_daemon.config import DAILY_CHAPTER_LIMIT, BOUNDARY_STRATEGY, SOURCE_PRIORITY

class QueueManager:
    """Xây dựng hàng đợi dịch theo cơ chế Lazy Streaming & Early Stop."""

    def __init__(self, limit: int = DAILY_CHAPTER_LIMIT, strategy: str = BOUNDARY_STRATEGY):
        self.limit = limit
        self.strategy = strategy

    def build_lazy_queue(
        self,
        candidate_stories_by_source: Dict[str, List[Dict[str, Any]]],
        chapter_inspector,
        current_count: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Quét cuốn chiếu các truyện Whitelist theo thứ tự nguồn và sắp xếp:
        - Nhận current_count từ Chặng 1 (Web Priority) để tiếp nối hạn mức.
        - Kiểm tra mục lục zip từ xa qua RAM cho từng truyện.
        - Tìm ra các chương tồn đọng chưa dịch (raw_count > trans_count).
        - Cộng dồn đến khi chạm ngưỡng limit chương thì DỪNG HẲN TIẾN TRÌNH QUÉT (các truyện sau = 0 request).
        """
        queue = []
        remaining_quota = self.limit - current_count

        print(f"\n📋 Đang xây dựng hàng đợi Whitelist (Hạn mức còn lại: {remaining_quota}/{self.limit} chaps, Chế độ: {self.strategy})...")

        for source in SOURCE_PRIORITY:
            candidates = candidate_stories_by_source.get(source, [])
            if not candidates:
                continue

            if current_count >= self.limit:
                break

            print(f"\n🔍 Đang duyệt cuốn chiếu nguồn [{source}] ({len(candidates)} ứng viên Whitelist)...")

            for s_info in candidates:
                story_id = s_info['story_id']

                # 1. Thẩm định mục lục zip từ xa qua RAM (0 byte ghi xuống ổ cứng)
                inspected = chapter_inspector.inspect_story_remotely(s_info)

                if not inspected.get('is_valid', False):
                    print(f"  ⚠️ [{story_id}]: Bỏ qua: {inspected.get('reason')}")
                    continue

                new_chaps = inspected.get('new_chapters', [])
                if not new_chaps:
                    # Đã dịch 100%, không còn chương dở
                    continue

                chap_len = len(new_chaps)
                remaining = self.limit - current_count

                print(f"  📊 [{story_id}] Gốc: {inspected['raw_chapters_count']} | Đã dịch: {inspected['translated_chapters_count']} | Cần dịch tiếp: {chap_len} chương")

                if remaining <= 0:
                    break

                if current_count + chap_len <= self.limit:
                    queue.append({
                        'story_id': story_id,
                        'source': source,
                        'story_info': s_info,
                        'chapters_to_translate': new_chaps,
                        'is_partial': False,
                        'total_new_available': chap_len,
                        'inspected_meta': inspected,
                        'is_web_priority': False
                    })
                    current_count += chap_len
                    print(f"  ➕ [{story_id}]: Nhận toàn bộ {chap_len} chương. (Tích lũy: {current_count}/{self.limit})")

                else:
                    if self.strategy == "SPLIT":
                        selected_chaps = new_chaps[:remaining]
                        queue.append({
                            'story_id': story_id,
                            'source': source,
                            'story_info': s_info,
                            'chapters_to_translate': selected_chaps,
                            'is_partial': True,
                            'total_new_available': chap_len,
                            'inspected_meta': inspected,
                            'is_web_priority': False
                        })
                        current_count += len(selected_chaps)
                        print(f"  ✂️ [{story_id}]: Chạm trần quota! Lấy {len(selected_chaps)}/{chap_len} chương đầu (chế độ SPLIT). (Tích lũy: {current_count}/{self.limit})")
                        break
                    else:
                        print(f"  🛑 [{story_id}]: Có {chap_len} chương mới, vượt quota còn lại ({remaining}). Dừng lại theo ATOMIC để bảo toàn mạch truyện.")
                        break

                if current_count >= self.limit:
                    print(f"🎯 ĐÃ ĐẠT TRẦN {self.limit} CHƯƠNG CHO HÔM NAY! DỪNG TOÀN BỘ TIẾN TRÌNH QUÉT LẬP TỨC.")
                    break

            if current_count >= self.limit:
                break

        print(f"\n✅ Hoàn tất Chặng 2 (Whitelist): {len(queue)} bộ truyện được chọn thêm (Tích lũy: {current_count}/{self.limit} chương).")
        return queue

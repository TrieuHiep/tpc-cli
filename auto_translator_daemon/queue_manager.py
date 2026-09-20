"""
Module quản lý hàng đợi Lazy Queue Builder:
Quét cuốn chiếu từng truyện một qua RAM, đủ trần 300 chương thì DỪNG LẬP TỨC (Early Stop).
"""
from typing import List, Dict, Any, Tuple
from auto_translator_daemon.config import DAILY_CHAPTER_LIMIT, BOUNDARY_STRATEGY, SOURCE_PRIORITY, MAX_CHAPTERS_PER_STORY

class QueueManager:
    """Xây dựng hàng đợi dịch theo cơ chế Lazy Streaming & Early Stop."""

    def __init__(self, limit: int = DAILY_CHAPTER_LIMIT, strategy: str = BOUNDARY_STRATEGY, max_per_story: int = MAX_CHAPTERS_PER_STORY):
        self.limit = limit
        self.strategy = strategy
        self.max_per_story = max_per_story

    def build_lazy_queue(
        self,
        candidate_stories_by_source: Dict[str, List[Dict[str, Any]]],
        chapter_inspector,
        current_count: int = 0
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Quét cuốn chiếu các truyện Whitelist theo thứ tự nguồn và sắp xếp:
        - Nhận current_count từ Chặng 1 (Web Priority) để tiếp nối hạn mức.
        - Kiểm tra mục lục zip từ xa qua RAM cho từng truyện.
        - Tự động loại bỏ các truyện bị nhảy cóc / khuyết chương và tiếp tục quét bù quota.
        - Tìm ra các chương tồn đọng chưa dịch (raw_count > trans_count).
        - Cộng dồn đến khi chạm ngưỡng limit chương thì DỪNG HẲN TIẾN TRÌNH QUÉT (các truyện sau = 0 request).
        Trả về: (queue, skipped_stories)
        """
        queue = []
        skipped_stories = []
        remaining_quota = self.limit - current_count

        print(f"\n📋 Đang xây dựng hàng đợi Whitelist (Hạn mức còn lại: {remaining_quota}/{self.limit} chaps, Chế độ: {self.strategy})...")

        # 1. Gom toàn bộ ứng viên từ các nguồn
        all_candidates = []
        for source in SOURCE_PRIORITY:
            all_candidates.extend(candidate_stories_by_source.get(source, []))

        # 2. Sắp xếp đa tầng ưu tiên (Stable Multi-tier Sorting):
        # Tầng 3: Thứ tự nguồn trong SOURCE_PRIORITY
        def get_source_idx(x):
            src = x.get('source', '')
            return SOURCE_PRIORITY.index(src) if src in SOURCE_PRIORITY else 99

        all_candidates.sort(key=get_source_idx)

        # Tầng 2: Thời gian sửa đổi chapters.zip (mới nhất lên đầu)
        all_candidates.sort(key=lambda x: x.get('modified_time') or '', reverse=True)

        # Tầng 1: Độ ưu tiên (Priority) từ Google Sheet Tab:
        # P1: gay (Đam Mỹ) -> P2: ixdzs8 -> P3: truyendichwiki -> P4: novel543
        all_candidates.sort(key=lambda x: (x.get('sheet_meta') or {}).get('priority', 99))

        print(f"\n🔍 Đang duyệt cuốn chiếu ({len(all_candidates)} ứng viên Whitelist đã xếp theo thứ tự ưu tiên)...")

        for s_info in all_candidates:
            if current_count >= self.limit:
                print(f"🎯 ĐÃ ĐẠT TRẦN {self.limit} CHƯƠNG CHO HÔM NAY! DỪNG TOÀN BỘ TIẾN TRÌNH QUÉT LẬP TỨC.")
                break

            story_id = s_info['story_id']
            source = s_info['source']
            sheet_meta = s_info.get('sheet_meta') or {}
            badge = sheet_meta.get('badge', '')
            badge_str = f" {badge}" if badge else ""
            priority = sheet_meta.get('priority', 99)

            # 1. Thẩm định mục lục zip từ xa qua RAM (0 byte ghi xuống ổ cứng)
            inspected = chapter_inspector.inspect_story_remotely(s_info)

            if not inspected.get('is_valid', False):
                reason = inspected.get('reason', 'Không hợp lệ')
                if inspected.get('is_gap'):
                    print(f"  ❌ [{story_id}]{badge_str} [SKIP - NHẢY CÓC]: {reason}")
                    title = sheet_meta.get('title') or story_id
                    skipped_stories.append({
                        'source': source,
                        'story_id': story_id,
                        'title': title,
                        'badge': badge,
                        'reason': reason,
                        'is_web_priority': False
                    })
                else:
                    print(f"  ⚠️ [{story_id}]{badge_str}: Bỏ qua: {reason}")
                continue

            new_chaps = inspected.get('new_chapters', [])
            if not new_chaps:
                # Đã dịch 100%, không còn chương dở
                continue

            chap_len = len(new_chaps)
            remaining = self.limit - current_count

            print(f"  📊 [{story_id}]{badge_str} (P{priority}) Gốc: {inspected['raw_chapters_count']} | Đã dịch: {inspected['translated_chapters_count']} | Cần dịch tiếp: {chap_len} chương")

            if remaining <= 0:
                break

            # Xác định số lượng chương mong muốn cho truyện này (tôn trọng max_per_story nếu > 0)
            desired_len = min(chap_len, self.max_per_story) if self.max_per_story > 0 else chap_len

            if current_count + desired_len <= self.limit:
                selected_chaps = new_chaps[:desired_len]
                is_partial = len(selected_chaps) < chap_len
                queue.append({
                    'story_id': story_id,
                    'source': source,
                    'story_info': s_info,
                    'chapters_to_translate': selected_chaps,
                    'is_partial': is_partial,
                    'total_new_available': chap_len,
                    'inspected_meta': inspected,
                    'is_web_priority': False
                })
                current_count += len(selected_chaps)
                if is_partial:
                    print(f"  ✂️ [{story_id}]{badge_str}: Giới hạn tối đa {self.max_per_story} chaps/truyện. Lấy {len(selected_chaps)}/{chap_len} chương đầu. (Tích lũy: {current_count}/{self.limit})")
                else:
                    print(f"  ➕ [{story_id}]{badge_str}: Nhận toàn bộ {chap_len} chương. (Tích lũy: {current_count}/{self.limit})")

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
                    print(f"  ✂️ [{story_id}]{badge_str}: Chạm trần quota! Lấy {len(selected_chaps)}/{chap_len} chương đầu (chế độ SPLIT). (Tích lũy: {current_count}/{self.limit})")
                    break
                else:
                    print(f"  🛑 [{story_id}]{badge_str}: Có {desired_len} chương cần dịch, vượt quota còn lại ({remaining}). Dừng lại theo ATOMIC để bảo toàn mạch truyện.")
                    break

            if current_count >= self.limit:
                print(f"🎯 ĐÃ ĐẠT TRẦN {self.limit} CHƯƠNG CHO HÔM NAY! DỪNG TOÀN BỘ TIẾN TRÌNH QUÉT LẬP TỨC.")
                break

        print(f"\n✅ Hoàn tất Chặng 2 (Whitelist): {len(queue)} bộ truyện được chọn thêm (Tích lũy: {current_count}/{self.limit} chương).")
        return queue, skipped_stories

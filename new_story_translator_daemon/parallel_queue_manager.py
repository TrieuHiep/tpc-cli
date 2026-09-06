"""
Module quản lý hàng đợi dịch mới (Parallel Queue Manager):
Quét cuốn chiếu các ứng viên truyện mới qua RAM, lọc ra đúng 100 chương đầu tiên (chương 1 -> 100).
Gom đủ 10 bộ truyện thì dừng quét (Early Stop) để kích hoạt xử lý song song.
"""
from typing import List, Dict, Any, Optional
from new_story_translator_daemon.config import (
    TARGET_CHAPTERS_PER_STORY,
    TARGET_STORY_QUEUE_SIZE,
    SOURCE_PRIORITY
)
from new_story_translator_daemon.remote_zip_inspector import RemoteZipInspector

class ParallelQueueManager:
    """Xây dựng hàng đợi 10 truyện mới, mỗi truyện lấy 100 chương đầu."""

    def __init__(
        self,
        queue_size: int = TARGET_STORY_QUEUE_SIZE,
        target_chapters: int = TARGET_CHAPTERS_PER_STORY
    ):
        self.queue_size = queue_size
        self.target_chapters = target_chapters

    def build_queue(
        self,
        candidate_stories_by_source: Dict[str, List[Dict[str, Any]]],
        remote_inspector: RemoteZipInspector,
        sort_by: str = "recent"
    ) -> List[Dict[str, Any]]:
        """
        Duyệt cuốn chiếu các truyện mới, đọc Central Directory của chapters.zip qua RAM,
        chọn ra danh sách các chương từ 1 đến min(target_chapters, max_chap).
        Ưu tiên theo Priority của từng tab (ví dụ: tab 'gay' ưu tiên 1 được xét trước),
        sau đó theo sort_by (recent/oldest) và SOURCE_PRIORITY.
        Đủ self.queue_size truyện thì dừng ngay lập tức (Early Stop).
        """
        queue = []
        print(f"\n📋 Đang xây dựng hàng đợi truyện mới (Mục tiêu: {self.queue_size} truyện, mỗi truyện tối đa {self.target_chapters} chaps)...")

        # 1. Gom toàn bộ ứng viên từ các nguồn
        all_candidates = []
        for source in SOURCE_PRIORITY:
            all_candidates.extend(candidate_stories_by_source.get(source, []))

        # 2. Sắp xếp ổn định (Stable Multi-tier Sorting):
        # Tầng 3: Thứ tự nguồn trong SOURCE_PRIORITY
        def get_source_idx(x):
            src = x.get('source', '')
            return SOURCE_PRIORITY.index(src) if src in SOURCE_PRIORITY else 99

        all_candidates.sort(key=get_source_idx)

        # Tầng 2: Thời gian sửa đổi chapters.zip (recent hoặc oldest)
        if sort_by == "oldest":
            all_candidates.sort(key=lambda x: x.get('modified_time') or '', reverse=False)
        else:
            all_candidates.sort(key=lambda x: x.get('modified_time') or '', reverse=True)

        # Tầng 1: Độ ưu tiên (Priority) từ Google Sheet Tab (1 = cao nhất, 2, 3...)
        all_candidates.sort(key=lambda x: (x.get('sheet_meta') or {}).get('priority', 99))

        print(f"🔍 Đang thẩm định mục lục từ xa ({len(all_candidates)} ứng viên đã sắp xếp theo độ ưu tiên)...")

        for s_info in all_candidates:
            if len(queue) >= self.queue_size:
                print(f"🎯 Đã gom đủ {self.queue_size} bộ truyện mới vào hàng đợi! Dừng quét (Early Stop).")
                break

            story_id = s_info['story_id']
            source = s_info['source']
            sheet_meta = s_info.get('sheet_meta') or {}
            badge = sheet_meta.get('badge', '')
            badge_str = f" {badge}" if badge else ""
            priority = sheet_meta.get('priority', 99)
            czip = s_info['chapters_file']
            czip_size = int(czip.get('size', 0))

            # Đọc mục lục chapters.zip từ xa qua RAM (0 byte ghi xuống đĩa)
            raw_chaps = remote_inspector.get_chapters_map(czip['id'], czip_size, 'content.txt')
            if raw_chaps is None:
                print(f"  ⚠️ [{story_id}]{badge_str}: Không thể đọc mục lục chapters.zip qua RAM (lỗi kết nối). Bỏ qua.")
                continue

            raw_nums = sorted(list(raw_chaps.keys()))
            if not raw_nums:
                print(f"  ⚠️ [{story_id}]{badge_str}: chapters.zip rỗng hoặc không tìm thấy content.txt. Bỏ qua.")
                continue

            # Lấy các chương từ 1 đến self.target_chapters (ví dụ 1..100)
            selected_chaps = [c for c in raw_nums if c <= self.target_chapters]
            if not selected_chaps:
                selected_chaps = raw_nums[:self.target_chapters]

            print(f"  ✨ [{story_id}]{badge_str} (P{priority}): Phát hiện {len(raw_nums)} chương raw -> Chọn {len(selected_chaps)} chương đầu ({selected_chaps[0]} ➔ {selected_chaps[-1]})")

            queue.append({
                'story_id': story_id,
                'source': source,
                'story_info': s_info,
                'raw_total': len(raw_nums),
                'chapters_to_translate': selected_chaps,
                'sheet_meta': sheet_meta,
                'badge': badge,
                'priority': priority,
                'tab_name': sheet_meta.get('tab_name', '')
            })

        return queue

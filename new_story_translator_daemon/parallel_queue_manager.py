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
        remote_inspector: RemoteZipInspector
    ) -> List[Dict[str, Any]]:
        """
        Duyệt cuốn chiếu các truyện mới, đọc Central Directory của chapters.zip qua RAM,
        chọn ra danh sách các chương từ 1 đến min(target_chapters, max_chap).
        Đủ self.queue_size truyện thì dừng ngay lập tức.
        """
        queue = []
        print(f"\n📋 Đang xây dựng hàng đợi truyện mới (Mục tiêu: {self.queue_size} truyện, mỗi truyện tối đa {self.target_chapters} chaps)...")

        for source in SOURCE_PRIORITY:
            candidates = candidate_stories_by_source.get(source, [])
            if not candidates:
                continue

            if len(queue) >= self.queue_size:
                break

            print(f"\n🔍 Đang thẩm định mục lục các truyện mới nguồn [{source}] ({len(candidates)} ứng viên)...")

            for s_info in candidates:
                if len(queue) >= self.queue_size:
                    print(f"🎯 Đã gom đủ {self.queue_size} bộ truyện mới vào hàng đợi! Dừng quét (Early Stop).")
                    break

                story_id = s_info['story_id']
                czip = s_info['chapters_file']
                czip_size = int(czip.get('size', 0))

                # Đọc mục lục chapters.zip từ xa qua RAM (0 byte ghi xuống đĩa)
                raw_chaps = remote_inspector.get_chapters_map(czip['id'], czip_size, 'content.txt')
                if raw_chaps is None:
                    print(f"  ⚠️ [{story_id}]: Không thể đọc mục lục chapters.zip qua RAM (lỗi kết nối). Bỏ qua.")
                    continue

                raw_nums = sorted(list(raw_chaps.keys()))
                if not raw_nums:
                    print(f"  ⚠️ [{story_id}]: chapters.zip rỗng hoặc không tìm thấy content.txt. Bỏ qua.")
                    continue

                # Lấy các chương từ 1 đến self.target_chapters (ví dụ 1..100)
                selected_chaps = [c for c in raw_nums if c <= self.target_chapters]
                if not selected_chaps:
                    # Nếu vì lý do nào đó chương bắt đầu > target_chapters, lấy target_chapters chương đầu tiên hiện có
                    selected_chaps = raw_nums[:self.target_chapters]

                print(f"  ✨ [{story_id}]: Phát hiện {len(raw_nums)} chương raw -> Chọn {len(selected_chaps)} chương đầu ({selected_chaps[0]} ➔ {selected_chaps[-1]})")

                queue.append({
                    'story_id': story_id,
                    'source': source,
                    'story_info': s_info,
                    'raw_total': len(raw_nums),
                    'chapters_to_translate': selected_chaps,
                    'sheet_meta': s_info.get('sheet_meta')
                })

        return queue

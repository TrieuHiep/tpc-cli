import os
import time
import argparse
from typing import Optional
from .config import PAUSE_TITLE_TAG
from .api_client import TTSApiClient
from .audio_processor import AudioProcessor

class BatchRunner:
    """Điều phối toàn bộ quy trình đọc truyện, gọi TTS API và đóng gói SRT."""

    def __init__(self, api_client: Optional[TTSApiClient] = None):
        self.client = api_client or TTSApiClient()
        self.processor = AudioProcessor()

    def process_chapter_dir(self, chapter_dir: str) -> bool:
        """Thực thi xử lý cho duy nhất 1 thư mục chương."""
        chap_num = os.path.basename(os.path.normpath(chapter_dir))
        content_vi_path = os.path.join(chapter_dir, 'content_vi.txt')
        
        mp3_path = os.path.join(chapter_dir, f"audio_chapter{chap_num}.mp3")
        m4a_path = os.path.join(chapter_dir, f"audio_chapter{chap_num}.m4a")
        srt_path = os.path.join(chapter_dir, 'content_vi.srt')

        # Resume Check
        if os.path.exists(m4a_path) and os.path.exists(srt_path):
            print(f"⏩ Bỏ qua Chương {chap_num} (đã hoàn thành).")
            return True

        if not os.path.exists(content_vi_path):
            print(f"⚠️ Không tìm thấy file: {content_vi_path}")
            return False

        with open(content_vi_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        if not lines:
            print(f"⚠️ Thư mục chương {chap_num} rỗng.")
            return False

        # Chèn thẻ pause sau tiêu đề
        title_line = lines[0] + f" {PAUSE_TITLE_TAG}"
        body_lines = lines[1:]
        processed_sentences = [lines[0]] + body_lines
        full_tts_text = "\n".join([title_line] + body_lines)

        print(f"🚀 [Chương {chap_num}] Đang gửi TTS API: '{lines[0]}'...")

        # Gọi API
        output_filename, duration_s = self.client.generate_audio(full_tts_text)

        # Tải file MP3
        self.client.download_audio(output_filename, mp3_path)

        # Nén M4A (AAC 56kbps Mono)
        self.processor.compress_to_m4a(mp3_path, m4a_path)

        # Căn mốc SRT
        self.processor.generate_srt(m4a_path, processed_sentences, duration_s, srt_path)

        orig_sz = os.path.getsize(mp3_path)
        m4a_sz = os.path.getsize(m4a_path)
        savings = (1 - m4a_sz / orig_sz) * 100

        print(f"✅ [Chương {chap_num}] Thành công! Thời lượng: {duration_s:.1f}s | Audio: {m4a_sz} bytes (-{savings:.1f}%)")
        return True

    def run_all(self, base_chapters_dir: str, start_chap: Optional[int] = None, end_chap: Optional[int] = None, max_retries: int = 3):
        """Duyệt và chạy hàng loạt trên thư mục chứa tất cả các chương."""
        if not os.path.exists(base_chapters_dir):
            print(f"❌ Đường dẫn không tồn tại: {base_chapters_dir}")
            return

        chapter_folders = []
        for entry in os.listdir(base_chapters_dir):
            full_p = os.path.join(base_chapters_dir, entry)
            if os.path.isdir(full_p) and entry.isdigit():
                num = int(entry)
                if start_chap is not None and num < start_chap:
                    continue
                if end_chap is not None and num > end_chap:
                    continue
                chapter_folders.append((num, full_p))

        chapter_folders.sort(key=lambda x: x[0])
        total = len(chapter_folders)

        print("=" * 50)
        print(f"🎯 BẮT ĐẦU CHẠY BATCH PROCESSOR CHO {total} CHƯƠNG TRUYỆN")
        if start_chap or end_chap:
            print(f"📌 Giới hạn phạm vi: Chương {start_chap or 1} -> Chương {end_chap or 'Cuối'}")
        print("=" * 50 + "\n")

        success_cnt, fail_cnt = 0, 0

        for idx, (chap_num, chap_dir) in enumerate(chapter_folders, start=1):
            print(f"[{idx}/{total}] ({(idx/total)*100:.1f}%) Đang xử lý Chương {chap_num}...")
            
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    success = self.process_chapter_dir(chap_dir)
                    break
                except Exception as e:
                    print(f"  ❌ Lỗi thử lần {attempt}/{max_retries} ở Chương {chap_num}: {e}")
                    time.sleep(3)

            if success:
                success_cnt += 1
            else:
                fail_cnt += 1

        print("\n" + "=" * 50)
        print(f"🎉 TỔNG KẾT BATCH PROCESS:")
        print(f" Thành công: {success_cnt}/{total} chương")
        print(f" Thất bại: {fail_cnt}/{total} chương")
        print("=" * 50)

def main():
    parser = argparse.ArgumentParser(description="TTS Audio & SRT Batch Processor for Audiobooks")
    parser.add_argument(
        "--chapters-dir",
        type=str,
        default=os.path.join("data", "0502606772", "chapters"),
        help="Đường dẫn đến thư mục chứa các folder chương"
    )
    parser.add_argument("--start-chap", type=int, default=None, help="Số thứ tự chương bắt đầu")
    parser.add_argument("--end-chap", type=int, default=None, help="Số thứ tự chương kết thúc")
    args = parser.parse_args()

    runner = BatchRunner()
    runner.run_all(args.chapters_dir, start_chap=args.start_chap, end_chap=args.end_chap)

if __name__ == '__main__':
    main()


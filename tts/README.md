# TTS Audiobook & Subtitle Generator Module

Module Python độc lập dùng để tự động hóa việc đọc truyện chữ tiếng Việt qua dịch vụ TTS AI, nén âm thanh mượt mà (AAC/M4A 56kbps Mono) và tự động tạo phụ đề mốc thời gian từng câu (`.srt`).

---

## 📁 Cấu Trúc Thư Mục `tts/`

```text
tts/
├── __init__.py           # Khởi tạo Python Package
├── config.py             # Cấu hình API, Payload TTS & Thông số nén FFmpeg
├── api_client.py         # HTTP POST & Stream SSE giao tiếp với TTS Server
├── audio_processor.py    # Xử lý nén M4A (AAC Mono) & Silence Detection căn mốc SRT
├── batch_runner.py       # Kịch bản chạy Batch tự động cho tất cả các chương
└── README.md             # Hướng dẫn sử dụng
```

---

## ⚙️ Yêu Cầu Tiền Đề

1. **Python 3.8+** (Chỉ dùng các thư viện tiêu chuẩn trong Python Standard Library: `urllib`, `json`, `subprocess`, `re`, `argparse`).
2. **FFmpeg** đã được cài đặt và thêm vào PATH hệ thống (để chạy `ffmpeg`).

---

## 🚀 Cách Sử Dụng

### 1. Chạy hàng loạt tất cả các chương trong dự án:

```bash
python -m tts.batch_runner --chapters-dir data/0502606772/chapters
```

### 2. Sử dụng dưới dạng Module trong code Python riêng:

```python
from tts import BatchRunner, TTSApiClient, AudioProcessor

# 1. Chạy batch cho một thư mục bất kỳ
runner = BatchRunner()
runner.run_all("path/to/your/chapters")

# 2. Hoặc xử lý riêng cho duy nhất 1 chương
runner.process_chapter_dir("data/0502606772/chapters/1")
```

---

## 📋 Đầu Ra Mỗi Chương

Sau khi xử lý thành công, trong mỗi thư mục chương sẽ tự động tạo ra:
* `audio_chapter[N].mp3`: File MP3 gốc từ server.
* `audio_chapter[N].m4a`: File M4A nén tối ưu dung lượng (tiết kiệm ~55% dung lượng, tương thích 100% Web/App).
* `content_vi.srt`: File phụ đề chuẩn mốc thời gian từng câu (có 1 giây tạm dừng sau tiêu đề chương).

# 📖 Hướng Dẫn Sử Dụng Story Translator CLI

**Story Translator CLI** là hệ thống tự động hóa dịch thuật truyện chuyên nghiệp từ Local Dataset (hoặc cào từ web), biên tập mượt văn phong Tiếng Việt (theo chuẩn *Văn phong Hỗn hợp có kiểm soát*), thẩm định chất lượng QC chống tràn Hán tự/HTML, hỗ trợ **Multi-Worker chạy song song trên Server**, tự động gom nén và đồng bộ dữ liệu bản dịch hai chiều với Google Drive.

---

## 🚀 1. Cài Đặt Môi Trường (Setup)

### Yêu cầu hệ thống
- **Python 3.10+** (Khuyên dùng Python 3.11 hoặc 3.13)
- Kết nối Internet (OpenRouter API & Google Drive API)

### Cài đặt thư viện phụ thuộc
```bash
cd story-translator-cli
pip install -r requirements.txt
```

### Cấu hình File Môi Trường (`.env`)
Tạo file `.env` tại thư mục gốc `story-translator-cli/` với nội dung:
```env
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-api-key
OPENROUTER_MODEL=deepseek/deepseek-v4-flash-0731
TEMPERATURE_TRANSLATOR=0.3
TEMPERATURE_QC=0.1
ENABLE_QC_AUDITOR=false
SUMMARY_LAST_N=15
```

---

## 🔑 2. Cấu Hình Xác Thực Google Drive

Thư mục [`conf/`](file:///f:/Workplace/outside/test-tmp/story-translator-cli/conf) quản lý thông tin xác thực Google Drive:

1. **`conf/token.json` (Khuyên dùng):** Chứa token ủy quyền User OAuth (`nthzuzu@gmail.com`). Tự động tải/ghi đè bản dịch lên Drive mà không dính lỗi dung lượng storage quota.
2. **`conf/client_secret.json`:** OAuth Client Secret (Desktop App) dùng để cấp mới token khi hết hạn.
3. **`conf/gdrive-key.json`:** Service Account Key dùng làm phương án dự phòng.

---

## 🔄 3. Đồng Bộ Dữ Liệu Từ Drive Về Local (`sync_from_gdrive.py`)

Khi tác giả trên Drive cập nhật thêm truyện mới hoặc đăng thêm chương mới vào `chapters.zip`, bạn có thể đồng bộ toàn bộ kho hoặc đồng bộ **duy nhất 1 bộ truyện cụ thể**:

### Kịch bản 1: Đồng bộ CHỈ KÉO FILE THÔ (info.json và chapters.zip) - Khuyên dùng khi chuẩn bị dịch mới:
```bash
python sync_from_gdrive.py --type truyendichwiki --raw-only
```
*(Bỏ qua hoàn toàn ảnh bìa và translated_chapters.zip cũ trên Drive)*.

### Kịch bản 2: Đồng bộ 1 bộ truyện cụ thể:
```bash
python sync_from_gdrive.py --type truyendichwiki --story-id W_Ap1lS4CEbyOJSq --raw-only
```

### Kịch bản 3: Đồng bộ toàn bộ các truyện thuộc 1 kho cụ thể:
```bash
python sync_from_gdrive.py --type novel543
```

### Kịch bản 3: Đồng bộ toàn bộ tất cả các kho truyện trên Drive:
```bash
python sync_from_gdrive.py
```

---

## 💻 4. Dịch Đơn Bộ Truyện Cụ Thể (`main.py`)

Dành cho nhu cầu chạy thử nghiệm, kiểm tra chất lượng hoặc dịch từng bộ truyện độc lập:

### 🟢 Kịch bản 1: Dịch tiếp các chương còn thiếu (`--resume`)
* Tự động giải nén `translated_chapters.zip` (nếu có), **bỏ qua các chương đã dịch** và tiếp tục dịch các chương còn lại:
```bash
# Dịch thêm 200 chương tiếp theo và đẩy lên Google Drive:
python main.py --source "../storage/truyendichwiki/WOqruu8h7AsKxRYh" --chapters 200 --resume --upload-gdrive

# Dịch một mạch TOÀN BỘ tất cả các chương còn lại cho đến khi FULL 100%:
python main.py --source "../storage/truyendichwiki/WOqruu8h7AsKxRYh" --chapters 0 --resume --upload-gdrive
```

---

### 🔴 Kịch bản 2: Dịch lại từ đầu từ Chương 1 (`--retranslate`)
* Khi truyện bị dịch lỗi hoặc muốn đổi model dịch lại với văn phong mới: Tự động xóa sạch bản dịch cũ, checkpoints, summary và log cũ (bảo tồn nguyên vẹn `info.json` và `chapters.zip`), sau đó dịch mới 100% từ Chương 1:
```bash
# Dịch lại từ đầu 200 chương đầu tiên:
python main.py --source "../storage/truyendichwiki/X7Yb6VS4CDNFzfcB" --chapters 200 --retranslate --upload-gdrive

# Dịch lại từ đầu cho đến khi FULL 100% truyện:
python main.py --source "../storage/truyendichwiki/X7Yb6VS4CDNFzfcB" --chapters 0 --retranslate --upload-gdrive
```

---

### 🎯 Kịch bản 3: Dịch Chỉ Định 1 Chương, Khoảng Chương Hoặc Danh Sách Chương
* Hệ thống sẽ dịch chính xác các chương được chỉ định, cập nhật đè an toàn vào `translated_chapters.zip`, `summary.txt`, `checkpoints.json` và bảo toàn 100% các chương khác:

```bash
# 1. Chỉ dịch đúng DUY NHẤT Chương 34:
python main.py --source "../storage/truyendichwiki/Yee9N1S4CHauW96H" --chapter 34 --upload-gdrive

# 2. Dịch đúng một khoảng từ Chương 10 đến Chương 20:
python main.py --source "../storage/truyendichwiki/Yee9N1S4CHauW96H" --chapter-range 10 20

# 3. Dịch theo danh sách các chương bất kỳ (cách nhau bởi dấu cách hoặc dấu phẩy):
python main.py --source "../storage/truyendichwiki/Yee9N1S4CHauW96H" --chapters-list 1 5 12 34 80

# 4. Hỗ trợ kết hợp dải và số rời rạc:
python main.py --source "../storage/truyendichwiki/Yee9N1S4CHauW96H" --chapters-list 1-5 10 20-25
```

---

### 💡 Bảng Tham Số (Arguments) Của `main.py`:
| Tham số | Dạng | Ý nghĩa & Mô tả | Mặc định |
| :--- | :--- | :--- | :--- |
| `--source` | `String` | **(Bắt buộc)** Đường dẫn tới thư mục truyện local (chứa `info.json` và `chapters.zip`). | *(Bắt buộc)* |
| `--chapters` | `Integer` | Số lượng chương cần dịch theo thứ tự (`0` là dịch TOÀN BỘ các chương còn lại). | `5` |
| `--chapter` | `Integer` | Chỉ định dịch chính xác **DUY NHẤT 1 chương** cụ thể (Ví dụ: `--chapter 34`). | `None` |
| `--chapter-range` | `Int Int` | Chỉ định dịch một **khoảng chương [Start End]** (Ví dụ: `--chapter-range 10 20`). | `None` |
| `--chapters-list` | `List/Str` | Chỉ định **danh sách các chương bất kỳ** (Ví dụ: `--chapters-list 1 5 12 34` hoặc `1-5 10`). | `None` |
| `--resume` | `Flag` | **Dịch tiếp:** Khôi phục tiến độ và bỏ qua các chương đã dịch. *(Loại trừ với `--retranslate`)*. | `False` |
| `--retranslate` | `Flag` | **Dịch lại từ đầu:** Xóa sạch toàn bộ bản dịch cũ và dịch mới từ Chương 1. *(Loại trừ với `--resume`)*. | `False` |
| `--upload-gdrive` | `Flag` | Tự động nén và tải/ghi đè `translated_chapters.zip` lên Google Drive sau khi dịch xong. | `False` |
| **Auto-Cleanup** | *Tự động* | Sau khi đóng gói `translated_chapters.zip` thành công, thư mục giải nén `chapters/` sẽ tự động được xóa để giải phóng ổ cứng. | *Bật sẵn* |

---

## 🚜 5. Bộ Điều Phối Hàng Loạt Multi-Worker (`batch_runner.py`)

Dành cho kịch bản triển khai trên **Server / VPS** với nhiều Worker chạy song song nhiều bộ truyện cùng lúc mà **không bao giờ đụng độ nhau** nhờ cơ chế khóa file nguyên tử `.lock`.

### 1. Dịch Hàng Loạt Các Truyện Đang Dịch Dở (`--mode resume`):
```bash
# Quét kho truyendichwiki, mở 4 Worker song song dịch tiếp các bộ đang dở:
python batch_runner.py --type truyendichwiki --mode resume --workers 4 --target-chapters 200 --upload-gdrive
```

### 2. Dịch Cho Các Truyện Mới Tinh (Ưu tiên truyện ngắn/ít chương trước):
```bash
# Quét kho truyendichwiki, mở 4 Worker song song, ưu tiên các truyện ít chương nhất dịch trước:
python batch_runner.py --type truyendichwiki --mode new --workers 4 --target-chapters 200 --sort-shortest --upload-gdrive
```

### 3. Dịch Lại Hàng Loạt Từ Đầu (`--mode retranslate`):
```bash
python batch_runner.py --type truyendichwiki --mode retranslate --workers 4 --target-chapters 200 --sort-shortest --upload-gdrive
```

### 4. Dịch Chỉ Định Danh Sách Các Bộ Truyện Cụ Thể (`--stories` / `--stories-file`):
```bash
# Chỉ định danh sách Story ID trực tiếp trên dòng lệnh:
python batch_runner.py --type truyendichwiki --stories YPire1S4CAhlFVsL YM06B1S4CH1RVTQP X7Yb6VS4CDNFzfcB --workers 3 --upload-gdrive

# Đọc danh sách Story ID từ file text 'danh_sach_can_dich.txt' (mỗi dòng 1 ID):
python batch_runner.py --type truyendichwiki --stories-file "danh_sach_can_dich.txt" --workers 4 --upload-gdrive
```

### 5. Tùy chọn Kéo Data Từng Truyện Trước Khi Dịch (`--sync-first`):
```bash
# Mỗi khi Worker nhận 1 truyện, tự kéo data mới nhất của truyện đó từ Drive về trước khi dịch:
python batch_runner.py --type novel543 --mode new --workers 3 --sync-first --raw-only --upload-gdrive
```

---

### 💡 Bảng Tham Số Của `batch_runner.py`:

| Tham số | Dạng | Ý nghĩa & Mô tả | Mặc định |
| :--- | :--- | :--- | :--- |
| `--type` | `String` | **BẮT BUỘC:** Nhóm kho truyện (`truyendichwiki`, `novel543` hoặc `all`). | *(Bắt buộc)* |
| `--mode` | `String` | Mode hoạt động: `new` (dịch 200 chap đầu), `resume` (dịch nốt), `retranslate` (dịch lại từ đầu) hoặc `all`. | `new` |
| `--stories ID1 ID2` | `List` | **Danh sách CẦN DỊCH:** Chỉ quét và dịch đúng các Story ID được chỉ định. | `None` |
| `--stories-file PATH` | `String` | Đường dẫn file `.txt` chứa danh sách Story ID cần dịch (mỗi dòng 1 ID). | `None` |
| `--workers N` | `Integer` | **Dịch song song:** Số lượng bộ truyện dịch cùng một lúc trong 1 Terminal. | `1` |
| `--max-stories N` | `Integer` | **Khóa ngân sách:** Tối đa `N` bộ truyện rồi dừng hẳn (`0` là không giới hạn). | `0` |
| `--target-chapters N` | `Integer` | Số chương cho mỗi đợt dịch (`0` là dịch FULL TOÀN BỘ). | `200` |
| `--sort-shortest` | `Flag` | **Ưu tiên truyện ngắn:** Đưa các bộ truyện ít chương nhất lên đầu dịch trước. | `False` |
| `--upload-gdrive` | `Flag` | Tự động nén `translated_chapters.zip` và push Drive. | `False` |
| `--sync-first` | `Flag` | Tự động kéo data mới nhất trên Drive của ĐÚNG BỘ TRUYỆN ĐÓ về trước khi dịch. | `False` |
| `--raw-only` | `Flag` | Khi bật `--sync-first`, chỉ kéo `info.json` và `chapters.zip` (bỏ qua ảnh bìa và bản dịch cũ). | `False` |
| `--exclude ID1 ID2` | `List` | **Danh sách loại trừ:** Bỏ qua các bộ truyện chỉ định (không dịch). Ví dụ: `--exclude X7Yb6VS4CDNFzfcB`. | `None` |
| `--exclude-file PATH` | `String` | Đường dẫn file `.txt` chứa danh sách Story ID cần bỏ qua (mỗi dòng 1 ID). | `None` |

---

## 🔍 6. Quét & Báo Cáo Tiến Độ Toàn Bộ Kho Truyện (`scan_translation_status.py`)

Tiện ích quét tiến độ siêu tốc **đọc trực tiếp header file zip trong bộ nhớ RAM trong 3 giây**:

```bash
# 1. Quét và in bảng tiến độ toàn bộ kho:
python scan_translation_status.py --root_dir ../storage/truyendichwiki

# 2. Lọc danh sách các truyện ĐÃ DỊCH FULL (100%):
python scan_translation_status.py --root_dir ../storage/truyendichwiki --filter full

# 3. Lọc danh sách các truyện ĐANG DỊCH DỞ (cần resume):
python scan_translation_status.py --root_dir ../storage/truyendichwiki --filter partial

# 4. Lọc danh sách các truyện CHƯA DỊCH (0%):
python scan_translation_status.py --root_dir ../storage/truyendichwiki --filter not_started

# 5. Xuất báo cáo ra file CSV:
python scan_translation_status.py --root_dir ../storage/truyendichwiki --export tien_do.csv
```

---

## 📊 7. Cấu Trúc Lưu Trữ Sau Khi Dịch Xong

Nhờ cơ chế **Auto-Cleanup**, mỗi bộ truyện sau khi dịch xong luôn duy trì trạng thái **cực kỳ gọn gàng (chỉ 5-6 file nén/metadata)**:

```text
storage/truyendichwiki/WOqruu8h7AsKxRYh/
├── info.json                 (Metadata truyện: Tên, Tác giả, Thể loại, Tags...)
├── chapters.zip              (Dữ liệu thô gốc tiếng Trung / Convert)
├── translated_chapters.zip   (Bản dịch hoàn tất, sẵn sàng đẩy lên Drive)
├── glossary.json             (Từ điển nhân vật & thuật ngữ tự động tích lũy)
├── summary.txt               (Nhật ký tóm tắt 15 chương gần nhất)
└── checkpoints.json          (Lịch sử commit tiến độ từng chương)
```

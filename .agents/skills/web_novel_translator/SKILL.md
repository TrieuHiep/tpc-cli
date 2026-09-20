---
name: "dich_truyen_web"
description: "Tự động dịch và biên tập truyện từ Local Dataset (info.json + chapters/) hoặc cào từ truyendichwiki.net, phân tích bối cảnh/tags, trích xuất bảng thuật ngữ glossary, biên tập mượt hóa văn phong Tiếng Việt và kiểm duyệt QC chống tràn context."
---

# Hướng Dẫn Antigravity Thực Thi Workflow Dịch & Biên Tập Truyện Automated (`dich_truyen_web`)

Khi người dùng yêu cầu dịch/biên tập truyện từ **Thư mục Local Dataset** (có `info.json` & `chapters/`) hoặc từ `truyendichwiki.net`, Antigravity **BẮT BUỘC THỰC HIỆN ĐỦ 100% CÁC BƯỚC** theo đúng trình tự dưới đây.

## ⚠️ CHECKLIST BẮT BUỘC THỰC HIỆN TỪNG BƯỚC:

- [ ] **Bước 1: Nạp Dữ Liệu Đầu Vào & Bootstrapping Metadata**
  - **Nguồn Local (Ưu tiên):** Nạp `info.json` & đọc các file `chapters/[Chương]/content.txt`.
  - **Nguồn Web:** Tải từng trang chương thô lưu vào `data/raw_chapters/chap_XXXX.txt`.
  - Trích xuất Tên truyện, Tác giả, Thể loại, Tags, Tóm tắt cốt truyện và Nữ chính x Nam chính để tạo `[dataset_dir]/glossary.json` & `[dataset_dir]/summary.txt` ban đầu (nằm trực tiếp TRONG thư mục bộ truyện).
- [ ] **Bước 2: Dynamic Glossary Filtering & Context Injection**
  - Lọc 20-50 terms xuất hiện trong các chương của batch/chương hiện tại từ `[dataset_dir]/glossary.json`. Nạp bối cảnh tóm tắt các chương trước (`summary.txt`).
- [ ] **Bước 3: Dịch thuật & Biên tập Mượt (Translator Subagent - Automated Spawning với DeepSeek Tone Steering & Commonsense Check)**
  - Tự động spawn `Translator Subagent` áp dụng **Bộ lọc tính hợp lý đời thực & 5 Nguyên lý dịch thuật sâu**.
  - 🔴 **Anti-Abridgment Mandate:** Dịch toàn văn 100% chi tiết bám sát nội dung gốc (Full Verbatim Narrative Translation). CẤM TUYỆT ĐỐI tóm tắt, cấm lược dịch, cấm gộp đoạn hay cắt xén lời thoại/miêu tả. Tỷ lệ ký tự Vi/Zh bắt buộc $\ge 1.2$, số từ tiếng Việt phải tương đương raw Trung ($\ge 1.500$ từ/chương).
  - **Tự động xử lý & suy luận tiêu đề chương:** Nếu truyện gốc có tiêu đề thì dịch mượt; nếu raw khuyết tiêu đề (chỉ có `第X章` hoặc `无题`) thì bắt buộc **tự suy luận 1 tiêu đề ngắn gọn (3-8 từ)** phản ánh sự kiện chính trong chương.
  - Đối với batch nhiều chương (>= 10 chương), subagent đọc và ghi lần lượt từng file `chapters/[Chương]/content_vi.txt` tương ứng.
  - Trích xuất tự động `extracted_new_terms` (danh từ riêng mới) và tóm tắt diễn biến (`chapter_summary` hoặc `batch_summary`).
- [ ] **Bước 4: QC Thẩm định & Làm sạch Hán tự & Thẻ HTML (QC Auditor Subagent - Automated Spawning)**
  - Kiểm duyệt độc lập theo từng batch/chương tương ứng.
  - 🔴 **In-Flight Batch QC Gate:** Đo độ dài từng file, kiểm tra tỷ lệ Vi/Zh $\ge 1.2$ và số từ $\ge 1.000$ từ. Nếu phát hiện tóm tắt / cắt gọt, bắt buộc từ chối và yêu cầu translator dịch lại ngay lập tức.
  - Quét 100% không còn chữ Hán / rác convert / thẻ HTML.
- [ ] **Bước 5: Commit Sản Phẩm & Reset Context Session (Chống tràn Memory / Context Window 1,000+ Chương)**
  - Ghi file kết quả dưới dạng **Văn bản thuần túy (Plain Text, KHÔNG CHỨA BẤT KỲ THẺ HTML NÀO NHƯ `<p>`, `</p>`)** trực tiếp vào `chapters/[Chương]/content_vi.txt`.
  - 🔴 **Quy chuẩn cấu trúc file `content_vi.txt` phục vụ nạp CSDL tự động:** Dòng đầu tiên BẮT BUỘC là `Chương [X]: [Tiêu đề chương]` (lấy từ tiêu đề dịch hoặc đã suy luận ở Bước 3), theo sau là một dòng trống `\n\n`, sau đó mới đến nội dung chi tiết của chương.
  - **Agent chính BẮT BUỘC cập nhật LẬP TỨC** `[dataset_dir]/glossary.json` & `[dataset_dir]/summary.txt` ngay sau mỗi chương/batch.

---

## 1. Tham Số Đầu Vào (Inputs)
- **`source`**: Thư mục truyện local HOẶC URL web.
- **`max_chapters`**: Tổng số lượng chương cần dịch/biên tập.
- **`batch_size`**: Kích thước batch phân bổ cho mỗi Subagent Session (BẮT BUỘC tuân thủ `AGENTS.md`):
  * **Truyện dài (>= 10 chương):** Mặc định `batch_size = 10` chương / Subagent Session.
  * **Truyện ngắn / Vừa (< 10 chương):** Mặc định `batch_size = 1` chương / Subagent Session (1 Chapter = 1 Session độc lập).
- **`output_dir`**: Thư mục lưu kết quả.

---

## 2. Chi Tiết Lệnh & Quy Trình Thực Thi Subagent Automation (STRICT SEQUENTIAL)

### A. Quy tắc Phân Bổ Subagent Session theo Quy Mô Truyện (BẮT BUỘC theo AGENTS.md):
- **Truyện ngắn / Vừa (< 10 chương):** Thực thi **1 Chapter = 1 Subagent Session** (Mỗi chương kích hoạt 1 `translator_subagent` session độc lập hoàn toàn).
- **Truyện dài (>= 10 chương):** Thực thi **10 Chapters = 1 Subagent Session** (Gom cụm thành các batch 10 chương: ví dụ cụm 1: [1..10], cụm 2: [11..20]...):
  * Trong mỗi batch 10 chương: Kích hoạt 1 `translator_subagent` session duy nhất để dịch và ghi lần lượt các file `content_vi.txt` của 10 chương đó.
  * Sau khi Translator hoàn thành 100% cả batch, kích hoạt 1 `qc_auditor_subagent` session để thẩm định độc lập toàn bộ các file vừa tạo trong batch đó.
  * Agent chính cập nhật ngay các thuật ngữ mới vào `glossary.json` và tóm tắt vào `summary.txt` trước khi chuyển sang batch 10 chương tiếp theo.
  * Reset context hoàn toàn sau mỗi batch để chống tràn bộ nhớ (Stateless Execution).

### B. Thứ Tự Tuần Tự Nghiêm Ngặt Trong Mỗi Batch/Chương:
Antigravity **BẮT BUỘC** thực hiện quy trình Multi-Subagent theo đúng thứ tự tuần tự nghiêm ngặt:
1. Khởi tạo `translator_subagent` và `qc_auditor_subagent` via `define_subagent` với tham số `enable_write_tools: true` (BẮT BUỘC để subagents có công cụ `write_to_file`, `replace_file_content`, `run_command` trực tiếp lưu/sửa file `content_vi.txt`).
2. **Kích hoạt `translator_subagent` ĐẦU TIÊN** via `invoke_subagent` để dịch và lưu các file `content_vi.txt`.
   - 🔴 **QUY TẮC HEADLESS CLI:** Tuyệt đối KHÔNG xuất tin nhắn trò chuyện (chat text) trung gian sau khi `invoke_subagent`. Hãy im lặng kết thúc lượt công cụ để CLI chờ nhận phản hồi từ subagent.
3. **CHỜ `translator_subagent` HOÀN THÀNH 100%**.
4. **Kích hoạt `qc_auditor_subagent` CUỐI CÙNG** via `invoke_subagent` để kiểm duyệt QC các chương vừa dịch (cũng không xuất tin nhắn trung gian).
5. Cập nhật `glossary.json` và `summary.txt` từ kết quả trả về trước khi tiếp tục thực thi batch tiếp theo.
6. Lặp lại liên tục qua toàn bộ các batch cho đến chương cuối cùng, và chỉ xuất bảng báo cáo nghiệm thu tổng kết kèm `<!-- GOAL_COMPLETE -->` sau khi toàn bộ file đã tồn tại trên đĩa.

---

## 3. 🔥 BỘ QUY TẮC DỊCH THUẬT & BIÊN TẬP VĂN HỌC SÂU (Production-Grade Prompting)

Khi cấu hình `translator_subagent` hoặc gửi prompt dịch thuật, **BẮT BUỘC NẠP TOÀN BỘ CÁC NGUYÊN LÝ SAU VÀO SYSTEM PROMPT**:

### A. 4 NGUYÊN LÝ GIẢI MÃ NGỮ NGHĨA SÂU & BỘ LỌC ĐỜI THỰC (COMMONSENSE SENSE-CHECK):
1. **Khử Nhiễu Bản Thô Convert (De-noising Directive):**
   - Văn bản đầu vào là bản Convert Hán-Việt thô từ phần mềm cũ (chữ-đổi-chữ). Tuyệt đối KHÔNG ĐƯỢC tin vào mặt chữ tiếng Việt thô và không dịch lắp ghép từ bề mặt. Hãy luôn truy tìm ý đồ thực sự và bản chất câu chuyện.
2. **Bộ Lọc Tính Hợp Lý Đời Thực (Commonsense Sense-Check):**
   - Luôn tự vấn trước khi hạ bút: Đặt vào bối cảnh xã hội, tâm lý nhân vật và đời thực, câu văn này có hợp lý và có nghĩa không?
   - 👉 **Quy tắc vàng:** Nếu câu dịch nghe phi lý, kỳ quặc, vô nghĩa hoặc ngô nghê trong tiếng Việt (ví dụ: *"sinh viên tốt nghiệp đi ăn bánh trái"*, *"bị đóng cửa ăn canh"*, *"hệ thống hỏi có bao nhiêu tích phân"*...) $\rightarrow$ **100% ĐÓ LÀ BẪY TỪ ĐA NGHĨA / BẪY THÀNH NGỮ CONVERT, BẮT BUỘC PHẢI DỊCH THOÁT Ý THEO NGHĨA BÓNG VÀ HOÀN CẢNH THỰC TẾ!**
3. **Giải Mã Ẩn Dụ & Thành Ngữ Tiếng Trung (Metaphor & Idiom Decoding):**
   - Tiếng Trung dùng dày đặc hình ảnh ẩn dụ (đồ ăn: bánh trái, giấm, đậu phụ, trà xanh; hành động: đào góc tường, ôm đùi, cắm sừng, kéo chân sau...).
   - **Bắt buộc dịch ra bản chất hành động thực tế:** Ăn giấm $\rightarrow$ Ghen tuông; Hương bánh trái $\rightarrow$ Nhân tài đắt giá / Đối tượng săn đón; Ăn đậu phụ $\rightarrow$ Sàm sỡ / Trêu ghẹo; Đào góc tường $\rightarrow$ Giật bồ / Cướp người; Ôm đùi $\rightarrow$ Dựa dẫm đại gia.
4. **Dịch Theo Ý Nghĩa, Tự Do Cấu Trúc Câu (Sense-for-Sense Translation):**
   - Hoàn toàn thả tự do cấu trúc câu, tự do ngắt nghỉ, đảo ngữ pháp, viết lại câu văn để đạt độ mượt mà, trôi chảy và giàu chất văn học hiện đại.
5. **Bảo Toàn Dung Lượng & Anti-Abridgment Mandate (CẤM TÓM TẮT TUYỆT ĐỐI):**
   - Dịch toàn văn 100% bám sát tình tiết gốc (Full Verbatim Narrative Translation). Việc "biên tập mượt mà" TUYỆT ĐỐI KHÔNG ĐỒNG NGHĨA với "lược bỏ hay tóm tắt".
   - CẤM TUYỆT ĐỐI tóm tắt diễn biến, cấm gộp đoạn tùy tiện, cấm bỏ sót lời thoại, miêu tả tâm lý hay bối cảnh. Ràng buộc định lượng: Tỷ lệ ký tự Vi/Zh bắt buộc $\ge 1.2$, số từ tiếng Việt phải đạt từ 1.500 – 3.500 từ/chương (tương đương số chữ Hán raw). Bất kỳ chương nào dưới 1.000 từ hoặc Vi/Zh < 1.0 đều là lỗi phế phẩm nghiêm trọng!

---

### B. VĂN PHONG HỖN HỢP CÓ KIỂM SOÁT (GENRE-ADAPTIVE):
- **Khu vực giữ Hán Việt (Ưu tiên cao):** Thuật ngữ hệ thống (cảnh giới, kỹ năng, pháp bảo, môn phái, tu vi, thần thức, linh lực, đại đạo, kiếp nạn...), xưng hô tôn ti (bản vương, đạo hữu, sư tôn, tiên sinh, công tử, lão phu...), từ ngữ tạo không khí cổ kính (*sát khí, thiên cơ, kỳ ngộ, phong tư, uy áp*), thành ngữ/điển cố.
- **Khu vực thuần Việt hóa:** Lời thoại đời thường, hội thoại cảm xúc, miêu tả hành động hàng ngày. Đảo ngữ pháp tiếng Trung sang tiếng Việt tự nhiên.
- **Kiểm soát mật độ:** Không nhồi nhét Hán Việt quá dày trong một đoạn văn, xen kẽ tự nhiên theo nhịp điệu truyện.

---

### C. TỪ ĐIỂN BẮT LỖI CONVERT & BẪY ĐA NGHĨA MỞ RỘNG (BẮT BUỘC THAY THẾ):
- `nguyên lai` $\rightarrow$ `hóa ra` hoặc `thì ra`
- `bất quá` $\rightarrow$ `nhưng mà`, `dù sao` hoặc `có điều`
- `phi thường` / `thập phần` $\rightarrow$ `vô cùng`, `hết sức` hoặc `cực kỳ`
- `thanh âm` $\rightarrow$ `giọng nói`, `âm thanh` hoặc `tiếng động`
- `nhãn thần` $\rightarrow$ `ánh mắt` hoặc `ánh nhìn`
- `sắc mặt nan khán` $\rightarrow$ `sắc mặt khó coi`, `mặt mày xám xịt` hoặc `nét mặt sa sầm`
- `hít một hơi lãnh khí` $\rightarrow$ `hít sâu một hơi khí lạnh` hoặc `bất giác rùng mình`
- `khủng bố như tư` $\rightarrow$ `đáng sợ đến như vậy` hoặc `kinh khủng đến mức này`
- `khóe miệng trừu súc` $\rightarrow$ `khóe miệng giật giật` hoặc `méo mặt`
- `thân hình nhất trệ` $\rightarrow$ `bước chân khựng lại` hoặc `người khẽ dừng lại`
- `bối tích phát lương` $\rightarrow$ `sống lưng lạnh toát` hoặc `lạnh buốt sống lưng`
- `tích phân` / `积分` trong bối cảnh Hệ thống/Game $\rightarrow$ `điểm tích lũy`, `điểm hệ thống`, `điểm thưởng` (🔴 CẤM dịch thành 'tích phân')
- `khấu phân` $\rightarrow$ `trừ điểm`, `gia phân` $\rightarrow$ `cộng điểm`
- `hảo cảm độ` $\rightarrow$ `độ thiện cảm`, `hắc hóa trị` $\rightarrow$ `chỉ số hắc hóa`
- `sinh mệnh trị` $\rightarrow$ `thanh máu` / `chỉ số sinh mệnh`, `kinh nghiệm trị` $\rightarrow$ `điểm kinh nghiệm`
- `mãi đơn` $\rightarrow$ `tính tiền / thanh toán`, `đả xa` $\rightarrow$ `bắt taxi / đặt xe`, `ngật thố` $\rightarrow$ `ghen tuông`
- `香饽饽` / `hương bánh trái` $\rightarrow$ `đối tượng được săn đón`, `nhân tài đắt giá` hoặc `món hàng hot`
- `吃香` / `ngật hương` $\rightarrow$ `được ưa chuộng`, `rất có giá` hoặc `được trọng dụng`
- `吃豆腐` / `ngật đậu hủ` $\rightarrow$ `sàm sỡ`, `trêu ghẹo` hoặc `lợi dụng`
- `开小灶` / `khai tiểu táo` $\rightarrow$ `ưu ái chăm sóc riêng`, `nấu riêng` hoặc `dạy kèm riêng`
- `吃闭门羹` / `ngật bế môn canh` $\rightarrow$ `bị cự tuyệt`, `bị từ chối thẳng thừng` hoặc `bị đóng cửa không tiếp`
- `喝西北风` / `hát tây bắc phong` $\rightarrow$ `húp gió tây bắc`, `nhịn đói` hoặc `cạp đất mà ăn`
- `炒鱿鱼` / `sao du ngư` $\rightarrow$ `bị sa thải / bị đuổi việc`, `戴绿帽子` $\rightarrow$ `bị cắm sừng`
- 🔴 **TUYỆT ĐỐI KHÔNG DÙNG TIẾNG LÓNG MẠNG THÔ THIỂN CỦA GIỚI TRẺ TRUNG QUỐC (Internet Slang / Netizen Jargon):**
  * *Nguyên nhân:* Những cụm từ này là tiếng lóng mạng rập khuôn, thô thiển, làm câu văn lủng củng, kỳ quặc, thiếu tính văn học, người đọc ở các lứa tuổi khác nhau rất khó hiểu hoặc gây phản cảm. Bắt buộc phải dịch thoát ý sang tiếng Việt chuẩn văn học tự nhiên, dễ hiểu:
    * `kiếp trâu ngựa` / `ngưu mã` / `牛马` $\rightarrow$ `làm lụng vất vả / phận làm thuê cực nhọc / thân phận thấp cổ bé họng / cày cuốc ngày đêm` (CẤM giữ nguyên "kiếp trâu ngựa / làm trâu làm ngựa cho tư bản")
    * `bò long sàng` / `bò lên long sàng` / `爬龙床` $\rightarrow$ `trèo lên giường vua / quyến rũ hoàng thượng / trèo cành cao`
    * `xoát hảo cảm` / `xoát độ hảo cảm` / `刷好感` $\rightarrow$ `lấy lòng / tạo thiện cảm / ghi điểm trong mắt ai đó` (CẤM dùng từ "xoát")
    * `hố cha` / `keng điệt` / `坑爹` $\rightarrow$ `bẫy người / lừa đảo / hại người / chơi khăm / xui xẻo / tức chết đi được`
    * `bạch liên hoa` / `白莲花` $\rightarrow$ `đạo đức giả / giả tạo / ra vẻ ngây thơ thánh thiện / miệng nam mô bụng một bồ dao găm`
    * `cái chết xã hội` / `xã tử` / `社死` $\rightarrow$ `mất mặt trước bàn dân thiên hạ / ngượng chín người / xấu hổ muốn độn thổ / bẽ mặt nhục nhã`
    * `trà xanh` / `绿茶` $\rightarrow$ `kẻ trơ trẽn / giả vờ ngây thơ / tiểu tam mưu mô`
    * `ăn dưa` / `ngật qua` / `吃瓜` $\rightarrow$ `hóng chuyện / hóng hớt / xem kịch vui / đứng ngoài xem trò hay`
    * `nằm ngửa` / `thảng bình` / `躺平` $\rightarrow$ `buông xuôi / mặc kệ đời / an phận thủ thường`
    * `bại gia` / `bại gia tử` $\rightarrow$ `phá gia chi tử / kẻ hoang phí`
    * `bạo kích` $\rightarrow$ `đòn giáng nặng nề / cú sốc lớn / đả kích đau đớn`
    * `thổ tào` / `nhổ nước bọt` $\rightarrow$ `châm chọc / mỉa mai / bóc mẽ / càu nhàu`
    * `vả mặt` / `đả kiểm` $\rightarrow$ `bẽ mặt / tự vỗ vào mặt mình / gậy ông đập lưng ông`
    * `tiểu thịt tươi` $\rightarrow$ `chàng trai trẻ tuấn tú / mỹ nam trẻ tuổi`
- Mượt hóa chú thích/meme: CẤM dịch word-by-word `腦子寄存處` $\rightarrow$ Dịch mượt: `[Lời tác giả: Truyện thuộc thể loại hài hước hóm hỉnh, đọc thuần giải trí xả stress...]`.
- 🔴 **LOẠI BỎ RÁC QUẢNG CÁO & DỰ THU TRUYỆN:** Cắt bỏ 100% các đoạn tác giả tự quảng cáo truyện mới, xin phiếu/hoa/donate ở đầu/cuối chương.

---

### D. MẪU DỊCH ĐỐI CHIẾU THAM CHIẾU (FEW-SHOT EXEMPLARS):
- **Mẫu 1 (Hội thoại & Cảm xúc):**
  * *Convert thô:* `Hắn nhãn thần lộ ra một vệt ngưng trọng, thanh âm băng lãnh nói: "Ngươi nguyên lai bất quá chỉ là ếch ngồi đáy giếng."`
  * *Dịch văn học chuẩn:* `Ánh mắt hắn thoáng hiện vẻ ngưng trọng, giọng nói lạnh như băng: "Hóa ra ngươi cũng chỉ là một con ếch ngồi đáy giếng mà thôi."`
- **Mẫu 2 (Miêu tả thần thái & Cổ trang):**
  * *Convert thô:* `尾羽染着薄薄的胭脂色，瞳黑如墨`
  * *Dịch văn học chuẩn:* `Đuôi mắt ửng lên sắc yên chi mỏng, đồng tử đen bóng như mực, tựa yêu quái sắp sửa mê hoặc lòng người.`

---

### E. QUY TẮC XỬ LÝ VÀ TỰ ĐỘNG SUY LUẬN TIÊU ĐỀ CHƯƠNG (CHAPTER TITLE INFERENCE):
- **Mục đích:** Đảm bảo 100% các chương đều có tiêu đề hoàn chỉnh phục vụ tự động nạp CSDL (Database Ingestion) và hiển thị mục lục trên Web/App đọc truyện.
- **Quy chuẩn bắt buộc cấu trúc file `content_vi.txt`:**
  ```text
  Chương {X}: {Tiêu đề chương}

  {Toàn bộ nội dung bản dịch mượt mà tiếng Việt, phân tách các đoạn bằng \n\n...}
  ```
- **Quy tắc trích xuất và suy luận:**
  * **Trường hợp 1 (Raw đã có tiêu đề):** Dịch thoát ý, mượt mà tiêu đề sang tiếng Việt theo ngữ cảnh chương. Ví dụ: `第10章 偶遇故人` $\rightarrow$ `Chương 10: Tình cờ gặp lại cố nhân`.
  * **Trường hợp 2 (Raw KHÔNG CÓ tiêu đề, chỉ có `第X章` hoặc ghi `无题` / `Vô đề`):** Translator Subagent **BẮT BUỘC phải đọc lướt nội dung, nắm bắt sự kiện/xung đột then chốt nhất của chương để tự động suy luận ra 1 tiêu đề ngắn gọn (từ 3 đến 8 từ)**, súc tích, hấp dẫn và chuẩn phong cách của thể loại truyện (ví dụ: `Chương 10: Sóng gió sàn đấu giá`, `Chương 25: Quyết định bất ngờ`). CẤM để trơ trọi mỗi `Chương 10` hay ghi chung chung vô nghĩa.

---

### F. CẤU TRÚC ĐẦU RA STRUCTURED OUTPUT CỦA SUBAGENT:
Translator Subagent BẮT BUỘC trả về dữ liệu có cấu trúc:

**1. Đối với dịch 1 chương lẻ (< 10 chương):**
```json
{
  "chapter_title_vi": "Chương {X}: {Tiêu đề chương dịch hoặc tự suy luận}",
  "translated_content": "Toàn bộ nội dung bản dịch mượt tiếng Việt (Dòng đầu tiên là 'Chương {X}: {Tiêu đề}', tiếp theo là dòng trống, rồi đến nội dung Plain Text, ngắt đoạn bằng \\n\\n, KHÔNG CÓ THẺ HTML)",
  "extracted_new_terms": {
    "ChữHánNhânVật1": "TênTiếngViệt1",
    "ChữHánĐịaDanh1": "TênĐịaDanhTiếngViệt1"
  },
  "chapter_summary": "Tóm tắt 2-3 câu ngắn diễn biến chính của chương"
}
```

**2. Đối với dịch theo batch (>= 10 chương):**
Subagent tự động dùng công cụ file để tạo và lưu trực tiếp toàn bộ các file `chapters/[Chương]/content_vi.txt` cho từng chương trong batch, sau đó trả về dữ liệu tổng hợp:
```json
{
  "translated_chapters": [
    {"chapter": 201, "title": "Chương 201: Tiêu đề chương", "file": "chapters/201/content_vi.txt"},
    {"chapter": 202, "title": "Chương 202: Tiêu đề chương", "file": "chapters/202/content_vi.txt"}
  ],
  "extracted_new_terms": {
    "ChữHán1": "TiếngViệt1"
  },
  "batch_summary": "Tóm tắt 3-5 câu diễn biến chính của toàn bộ cụm chương trong batch"
}
```

---

## 4. Mẫu Báo Cáo Kết Quả Workflow (Report Template)

```markdown
### 📊 Báo Cáo Kết Quả Thẩm Định Dịch Truyện Subagent Workflow

| Chương | Điểm QC | Trạng thái | Đơn vị thực thi Subagent |
| :--- | :---: | :---: | :--- |
| Chương 01 | 10.0 / 10 | PASSED ✅ | translator_subagent (dfdda025...) |
| Chương 02 | 10.0 / 10 | PASSED ✅ | translator_subagent (642f0be5...) |
```

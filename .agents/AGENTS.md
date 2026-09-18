# Quy Tắc Dự Án: Dịch & Biên Tập Truyện Tránh Lỗi Convert (truyendichwiki.net & Local Dataset)

Khi làm việc trong workspace `truyen-online`, Antigravity và các subagent cần tuân thủ tuyệt đối các quy tắc sau:

1. **Tuân thủ 100% các bước trong SKILL workflow (BẮT BUỘC CHECKLIST):**
   Mỗi khi thực thi dịch thuật/biên tập theo skill `dich_truyen_web` (hoặc `dich_truyen`), Agent KHÔNG ĐƯỢC BỎ BẤT KỲ BƯỚC NÀO trong 5 bước chính:
   - [ ] **Bước 1:** Nạp dữ liệu thô (Đọc từ Local Dataset `info.json` + `chapters/` hoặc Web Crawl) & Trích xuất Metadata khởi tạo `<dataset_dir>/glossary.json` + `<dataset_dir>/summary.txt` (nằm trực tiếp trong thư mục bộ truyện).
   - [ ] **Bước 2:** Dynamic Glossary Filtering (Lọc 20-50 terms xuất hiện trong chương) & Regex Slotting.
   - [ ] **Bước 3:** Dịch & Biên tập Mượt hóa (Áp dụng 4 chuẩn mực cốt lõi).
   - [ ] **Bước 4:** 🔴 **ĐỘ ƯU TIÊN CAO NHẤT - QC Thẩm định Văn phong & Làm sạch Hán tự** (Sạch 100% chữ Hán, văn phong trôi chảy tự nhiên, không ràng buộc số câu/số đoạn).
   - [ ] **Bước 5:** Ghi file kết quả (`chapters/[Chương]/content_vi.txt` đối với nguồn Local Dataset HOẶC `data/translated/chap_XXXX.txt` đối với nguồn Web Crawl) dưới dạng **văn bản thuần túy (Plain Text, KHÔNG CHỨA BẤT KỲ THẺ HTML NÀO NHƯ `<p>`, `</p>`)**. 🔴 **Dòng đầu tiên BẮT BUỘC theo định dạng `Chương [X]: [Tiêu đề chương]`** (nếu raw gốc thiếu tiêu đề thì tự suy luận tiêu đề ngắn gọn 3-8 từ phù hợp theo nội dung phục vụ nạp CSDL tự động), theo sau là 1 dòng trống rồi đến nội dung chương. Cập nhật Summary & **Reset Context Session (Chống tràn token)**.

2. **Tuân thủ quy trình dịch đa bước:** Không bao giờ dịch truyện trực tiếp bằng 1 prompt duy nhất. Hãy luôn đi qua các bước: Trích xuất thực thể/xưng hô -> Dịch thô -> Hiệu đính mượt văn phong Việt hóa -> Thẩm định QC.

3. **Tuân thủ 4 Chuẩn mực Dịch thuật Cốt lõi & Triết lý "Văn phong Hỗn hợp có kiểm soát":**
   - **4 NGUYÊN LÝ GIẢI MÃ NGỮ NGHĨA SÂU & BỘ LỌC ĐỜI THỰC (COMMONSENSE SENSE-CHECK - TỐI QUAN TRỌNG):**
     * **Nguyên lý 1 (Khử nhiễu Convert):** Văn bản đầu vào là bản Convert Hán-Việt thô từ phần mềm cũ (chữ-đổi-chữ). Tuyệt đối KHÔNG ĐƯỢC tin vào mặt chữ tiếng Việt thô và không dịch lắp ghép từ bề mặt. Hãy luôn truy tìm ý đồ thực sự và bản chất câu chuyện.
     * **Nguyên lý 2 (Bộ lọc tính hợp lý đời thực):** Luôn tự vấn trước khi hạ bút: Đặt vào bối cảnh xã hội, tâm lý nhân vật và đời thực, câu văn này có hợp lý và có nghĩa không? 👉 **Quy tắc vàng:** Nếu câu dịch nghe phi lý, kỳ quặc, vô nghĩa hoặc ngô nghê trong tiếng Việt (ví dụ: *"sinh viên tốt nghiệp đi ăn bánh trái"*, *"bị đóng cửa ăn canh"*, *"hệ thống hỏi có bao nhiêu tích phân"*...) $\rightarrow$ **100% ĐÓ LÀ BẪY TỪ ĐA NGHĨA / BẪY THÀNH NGỮ CONVERT, BẮT BUỘC PHẢI DỊCH THOÁT Ý THEO NGHĨA BÓNG VÀ HOÀN CẢNH THỰC TẾ!**
     * **Nguyên lý 3 (Giải mã ẩn dụ tiếng Trung):** Bắt buộc dịch ra bản chất hành động thực tế (*Ăn giấm $\rightarrow$ Ghen tuông; Hương bánh trái $\rightarrow$ Nhân tài đắt giá / Đối tượng săn đón; Ăn đậu phụ $\rightarrow$ Sàm sỡ / Trêu ghẹo; Đào góc tường $\rightarrow$ Giật bồ / Cướp người; Ôm đùi $\rightarrow$ Dựa dẫm đại gia*).
     * **Nguyên lý 4 (Dịch theo ý nghĩa, tự do cấu trúc câu):** Hoàn toàn thả tự do cấu trúc câu, tự do ngắt nghỉ, đảo ngữ pháp, viết lại câu văn để đạt độ mượt mà, trôi chảy và giàu chất văn học hiện đại.
   - **VĂN PHONG TỰ NHIÊN, TRÔI CHẢY & HỖN HỢP CÓ KIỂM SOÁT:**
     * Kết hợp từ Hán Việt và cách diễn đạt thuần Việt hiện đại một cách có chủ đích: Không quá cứng (toàn Hán Việt), không quá mất chất (hiện đại hóa hết).
     * **Khu vực giữ Hán Việt (Ưu tiên cao):** Thuật ngữ hệ thống (cảnh giới, kỹ năng, pháp bảo, môn phái, tu vi, thần thức, đại đạo, kiếp nạn...), xưng hô tôn ti (bản vương, đạo hữu, sư tôn, công tử...), từ ngữ tạo khí thế cổ kính (*sát khí, thiên cơ, kỳ ngộ, phong tư*), thành ngữ/điển cố.
     * **Khu vực thuần Việt hóa:** Lời thoại đời thường, hội thoại cảm xúc, miêu tả hành động hàng ngày.
     * **Kiểm soát mật độ:** Không nhồi nhét Hán Việt quá dày trong một đoạn văn, xen kẽ tự nhiên theo nhịp điệu truyện.
     * CẤM CẤM TUYỆT ĐỐI dịch word-by-word hay dịch ngược cấu trúc tiếng Trung. HOÀN TOÀN THẢ TỰ DO số câu, số đoạn văn để Translator biến tấu tạo nhịp đọc mượt mà nhất.
   - **XƯNG HÔ NĂNG ĐỘNG:** Linh hoạt dựa theo Mối quan hệ nhân vật (Anh - em, Ta - ngươi, Chàng - thiếp, Lão phu - ngươi...). Cấm dịch đại từ rập khuôn (`他` luôn thành `hắn`, `她` luôn thành `nàng`).
   - **THUẬT NGỮ CỐ ĐỊNH:** Luôn tham chiếu và áp dụng bảng thuật ngữ trong `<dataset_dir>/glossary.json` để giữ tính đồng nhất.
   - **ĐIỀU CHỈNH THEO THỂ LOẠI (GENRE-ADAPTIVE):**
     * *Tiên hiệp / Huyền huyễn / Kiếm hiệp / Cổ đại:* Tăng tỷ lệ Hán Việt trang trọng, giữ không khí cổ kính và thuật ngữ tu luyện.
     * *Ngôn tình cổ đại / Cung đấu / Gia đấu:* Giữ Hán Việt ở xưng hô, nghi thức cung đình; mềm mại hóa cảm xúc và hội thoại.
     * *Đô thị / Ngôn tình hiện đại / Thanh xuân:* Giảm Hán Việt xuống mức tối thiểu, ưu tiên văn phong gần gũi, thuần Việt tự nhiên.
     * *Xuyên không / Trọng sinh / Hệ thống:* Linh hoạt chuyển đổi theo từng phân cảnh (bối cảnh cổ trang thì tăng Hán Việt, bối cảnh hiện đại thì giảm).

4. **Tránh ngôn từ Convert thô cứng & Khử từ Hán Việt lỗi thời:**
   - **Khử triệt để các từ nối Hán-Việt rập khuôn/lỗi thời & từ điển bẫy đa nghĩa mở rộng:**
     * `nguyên lai` $\rightarrow$ `hóa ra / thì ra`
     * `bất quá` $\rightarrow$ `nhưng mà / dù sao / có điều`
     * `phi thường` / `thập phần` $\rightarrow$ `vô cùng / hết sức / cực kỳ`
     * `thanh âm` $\rightarrow$ `giọng nói / tiếng động / âm thanh`
     * `nhãn thần` $\rightarrow$ `ánh mắt / ánh nhìn`
     * `sắc mặt nan khán` $\rightarrow$ `sắc mặt khó coi / mặt mày xám xịt / nét mặt sa sầm`
     * `hít một hơi lãnh khí` $\rightarrow$ `hít sâu một hơi khí lạnh / bất giác rùng mình`
     * `khủng bố như tư` $\rightarrow$ `đáng sợ đến như vậy / kinh khủng đến mức này`
     * `khóe miệng trừu súc` $\rightarrow$ `khóe miệng giật giật / méo mặt`
     * `thân hình nhất trệ` $\rightarrow$ `bước chân khựng lại / người khẽ dừng lại`
     * `bối tích phát lương` $\rightarrow$ `sống lưng lạnh toát / lạnh buốt sống lưng`
     * `tích phân` / `积分` trong bối cảnh Hệ thống/Game $\rightarrow$ `điểm tích lũy / điểm hệ thống / điểm thưởng` (🔴 CẤM dịch thành toán học 'tích phân')
     * `khấu phân` $\rightarrow$ `trừ điểm`, `gia phân` $\rightarrow$ `cộng điểm`
     * `hảo cảm độ` $\rightarrow$ `độ thiện cảm`, `hắc hóa trị` $\rightarrow$ `chỉ số hắc hóa`
     * `sinh mệnh trị` $\rightarrow$ `thanh máu / chỉ số sinh mệnh`, `kinh nghiệm trị` $\rightarrow$ `điểm kinh nghiệm`
     * `mãi đơn` $\rightarrow$ `tính tiền / thanh toán`, `đả xa` $\rightarrow$ `bắt taxi / đặt xe`, `ngật thố` $\rightarrow$ `ghen tuông`
     * `香饽饽` / `hương bánh trái` $\rightarrow$ `đối tượng được săn đón / nhân tài đắt giá / món hàng hot` (🔴 CẤM dịch thành 'ăn bánh trái' hay 'hương bánh trái')
     * `吃香` $\rightarrow$ `được ưa chuộng / rất có giá`, `吃豆腐` $\rightarrow$ `sàm sỡ / trêu ghẹo`, `开小灶` $\rightarrow$ `ưu ái chăm sóc riêng / dạy kèm riêng`
     * `吃闭门羹` $\rightarrow$ `bị từ chối thẳng thừng / bị đóng cửa không tiếp`, `喝西北风` $\rightarrow$ `húp gió tây bắc / nhịn đói`
     * `炒鱿鱼` $\rightarrow$ `bị sa thải / bị đuổi việc`, `戴绿帽子` $\rightarrow$ `bị cắm sừng`
     * 🔴 **TUYỆT ĐỐI KHÔNG DÙNG TIẾNG LÓNG MẠNG THÔ THIỂN CỦA GIỚI TRẺ TRUNG QUỐC (Internet Slang / Netizen Jargon):**
       - *Nguyên nhân:* Những cụm từ này là tiếng lóng mạng rập khuôn, thô thiển, làm câu văn lủng củng, kỳ quặc, thiếu tính văn học, người đọc ở các lứa tuổi khác nhau rất khó hiểu hoặc gây phản cảm. Bắt buộc phải dịch thoát ý sang tiếng Việt chuẩn văn học tự nhiên, dễ hiểu:
         - `kiếp trâu ngựa` / `ngưu mã` / `牛马` $\rightarrow$ `làm lụng vất vả / phận làm thuê cực nhọc / thân phận thấp cổ bé họng / cày cuốc ngày đêm` (CẤM giữ nguyên "kiếp trâu ngựa / làm trâu làm ngựa cho tư bản")
         - `bò long sàng` / `bò lên long sàng` / `爬龙床` $\rightarrow$ `trèo lên giường vua / quyến rũ hoàng thượng / trèo cành cao`
         - `xoát hảo cảm` / `xoát độ hảo cảm` / `刷好感` $\rightarrow$ `lấy lòng / tạo thiện cảm / ghi điểm trong mắt ai đó` (CẤM dùng từ "xoát")
         - `hố cha` / `keng điệt` / `坑爹` $\rightarrow$ `bẫy người / lừa đảo / hại người / chơi khăm / xui xẻo / tức chết đi được`
         - `bạch liên hoa` / `白莲花` $\rightarrow$ `đạo đức giả / giả tạo / ra vẻ ngây thơ thánh thiện / miệng nam mô bụng một bồ dao găm`
         - `cái chết xã hội` / `xã tử` / `社死` $\rightarrow$ `mất mặt trước bàn dân thiên hạ / ngượng chín người / xấu hổ muốn độn thổ / bẽ mặt nhục nhã`
         - `trà xanh` / `绿茶` $\rightarrow$ `kẻ trơ trẽn / giả vờ ngây thơ / tiểu tam mưu mô`
         - `ăn dưa` / `ngật qua` / `吃瓜` $\rightarrow$ `hóng chuyện / hóng hớt / xem kịch vui / đứng ngoài xem trò hay`
         - `nằm ngửa` / `thảng bình` / `躺平` $\rightarrow$ `buông xuôi / mặc kệ đời / an phận thủ thường`
         - `bại gia` / `bại gia tử` $\rightarrow$ `phá gia chi tử / kẻ hoang phí`
         - `bạo kích` $\rightarrow$ `đòn giáng nặng nề / cú sốc lớn / đả kích đau đớn`
         - `thổ tào` / `nhổ nước bọt` $\rightarrow$ `châm chọc / mỉa mai / bóc mẽ / càu nhàu`
         - `vả mặt` / `đả kiểm` $\rightarrow$ `bẽ mặt / tự vỗ vào mặt mình / gậy ông đập lưng ông`
         - `tiểu thịt tươi` $\rightarrow$ `chàng trai trẻ tuấn tú / mỹ nam trẻ tuổi`
   - **🔴 CẤM TUYỆT ĐỐI DỊCH WORD-BY-WORD:** CẤM dịch rập khuôn các cụm tác giả ghi chú / meme như `腦子寄存處` thành "Nơi gửi gắm trí não" hay "Trạm gửi não". Hãy mượt hóa thành văn phong chuẩn Việt: `[Lời tác giả: Truyện thuộc thể loại hài hước hóm hỉnh, đọc thuần giải trí xả stress...]`.
   - **🔴 LOẠI BỎ RÁC QUẢNG CÁO & DỰ THU TRUYỆN:** Tự động cắt bỏ 100% các đoạn tác giả tự quảng cáo truyện mới (Dự thu văn, Giới thiệu truyện khác, Lời tác giả xin phiếu/xin hoa/donate...) ở đầu hoặc cuối chương, chỉ dịch trọn vẹn phần nội dung cốt truyện chính.

5. **Giải phóng Bộ nhớ & Phân Bổ Session theo Quy Mô Truyện (Stateless Execution & Session Granularity):**
   - **Quy tắc Phân Bổ Subagent Session theo Quy Mô Truyện (BẮT BUỘC):**
     * **Truyện ngắn / Vừa (< 10 chương):** Thực thi **1 Chapter = 1 Subagent Session** (Mỗi chương kích hoạt 1 `translator_subagent` session mới độc lập hoàn toàn).
     * **Truyện dài (10 - 1000+ chương):** Thực thi **10 Chapters = 1 Subagent Session** (Mỗi cụm 10 chương kích hoạt 1 `translator_subagent` session mới).
   - **BẮT BUỘC Thực Thi Tuần Tự (Strict Sequential Constraint):** Mỗi khi nhận lệnh dịch/biên tập truyện, Agent BẮT BUỘC phải tuân thủ thứ tự tuần tự tuyệt đối:
     1. **Kích hoạt `translator_subagent` ĐẦU TIÊN** via `invoke_subagent` để dịch, biên tập mượt hóa và ghi file `content_vi.txt`.
     2. **CHỜ `translator_subagent` HOÀN THÀNH 100%** và nhận phản hồi thành công trước khi kích hoạt QC. CẤM TUYỆT ĐỐI kích hoạt đồng thời (in parallel) cả 2 subagents trong cùng 1 tool call.
     3. **Kích hoạt `qc_auditor_subagent` CUỐI CÙNG** via `invoke_subagent` để kiểm duyệt độc lập chất lượng văn phong, rà soát chữ Hán, thẻ HTML trên các file đã dịch.
   - **Định nghĩa Subagent đủ quyền ghi file (enable_write_tools: true):**
     * Khi gọi `define_subagent` cho `translator_subagent` và `qc_auditor_subagent`, Agent BẮT BUỘC phải đặt tham số `enable_write_tools: true` để Subagent được trang bị công cụ tạo và sửa file (`write_to_file`, `replace_file_content`, `run_command`).
   - **🔴 CẤM TUYỆT ĐỐI XUẤT TIN NHẮN TRUNG GIAN TRONG HEADLESS CLI MODE:**
     * Trong môi trường headless non-interactive CLI (`agy -p`), việc Agent phát ngôn tin nhắn trò chuyện (chat text) mà không gọi tool sẽ làm CLI hiểu là lượt đã kết thúc và tự động thoát tiến trình (`event: result`), gây ngắt đột ngột và giết chết subagent đang chạy ngầm.
     * Do đó, sau khi gọi `invoke_subagent`, Agent BẮT BUỘC phải im lặng kết thúc lượt gọi công cụ (stop calling tools) để hệ thống tự động đón nhận phản hồi từ subagent khi hoàn thành.
     * Agent phải thực thi tuần tự và liên tục qua toàn bộ các batch ([1..10], [11..20], ...) cho đến khi tạo đủ 100% file `content_vi.txt`. Chỉ được xuất bảng Báo Cáo Nghiệm Thu cuối cùng (kèm thẻ `<!-- GOAL_COMPLETE -->`) ở bước hoàn tất cuối cùng.
   - Hủy hoàn toàn Chat Session Context của subagent sau khi kết thúc batch/chương để tránh trôi ngữ cảnh, suy giảm chất lượng dịch thuật, và **chống tràn Context Window 100% ngay cả khi xử lý 1,000+ chương**.

6. **🔴 ĐỘ ƯU TIÊN CAO NHẤT - CẤM TUYỆT ĐỐI SÓT CHỮ TRUNG QUỐC / HÁN TỰ, THẺ HTML & THẨM ĐỊNH QC VĂN PHONG:**
   Khâu **QC Thẩm định** mang độ ưu tiên CAO NHẤT trong toàn bộ workflow dịch thuật. Trước khi ghi file dịch cuối cùng tại `data/translated/`, Agent BẮT BUỘC phải thực hiện bước kiểm duyệt QC khắt khe:
   - Rà soát kỹ lưỡng và loại bỏ 100% bất kỳ chữ Hán / chữ Trung Quốc nào còn sót lại (kể cả dạng chú thích `TừHán (Nghĩa dịch)`).
   - **Đánh giá văn phong:** Đảm bảo bản dịch trôi chảy, tự nhiên, dễ hiểu, đọc không bị gượng gạo hay dính lỗi dịch word-by-word.
   - **Loại bỏ 100% mọi thẻ HTML (như `<p>`, `</p>`, `<br>`)** trong file kết quả cuối cùng.
   - File dịch xuất ra phải là 100% tiếng Việt thuần túy (Plain Text), mượt mà chuẩn văn học, có dòng đầu tiên là `Chương X: [Tiêu đề]` (tự suy luận nếu raw thiếu).

7. **BẢO CÁO KẾT QUẢ THEO ĐÚNG CHUẨN ĐỊNH DẠNG BẢNG THẨM ĐỊNH:**
   Khi báo cáo kết quả dịch thuật/biên tập chuỗi chương, Agent BẮT BUỘC trình bày bảng tổng hợp theo đúng cấu trúc: `Chương | Điểm QC | Trạng thái | Đơn vị thực thi Subagent` (ví dụ: `Chương 01 | 10.0 / 10 | PASSED ✅ | translator_subagent (dfdda025...)`).

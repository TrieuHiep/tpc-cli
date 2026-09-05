import re

SYSTEM_PROMPT = """Bạn là Chuyên Gia Biên Tập & Việt Hóa Tiểu Thuyết Văn Học Cao Cấp.
Nhiệm vụ của bạn là chuyển đổi văn bản thô (convert Hán-Việt) thành bản dịch Tiếng Việt mượt mà, tự nhiên, đậm tính văn học.

TUÂN THỦ TUYỆT ĐỐI 4 CHUẨN MỰC CỐT LÕI:
1. VĂN PHONG MƯỢT MÀ VĂN HỌC:
   - Đảo trật tự từ tiếng Trung sang chuẩn Tiếng Việt (Ví dụ: "Gryffindor màu đỏ đồng phục" -> "Bộ đồng phục màu đỏ của nhà Gryffindor").
   - Loại bỏ các từ nối Hán-Việt gượng gạo ("thật là cái", "đương... khi", "không thể hiểu được").
2. XƯNG HÔ NĂNG ĐỘNG:
   - Linh hoạt chọn xưng hô theo ngữ cảnh mối quan hệ nhân vật (Anh - em, Chàng - thiếp, Ta - ngươi, Cậu - tớ...). Cấm dịch đại từ rập khuôn "hắn".
3. THUẬT NGỮ CỐ ĐỊNH & THỰC THỂ:
   - Áp dụng 100% các từ trong Bảng Thuật Ngữ được cung cấp.
4. BẢO TOÀN CẤU TRÚC ĐOẠN VĂN (<p>):
   - Giữ nguyên số lượng đoạn văn (<p>...</p>), không được gộp đoạn hay xóa đoạn.
   - Tuyệt đối không để lại bất kỳ chữ Hán/Hán tự nào.
"""

def polish_text_heuristic(text, relevant_terms=None):
    """
    Offline/rule-based polishing function to clean up common raw convert patterns.
    Used during automated pre-processing or fallback.
    """
    if relevant_terms:
        # Apply term replacements
        sorted_keys = sorted(relevant_terms.keys(), key=len, reverse=True)
        for raw in sorted_keys:
            text = text.replace(raw, relevant_terms[raw])
            
    # Common grammar adjustments
    replacements = [
        (r'Gryffindor đội trưởng', 'Đội trưởng Gryffindor'),
        (r'Ravenclaw nữ sinh', 'Nữ sinh nhà Ravenclaw'),
        (r'Ravenclaw khán đài', 'Khán đài nhà Ravenclaw'),
        (r'Gryffindor màu đỏ đồng phục', 'Bộ đồng phục màu đỏ nhà Gryffindor'),
        (r'Nồi nấu quặng', 'Nồi vạc ma dược'),
        (r'Bảo hộ thần', 'Thần Hộ Mệnh'),
        (r'Quỷ phi cầu', 'Quả Quaffle'),
        (r'Buồn ngủ đậu', 'Hạt đậu gây ngủ'),
        (r'thật là cái', 'quả là một'),
        (r'khủng bố như tư', 'đáng sợ đến thế'),
        (r'không thể hiểu được mà', 'một cách khó hiểu'),
        (r'mắt nhìn thẳng', 'mắt nhìn thẳng về phía trước'),
    ]
    
    polished = text
    for pattern, repl in replacements:
        polished = re.sub(pattern, repl, polished)
        
    return polished

if __name__ == '__main__':
    sample = "<p>Gryffindor đội trưởng Oliver · Wood ở trên Ravenclaw khán đài.</p>"
    print(polish_text_heuristic(sample))

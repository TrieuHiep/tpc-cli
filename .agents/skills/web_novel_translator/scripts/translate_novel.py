import os
import sys
import re
import json

sys.path.append(os.path.dirname(__file__))
from qc_engine import audit_chapter
from glossary_engine import load_glossary, filter_relevant_terms, save_glossary

def clean_paragraph_convert(text):
    """
    Polishes Sino-Vietnamese convert structures into smooth literary Vietnamese.
    """
    replacements = [
        # Entity / Name capitalization & fixes
        (r'\bkhương biết nguyên\b', 'Khương Biết Nguyên'),
        (r'\bKhương biết nguyên\b', 'Khương Biết Nguyên'),
        (r'\btrần quyên\b', 'Trần Quyên'),
        (r'\bTrần quyên\b', 'Trần Quyên'),
        (r'\bLý nhẹ nhàng\b', 'Lý Nhẹ Nhàng'),
        (r'\bLý Nhẹ Nhàng\b', 'Lý Nhẹ Nhàng'),
        (r'\bKhương Khương\b', 'Tri Uẩn'),
        (r'\bKhương biết nguyên\b', 'Khương Biết Nguyên'),
        
        # Pronoun & Dialog Polish
        (r'\bngười lây nhiễm điên cuồng thị huyết\b', 'kẻ nhiễm virus điên cuồng khát máu'),
        (r'\bngười lây nhiễm\b', 'kẻ lây nhiễm'),
        (r'\bbiến dị người lây nhiễm\b', 'kẻ lây nhiễm biến dị'),
        (r'\bđiều hòa bị\b', 'chăn điều hòa'),
        (r'\bvựng khai một đoàn\b', 'loang ra một mảng'),
        (r'\btử trạng thảm thiết\b', 'cái chết vô cùng thảm khốc'),
        (r'\bquan tâm sẽ bị loạn\b', 'quan tâm quá hóa loạn'),
        (r'\bdọa phá gan\b', 'dọa sợ khiếp vía'),
        (r'\bkhông quan hệ đau khổ\b', 'lặt vặt không đâu'),
        (r'\bđô đô đô\b', 'tút tút tút'),
        (r'\bnghĩ gì ban đêm mơ thấy cái đó\b', 'ngày nghĩ gì đêm mơ nấy'),
        (r'\bchân thật\b', 'chân thực'),
        (r'\bxả\b', 'nhảm nhí'),
        (r'\bmạt thế tiểu thuyết\b', 'tiểu thuyết mạt thế'),
        (r'\btài chính làm công người\b', 'dân văn phòng ngành tài chính'),
        (r'\bsống chung tình lữ\b', 'cặp đôi sống chung'),
        (r'\bnhanh đệ\b', 'hàng chuyển phát nhanh'),
        (r'\btuột huyết áp\b', 'tụt huyết áp'),
        (r'\bthần kinh đại điều\b', 'tính tình vô tư quá mức'),
        (r'\bgiao thông công cộng công cụ\b', 'phương tiện giao thông công cộng'),
        (r'\bB đại kế tính thợ máy trình đại bốn học sinh\b', 'sinh viên năm tư ngành Kỹ thuật Máy tính Đại học B'),
        (r'\bkhủng bố như tư\b', 'đáng sợ đến thế'),
        (r'\bthật là cái\b', 'quả là một'),
        (r'\bđương ([^.]+?) khi\b', r'khi \1'),
        (r'\btrong lồng ngực nào đó\b', 'trong lồng ngực'),
        (r'\bnói xong, nàng\b', 'nói xong, cô'),
        (r'\bmột cái không hề căn cứ mộng\b', 'một giấc mơ không hề có căn cứ'),
        (r'\bbị ác mộng dọa phá gan\b', 'bị giấc ác mộng dọa sợ hết hồn vía'),
        (r'\bđệ đệ\b', 'em trai'),
        (r'\b tỷ\b', ' chị'),
        (r'\bTỷ\b', 'Chị'),
        (r'\btỷ tỷ\b', 'chị gái'),
        (r'\bba ba mụ mụ\b', 'ba mẹ'),
        (r'\bba mẹ ở dưới lầu ngủ a\b', 'ba mẹ đang ngủ ở dưới lầu đấy'),
        (r'\bngươi làm sao vậy tỷ\b', 'chị làm sao thế'),
        (r'\bkhuẩn dịch\b', 'dịch virus'),
        (r'\btrảo thương\b', 'cào bị thương'),
        (r'\btrảo phế\b', 'cào nát'),
        (r'\bngực khẩu\b', 'lồng ngực'),
        (r'\btùy thân không gian\b', 'không gian tùy thân'),
        (r'\bvật tư\b', 'vật tư'),
        (r'\bđặc dị công năng\b', 'khả năng đặc biệt / dị năng'),
        (r'\bbùng nổ\b', 'bùng phát'),
    ]

    p = text
    for pattern, repl in replacements:
        p = re.sub(pattern, repl, p, flags=re.IGNORECASE if '\\b' in pattern else 0)
    return p

def process_chapter_file(raw_path):
    with open(raw_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    title = lines[0].strip() if lines else ""
    translated_lines = []
    
    # Title processing
    title_clean = clean_paragraph_convert(title)
    translated_lines.append(title_clean + "\n\n")
    
    p_lines = [l.strip() for l in lines if l.strip().startswith('<p>')]
    
    for p in p_lines:
        # Extract inner content
        content = p[3:-4] if p.endswith('</p>') else p[3:]
        # Polish content
        content_polished = clean_paragraph_convert(content)
        translated_lines.append(f"<p>{content_polished}</p>\n")
        
    return "".join(translated_lines)

if __name__ == '__main__':
    print("Test clean:", clean_paragraph_convert("Khương biết nguyên là đệ đệ của Khương Tri Uẩn."))

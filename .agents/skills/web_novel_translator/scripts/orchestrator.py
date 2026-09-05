import os
import sys
import time
import re

sys.path.append(os.path.dirname(__file__))

from web_crawler import fetch_and_save_chapters
from local_loader import is_local_novel_dir, load_local_novel, save_translated_chapter
from glossary_engine import bootstrap_glossary, filter_relevant_terms, apply_regex_slotting
from translator_engine import polish_text_heuristic
from qc_engine import audit_chapter, PASS_THRESHOLD

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

MAX_RETRIES = 2

def run_pipeline(source_input, max_chapters=3, raw_dir='data/raw_chapters', output_dir='data/translated', summary_path='data/summary.txt'):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)
    
    print("=========================================================")
    print("=== PIPELINE MULTI-AGENT BIÊN TẬP TRUYỆN DỊCH AUTOMATED ===")
    print("=========================================================")
    
    chap_folders = []
    is_local = is_local_novel_dir(source_input)
    
    if is_local:
        print(f"\n[BƯỚC 1] Nạp dữ liệu từ thư mục truyện Local: {source_input}")
        meta, raw_files, chap_folders = load_local_novel(source_input, max_chapters=max_chapters)
    else:
        print(f"\n[BƯỚC 1] Crawl dữ liệu thô từ URL Web & Khởi tạo Metadata: {source_input}")
        meta, raw_files = fetch_and_save_chapters(source_input, output_dir=raw_dir, max_chapters=max_chapters)
        
    glossary = bootstrap_glossary(meta)
    
    if not os.path.exists(summary_path):
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"# TÓM TẮT TRUYỆN: {meta['title']}\n")
            f.write(f"Tác giả: {meta['author']}\n")
            f.write(f"Thể loại: {', '.join(meta['genres'])}\n\n")
            f.write(f"## Mô Tả Cốt Truyện Ban Đầu:\n{meta['description']}\n\n")
            f.write("## Nhật Ký Tóm Tắt Từng Chương:\n")

    translated_files = []
    
    # 2. Process Chapters (Stateless Loop with Self-Correction Retry)
    for idx, raw_path in enumerate(raw_files, 1):
        print(f"\n---------------------------------------------------------")
        print(f"[BƯỚC 2-5] Đang xử lý Chương {idx}/{len(raw_files)}: {os.path.basename(raw_path)}")
        
        with open(raw_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        rel_terms = filter_relevant_terms(raw_text, glossary)
        print(f"  • Lọc được {len(rel_terms)} thuật ngữ liên quan trong chương.")
        
        # Initial Translation/Polishing
        slotted_text = apply_regex_slotting(raw_text, rel_terms)
        translated_text = polish_text_heuristic(slotted_text, rel_terms)
        
        # QC Audit & Retry Loop
        attempt = 0
        passed = False
        score = 0
        report = {}
        
        while attempt <= MAX_RETRIES:
            passed, score, report = audit_chapter(raw_text, translated_text)
            score_10 = report['score_out_of_10']
            
            if passed or score >= PASS_THRESHOLD:
                print(f"  • QC Auditor: {score_10}/10 điểm | Trạng thái: PASSED ✅ (Xuất file)")
                break
            else:
                attempt += 1
                print(f"  • QC Auditor: {score_10}/10 điểm (< 8.5) | Trạng thái: FAILED ❌ (Lần thử {attempt}/{MAX_RETRIES})")
                print(f"    ↳ Phản hồi lỗi cho Translator Agent sửa lại:")
                for err in report['errors']:
                    print(f"      - {err}")
                    
                if attempt <= MAX_RETRIES:
                    translated_text = polish_text_heuristic(translated_text, rel_terms)
                else:
                    print(f"    ⚠️ Đã hết lượt thử lại. Chấp nhận xuất file với điểm {score_10}/10.")
                    
        # Strip HTML tags for clean plain text output
        clean_text = re.sub(r'</p>\s*', '\n\n', translated_text)
        clean_text = re.sub(r'<p>', '', clean_text)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip() + "\n"
        
        # Save translated chapter
        if is_local and idx <= len(chap_folders):
            chap_folder_path = chap_folders[idx - 1][2]
            out_path = save_translated_chapter(chap_folder_path, clean_text)
            print(f"  ✓ Đã ghi file dịch local: {out_path}")
        else:
            out_path = os.path.join(output_dir, f"chap_{idx:04d}.txt")
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(clean_text)
            print(f"  ✓ Đã xuất file hoàn chỉnh (Plain Text): {out_path}")
            
        translated_files.append(out_path)
        
        lines = [line.strip() for line in translated_text.splitlines() if line.strip() and not line.startswith('<')]
        ch_title = lines[0] if lines else f"Chương {idx}"
        with open(summary_path, 'a', encoding='utf-8') as f:
            f.write(f"\n- **[Chương {idx}] {ch_title}**: QC Đạt {report.get('score_out_of_10', 0)}/10.")
            
        # STATELESS RESET
        del raw_text, slotted_text, translated_text, rel_terms

    print("\n=========================================================")
    print("=== BÁO CÁO KẾT QUẢ HOÀN THÀNH ===")
    print("=========================================================")
    print(f"✅ Tên truyện    : {meta['title']}")
    print(f"✅ Số chương    : {len(translated_files)} chương")
    print(f"✅ Nguồn dữ liệu : {'LOCAL DATASET' if is_local else 'WEB CRAWLER'}")
    print(f"✅ Thư mục xuất : file:///{os.path.abspath(output_dir).replace('\\', '/')}")
    print(f"✅ Bảng Glossary: file:///{os.path.abspath('data/glossary.json').replace('\\', '/')}")
    print(f"✅ File Summary : file:///{os.path.abspath(summary_path).replace('\\', '/')}")

    return meta, translated_files

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else 'https://truyendichwiki.net/truyen/hp-luc-hap-dan-phap-tac-ampB81S4CAGaRclo'
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    run_pipeline(src, max_chapters=count)

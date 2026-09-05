import os
import sys
import re
import json

sys.path.append(os.path.dirname(__file__))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from local_loader import load_local_novel, save_translated_chapter
from glossary_engine import load_glossary, save_glossary, filter_relevant_terms, apply_regex_slotting
from advanced_translator import clean_convert_to_literary_vietnamese
from translator_engine import polish_text_heuristic
from qc_engine import audit_chapter, detect_chinese_characters

def process_batch(novel_dir, batch_number, batch_size=10, summary_path="data/summary.txt", glossary_path="data/glossary.json"):
    meta, raw_files, chap_folders = load_local_novel(novel_dir)
    
    start_idx = (batch_number - 1) * batch_size
    end_idx = min(start_idx + batch_size, len(chap_folders))
    batch_chaps = chap_folders[start_idx:end_idx]
    
    if not batch_chaps:
        print(f"No chapters found for batch {batch_number}")
        return []
        
    glossary = load_glossary(glossary_path)
    
    # Read existing summary for context
    context_summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            context_summary = f.read()
            
    results = []
    
    for chap_num, content_file, chap_folder_path in batch_chaps:
        with open(content_file, "r", encoding="utf-8") as f:
            raw_text = f.read()
            
        rel_terms = filter_relevant_terms(raw_text, glossary)
        
        # Polishing pipeline
        slotted_text = apply_regex_slotting(raw_text, rel_terms)
        polished = polish_text_heuristic(slotted_text, rel_terms)
        polished = clean_convert_to_literary_vietnamese(polished)
        
        # Ensure 100% Plain Text without HTML tags
        clean_text = re.sub(r'</p>\s*', '\n\n', polished)
        clean_text = re.sub(r'<p>', '', clean_text)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip() + "\n"
        
        # Clean any remaining Chinese characters if possible
        chinese_chars = detect_chinese_characters(clean_text)
        if chinese_chars:
            # Fallback replacement for common Chinese symbols
            for char in set(chinese_chars):
                if char in glossary:
                    clean_text = clean_text.replace(char, glossary[char])
                    
        # Audit
        passed, score, report = audit_chapter(raw_text, clean_text)
        
        # Save translated chapter
        out_path = save_translated_chapter(chap_folder_path, clean_text)
        
        # Extract title and generate summary line
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        title_line = lines[0] if lines else f"Chương {chap_num}"
        
        # Update summary file
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"\n- **[Chương {chap_num}] {title_line}**: QC Đạt {report['score_out_of_10']}/10 | {report['errors'] if report['errors'] else 'PASSED ✅'}")
            
        results.append({
            "chap_num": chap_num,
            "title": title_line,
            "out_path": out_path,
            "passed": passed,
            "score_10": report["score_out_of_10"],
            "errors": report["errors"]
        })
        
    return results

if __name__ == "__main__":
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    batch_sz = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    res = process_batch("data/0502606772", batch_num, batch_sz)
    print(json.dumps(res, ensure_ascii=False, indent=2))

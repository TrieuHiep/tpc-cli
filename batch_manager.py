import os
import json
import zipfile
import datetime
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r'f:\Workplace\outside\test-tmp\storage\truyendichwiki'
STORY_ID = 'YOCaDFS4CF7psHlG'

def get_paths(story_id=STORY_ID):
    story_dir = os.path.join(BASE_DIR, story_id)
    return {
        'story_dir': story_dir,
        'info_file': os.path.join(story_dir, 'info.json'),
        'glossary_file': os.path.join(story_dir, 'glossary.json'),
        'summary_file': os.path.join(story_dir, 'summary.txt'),
        'checkpoints_file': os.path.join(story_dir, 'checkpoints.json'),
        'raw_zip': os.path.join(story_dir, 'chapters.zip'),
        'trans_zip': os.path.join(story_dir, 'translated_chapters.zip')
    }

def get_context(story_id=STORY_ID):
    paths = get_paths(story_id)
    info = {}
    if os.path.exists(paths['info_file']):
        with open(paths['info_file'], 'r', encoding='utf-8') as f:
            info = json.load(f)
    glossary = {}
    if os.path.exists(paths['glossary_file']):
        with open(paths['glossary_file'], 'r', encoding='utf-8') as f:
            glossary = json.load(f)
    summary = ""
    if os.path.exists(paths['summary_file']):
        with open(paths['summary_file'], 'r', encoding='utf-8') as f:
            summary = f.read()
    checkpoints = {}
    if os.path.exists(paths['checkpoints_file']):
        with open(paths['checkpoints_file'], 'r', encoding='utf-8') as f:
            checkpoints = json.load(f)
    return info, glossary, summary, checkpoints

def get_raw_chapter(chap_num, story_id=STORY_ID):
    paths = get_paths(story_id)
    with zipfile.ZipFile(paths['raw_zip'], 'r') as zf:
        candidates = [
            f'chapters/{chap_num}/content.txt',
            f'{chap_num}/content.txt',
            f'chapters/{chap_num}.txt',
            f'{chap_num}.txt'
        ]
        namelist = zf.namelist()
        for cand in candidates:
            if cand in namelist:
                return zf.read(cand).decode('utf-8', errors='ignore')
        for n in namelist:
            if f'/{chap_num}/content.txt' in n or n.startswith(f'{chap_num}/'):
                return zf.read(n).decode('utf-8', errors='ignore')
    raise FileNotFoundError(f"Chapter {chap_num} not found in {paths['raw_zip']}")

def prepare_batch_files(chap_start, chap_end, story_id=STORY_ID):
    scratch_dir = os.path.join(r'f:\Workplace\outside\test-tmp\scratch', story_id, f'batch_{chap_start}_{chap_end}')
    os.makedirs(scratch_dir, exist_ok=True)
    info, glossary, summary, _ = get_context(story_id)
    
    with open(os.path.join(scratch_dir, 'info.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    with open(os.path.join(scratch_dir, 'glossary.json'), 'w', encoding='utf-8') as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)
    
    summary_lines = [l.strip() for l in summary.split('\n') if l.strip()]
    recent_summary = "\n".join(summary_lines[-10:])
    with open(os.path.join(scratch_dir, 'recent_summary.txt'), 'w', encoding='utf-8') as f:
        f.write(recent_summary)
        
    for ch in range(chap_start, chap_end + 1):
        try:
            raw = get_raw_chapter(ch, story_id)
            with open(os.path.join(scratch_dir, f'chap_{ch}_raw.txt'), 'w', encoding='utf-8') as f:
                f.write(raw)
        except Exception as e:
            print(f"Warning: could not prepare chap {ch}: {e}")
            
    print(f"Successfully prepared batch {chap_start}-{chap_end} in {scratch_dir}")
    return scratch_dir

def commit_chapter(chap_num, title, translated_text, new_terms=None, chap_summary=None, story_id=STORY_ID):
    paths = get_paths(story_id)
    entries = {}
    if os.path.exists(paths['trans_zip']):
        with zipfile.ZipFile(paths['trans_zip'], 'r') as zf:
            for item in zf.infolist():
                entries[item.filename] = zf.read(item.filename)
                
    # Target translated entry
    target_entry = f'chapters/{chap_num}/content_vi.txt'
    entries[target_entry] = translated_text.strip().encode('utf-8')
    
    # Target raw entry (ensure content.txt is present)
    raw_entry = f'chapters/{chap_num}/content.txt'
    if raw_entry not in entries and os.path.exists(paths['raw_zip']):
        try:
            raw_text = get_raw_chapter(chap_num, story_id)
            entries[raw_entry] = raw_text.encode('utf-8')
        except Exception as e:
            print(f"Warning: could not copy raw chapter {chap_num}: {e}")
    
    temp_zip = paths['trans_zip'] + '.tmp'
    with zipfile.ZipFile(temp_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
        for filename, data in entries.items():
            zf_out.writestr(filename, data)
    os.replace(temp_zip, paths['trans_zip'])
    
    checkpoints = {}
    if os.path.exists(paths['checkpoints_file']):
        with open(paths['checkpoints_file'], 'r', encoding='utf-8') as f:
            checkpoints = json.load(f)
    checkpoints[str(chap_num)] = {
        'chapter_num': int(chap_num),
        'step': 'COMMITTED',
        'chapter_title': title if title else f'Chương {chap_num}',
        'updated_at': datetime.datetime.now().isoformat()
    }
    with open(paths['checkpoints_file'], 'w', encoding='utf-8') as f:
        json.dump(checkpoints, f, ensure_ascii=False, indent=2)
        
    if new_terms:
        glossary = {}
        if os.path.exists(paths['glossary_file']):
            with open(paths['glossary_file'], 'r', encoding='utf-8') as f:
                glossary = json.load(f)
        glossary.update(new_terms)
        with open(paths['glossary_file'], 'w', encoding='utf-8') as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
            
    if chap_summary:
        with open(paths['summary_file'], 'a', encoding='utf-8') as f:
            f.write(f"\nChương {chap_num}: {chap_summary.strip()}\n")
            
    print(f"Committed Chapter {chap_num}: {title}")

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 2 and sys.argv[1] == 'prepare':
        prepare_batch_files(int(sys.argv[2]), int(sys.argv[3]))

import os
import time
import json

def safe_append_summary(summary_path, content, max_retries=10, retry_delay=0.2):
    """
    Ghi an toàn vào file summary.txt chống tranh chấp (race conditions) khi nhiều subagent chạy đồng thời.
    Sử dụng cơ chế file lock sidecar (.lock).
    """
    lock_path = summary_path + ".lock"
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    
    acquired = False
    for _ in range(max_retries):
        try:
            # Atomic lock creation
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            time.sleep(retry_delay)
            
    try:
        with open(summary_path, 'a', encoding='utf-8') as f:
            f.write(content)
    finally:
        if acquired and os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass

def safe_update_glossary(glossary_path, new_terms, max_retries=10, retry_delay=0.2):
    """
    Cập nhật an toàn vào file glossary.json chống ghi đè/tranh chấp giữa nhiều subagent.
    """
    lock_path = glossary_path + ".lock"
    os.makedirs(os.path.dirname(glossary_path), exist_ok=True)
    
    acquired = False
    for _ in range(max_retries):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            time.sleep(retry_delay)
            
    try:
        current_data = {}
        if os.path.exists(glossary_path):
            try:
                with open(glossary_path, 'r', encoding='utf-8') as f:
                    current_data = json.load(f)
            except Exception:
                current_data = {}
                
        updated = False
        for raw, vi in new_terms.items():
            if raw and vi and raw not in current_data:
                current_data[raw] = vi
                updated = True
                
        if updated or not os.path.exists(glossary_path):
            with open(glossary_path, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=2)
    finally:
        if acquired and os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass

import os
import json
import re

DEFAULT_GLOSSARY_FILENAME = 'glossary.json'

def resolve_glossary_path(path=None, dataset_dir=None):
    """
    Resolves the exact path to glossary.json.
    Prioritizes dataset_dir/glossary.json over root data/glossary.json.
    """
    if dataset_dir:
        return os.path.join(dataset_dir, DEFAULT_GLOSSARY_FILENAME)
    if path:
        return path
    return os.path.join('data', DEFAULT_GLOSSARY_FILENAME)

def load_glossary(path=None, dataset_dir=None):
    target_path = resolve_glossary_path(path, dataset_dir)
    if os.path.exists(target_path):
        with open(target_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_glossary(glossary_data, path=None, dataset_dir=None):
    target_path = resolve_glossary_path(path, dataset_dir)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(glossary_data, f, ensure_ascii=False, indent=2)

def bootstrap_glossary(metadata, path=None, dataset_dir=None):
    """
    Initializes glossary from story metadata if not existing or merges core entities inside dataset_dir.
    """
    target_path = resolve_glossary_path(path, dataset_dir)
    glossary = load_glossary(path=target_path)
    
    # Common default replacements for Harry Potter & Convert terms
    default_terms = {
        "Oliver · Wood": "Oliver Wood",
        "Oliver · ngũ đức": "Oliver Wood",
        "Lai kéo · trần": "Leila Trần",
        "Leila · trần": "Leila Trần",
        "Bảo hộ thần": "Thần Hộ Mệnh",
        "Quỷ phi cầu": "Quả Quaffle",
        "Đánh cầu tay": "Tấn thủ (Beater)",
        "Nồi nấu quặng": "Nồi vạc ma dược",
        "Buồn ngủ đậu": "Hạt đậu gây ngủ",
        "Gryffindor đội trưởng": "Đội trưởng Gryffindor",
        "Ravenclaw nữ sinh": "Nữ sinh nhà Ravenclaw",
        "Ravenclaw khán đài": "Khán đài nhà Ravenclaw",
        "Gryffindor màu đỏ đồng phục": "Bộ đồng phục màu đỏ của nhà Gryffindor"
    }
    
    for raw, vi in default_terms.items():
        if raw not in glossary:
            glossary[raw] = vi
            
    save_glossary(glossary, path=target_path)
    return glossary

def filter_relevant_terms(text, glossary):
    """
    Filters and returns only terms from glossary that actually appear in text.
    Keeps context prompt extremely small!
    """
    relevant = {}
    for raw, vi in glossary.items():
        if raw in text:
            relevant[raw] = vi
    return relevant

def apply_regex_slotting(text, relevant_terms):
    """
    Replaces raw Sino-Vietnamese names in text with target translations using regex.
    Sorts keys by length descending to prevent partial string replacement issues!
    """
    sorted_keys = sorted(relevant_terms.keys(), key=len, reverse=True)
    slotted_text = text
    for raw in sorted_keys:
        target = relevant_terms[raw]
        slotted_text = slotted_text.replace(raw, target)
    return slotted_text

def update_glossary_with_new_terms(new_terms, path=None, dataset_dir=None):
    """
    Merges newly discovered terms into dataset's glossary file.
    """
    target_path = resolve_glossary_path(path, dataset_dir)
    glossary = load_glossary(path=target_path)
    updated = False
    for raw, vi in new_terms.items():
        if raw and vi and raw not in glossary:
            glossary[raw] = vi
            updated = True
    if updated:
        save_glossary(glossary, path=target_path)
    return glossary

if __name__ == '__main__':
    g = bootstrap_glossary({'title': 'Test'})
    print(f"Glossary initialized with {len(g)} terms.")


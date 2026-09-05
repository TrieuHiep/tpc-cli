import os
import json
import re

def is_local_novel_dir(path):
    """Kiểm tra đường dẫn có phải thư mục truyện local tiêu chuẩn hay không."""
    if not os.path.isdir(path):
        return False
    info_path = os.path.join(path, "info.json")
    return os.path.exists(info_path)

def load_local_novel(novel_dir, max_chapters=None):
    """
    Đọc dữ liệu từ thư mục truyện local.
    Trả về: (meta, raw_files, chap_folders)
    - meta: dict chứa metadata từ info.json
    - raw_files: danh sách đường dẫn tuyệt đối tới file content.txt của các chương
    - chap_folders: danh sách tuple (chap_num, content_file_path, folder_path)
    """
    info_path = os.path.join(novel_dir, "info.json")
    with open(info_path, "r", encoding="utf-8") as f:
        info_data = json.load(f)
        
    meta = {
        "title": info_data.get("title", "Truyện Không Tên"),
        "author": info_data.get("author", "Vô Danh"),
        "genres": info_data.get("genres", []),
        "description": info_data.get("description", ""),
        "setting_context": info_data.get("setting_context", ""),
        "protagonists": info_data.get("protagonists", {}),
        "default_pronouns": info_data.get("default_pronouns", {})
    }
    
    # Tìm các thư mục chương trong chapters/ hoặc trực tiếp ở novel_dir
    chapters_dir = os.path.join(novel_dir, "chapters")
    search_dir = chapters_dir if os.path.exists(chapters_dir) else novel_dir
    
    chap_folders = []
    for item in os.listdir(search_dir):
        item_path = os.path.join(search_dir, item)
        if os.path.isdir(item_path):
            # Kiểm tra xem folder có chứa content.txt không
            content_file = os.path.join(item_path, "content.txt")
            if os.path.exists(content_file):
                # Lấy số thứ tự chương từ tên folder (vd: "1", "chap_01", "chapter_1")
                num_match = re.search(r'\d+', item)
                chap_num = int(num_match.group()) if num_match else 999999
                chap_folders.append((chap_num, content_file, item_path))
                
    # Sắp xếp chương theo thứ tự tăng dần
    chap_folders.sort(key=lambda x: x[0])
    
    if max_chapters:
        chap_folders = chap_folders[:max_chapters]
        
    raw_files = [item[1] for item in chap_folders]
    return meta, raw_files, chap_folders

def save_translated_chapter(chap_folder_path, clean_text):
    """Ghi file dịch tiếng Việt vào folder chương tương ứng (content_vi.txt)."""
    out_path = os.path.join(chap_folder_path, "content_vi.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(clean_text)
    return out_path

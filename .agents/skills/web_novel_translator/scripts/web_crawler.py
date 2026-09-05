import urllib.request
import re
import time
import sys
import os
import json

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = 'https://truyendichwiki.net'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7'
}

def fetch_html(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode('utf-8')

def extract_story_metadata(story_url):
    """
    Crawls main story page to extract title, author, status, tags, summary and first chapter URL.
    """
    html = fetch_html(story_url)
    
    title_m = re.search(r'<h2[^>]*>([^<]+)<\/h2>', html)
    author_m = re.search(r'Tác giả:\s*<a[^>]*>([^<]+)<\/a>', html)
    status_m = re.search(r'Tình trạng:\s*<a[^>]*>([^<]+)<\/a>', html)
    latest_m = re.search(r'Mới nhất:\s*<a[^>]*>([^<]+)<\/a>', html)
    desc_m = re.search(r'<div class="book-desc-detail">([\s\S]*?)<\/div>', html)
    
    genres_span_m = re.search(r'Thể loại:\s*<span[^>]*>([\s\S]*?)<\/span>', html)
    genres = []
    if genres_span_m:
        genres = re.findall(r'<a[^>]*>([^<]+)<\/a>', genres_span_m.group(1))
        
    read_href_m = re.search(r'href="(/truyen/[^"]+/(?:chuong-1|1)-[^"]+)"', html)
    if not read_href_m:
        read_href_m = re.search(r'href="(/truyen/[^"]+/chuong-[^"]+)"', html)
    first_chapter_url = BASE_URL + read_href_m.group(1) if read_href_m else None
    
    desc_clean = re.sub(r'<[^>]+>', '\n', desc_m.group(1)).strip() if desc_m else ''
    desc_clean = re.sub(r'\n+', '\n', desc_clean)
    
    return {
        'story_url': story_url,
        'title': title_m.group(1).strip() if title_m else 'Chưa rõ',
        'author': author_m.group(1).strip() if author_m else 'Chưa rõ',
        'status': status_m.group(1).strip() if status_m else 'Hoàn thành',
        'latest_chapter': latest_m.group(1).strip() if latest_m else '',
        'genres': genres,
        'description': desc_clean,
        'first_chapter_url': first_chapter_url
    }

def fetch_and_save_chapters(story_url, output_dir='data/raw_chapters', max_chapters=5):
    """
    Crawls chapters sequentially starting from first_chapter_url and saves to raw_chapters/chap_XXXX.txt.
    """
    os.makedirs(output_dir, exist_ok=True)
    meta = extract_story_metadata(story_url)
    
    current_url = meta['first_chapter_url']
    if not current_url:
        raise ValueError("Không tìm thấy liên kết Chương 1 từ trang chủ truyện!")
        
    count = 1
    crawled_files = []
    
    print(f"📖 Bắt đầu cào dữ liệu truyện: {meta['title']} ({meta['author']})")
    print(f"📁 Thư mục lưu file thô: {output_dir}")
    
    while current_url and len(crawled_files) < max_chapters:
        html = fetch_html(current_url)
        
        ch_title_m = re.search(r'<a class="truncate chapter-name"[^>]*>([^<]+)<\/a>', html)
        ch_title = ch_title_m.group(1).strip() if ch_title_m else f"Chương {count}"
        
        body_m = re.search(r'<div id="bookContentBody"[^>]*>([\s\S]*?)<\/div>\s*<\/div>', html)
        paragraphs = []
        if body_m:
            paragraphs = re.findall(r'<p>([\s\S]*?)<\/p>', body_m.group(1))
            paragraphs = [re.sub(r'<[^>]+>', '', p).strip() for p in paragraphs if p.strip()]
            
        file_path = os.path.join(output_dir, f"chap_{count:04d}.txt")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"{ch_title}\n\n")
            for p in paragraphs:
                f.write(f"<p>{p}</p>\n")
                
        crawled_files.append(file_path)
        print(f"  ✓ Saved [{count:04d}] {ch_title} ({len(paragraphs)} đoạn) -> {file_path}")
        
        next_m = re.search(r'id="btnNextChapter"[^>]*href="([^"]+)"', html)
        if not next_m:
            next_m = re.search(r'href="([^"]+)"[^>]*>\s*Chương sau', html)
            
        if next_m and next_m.group(1):
            current_url = BASE_URL + next_m.group(1)
            count += 1
        else:
            current_url = None
            
        time.sleep(0.3)
        
    return meta, crawled_files

if __name__ == '__main__':
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    else:
        test_url = 'https://truyendichwiki.net/truyen/hp-luc-hap-dan-phap-tac-ampB81S4CAGaRclo'
    meta, files = fetch_and_save_chapters(test_url, max_chapters=3)
    print(f"\n🎉 Hoàn thành cào {len(files)} chương mẫu!")

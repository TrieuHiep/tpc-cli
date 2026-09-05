import os
import sys
import json
import re
from ebooklib import epub

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Đường dẫn mặc định
DATA_DIR = os.path.join('data', '0502606772')
INFO_PATH = os.path.join(DATA_DIR, 'info.json')
CHAPTERS_DIR = os.path.join(DATA_DIR, 'chapters')
OUTPUT_EPUB_PATH = os.path.join(DATA_DIR, 'Nghe_Noi_Sau_Khi_Toi_Chet.epub')

def build_epub(data_dir: str = DATA_DIR, output_epub: str = OUTPUT_EPUB_PATH):
    info_path = os.path.join(data_dir, 'info.json')
    chapters_dir = os.path.join(data_dir, 'chapters')

    # 1. Đọc metadata từ info.json
    book_title = "Bộ Sách Truyện"
    author_name = "Tác Giả"
    description = ""

    if os.path.exists(info_path):
        with open(info_path, 'r', encoding='utf-8') as f:
            info = json.load(f)
            book_title = info.get('title', book_title)
            author_name = info.get('author', author_name)
            description = info.get('description', '')

    print(f"==================================================")
    print(f"📖 TẠO FILE EPUB CHO CUỐN SÁCH:")
    print(f"   Tiêu đề: {book_title}")
    print(f"   Tác giả: {author_name}")
    print(f"==================================================\n")

    # 2. Khởi tạo EpubBook
    book = epub.EpubBook()
    book.set_identifier("epub_0502606772")
    book.set_title(book_title)
    book.set_language('vi')
    book.add_author(author_name)

    if description:
        book.add_metadata('DC', 'description', description)

    # Styling CSS chuẩn cho E-reader (Apple Books, Kindle, Kobo)
    style = '''
    @namespace page url(http://www.w3.org/1999/xhtml);
    body {
        font-family: "Georgia", "Times New Roman", serif;
        line-height: 1.6;
        padding: 5%;
        margin: 0;
    }
    h1 {
        text-align: center;
        font-size: 1.5em;
        margin-top: 1.5em;
        margin-bottom: 1.5em;
        color: #2c3e50;
        font-weight: bold;
    }
    p {
        text-indent: 1.5em;
        margin-top: 0;
        margin-bottom: 0.8em;
        text-align: justify;
    }
    '''
    default_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style
    )
    book.add_item(default_css)

    # 3. Duyệt danh sách các chương
    chapter_folders = []
    for entry in os.listdir(chapters_dir):
        full_p = os.path.join(chapters_dir, entry)
        if os.path.isdir(full_p) and entry.isdigit():
            chapter_folders.append((int(entry), full_p))

    chapter_folders.sort(key=lambda x: x[0])
    print(f"-> Tìm thấy {len(chapter_folders)} chương.")

    toc_chapters = []
    spine = ['nav']

    for chap_num, chap_dir in chapter_folders:
        content_vi_path = os.path.join(chap_dir, 'content_vi.txt')
        if not os.path.exists(content_vi_path):
            continue

        with open(content_vi_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            continue

        title = lines[0]
        title_with_pause = f"{title} [pause 1000ms]"
        body_paragraphs = lines[1:]

        # Tạo HTML cho chương (thẻ h1 chứa tiêu đề có [pause 1000ms])
        html_content = [f'<html><head><link rel="stylesheet" href="style/nav.css" type="text/css"/></head><body>']
        html_content.append(f'<h1>{title_with_pause}</h1>')
        for p in body_paragraphs:
            # Escape ký tự HTML
            safe_p = p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_content.append(f'<p>{safe_p}</p>')
        html_content.append('</body></html>')


        chapter_item = epub.EpubHtml(
            title=title,
            file_name=f'chap_{chap_num}.xhtml',
            lang='vi'
        )
        chapter_item.content = "".join(html_content)
        chapter_item.add_item(default_css)

        book.add_item(chapter_item)
        toc_chapters.append(chapter_item)
        spine.append(chapter_item)

    # 4. Thiết lập TOC (Table of Contents) và Navigation
    book.toc = tuple(toc_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    # 5. Ghi file EPUB
    epub.write_epub(output_epub, book, {})
    size_mb = os.path.getsize(output_epub) / (1024 * 1024)
    print(f"\n🎉 Đã xuất thành công file EPUB tại: {output_epub} ({size_mb:.2f} MB)")

if __name__ == '__main__':
    build_epub()

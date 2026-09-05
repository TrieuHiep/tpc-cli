import os
import json
from ebooklib import epub
from typing import Optional

class EpubBuilder:
    """Tự động đóng gói tất cả các chương content_vi.txt thành file EPUB."""

    @staticmethod
    def create_epub(data_dir: str, output_epub_path: str, title: Optional[str] = None, author: Optional[str] = None):
        info_path = os.path.join(data_dir, 'info.json')
        chapters_dir = os.path.join(data_dir, 'chapters')

        book_title = title or "Bộ Sách Truyện"
        author_name = author or "Tác Giả"
        description = ""

        if os.path.exists(info_path):
            with open(info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
                book_title = title or info.get('title', book_title)
                author_name = author or info.get('author', author_name)
                description = info.get('description', '')

        book = epub.EpubBook()
        book.set_identifier("epub_autogen")
        book.set_title(book_title)
        book.set_language('vi')
        book.add_author(author_name)

        if description:
            book.add_metadata('DC', 'description', description)

        style = '''
        body { font-family: "Georgia", serif; line-height: 1.6; padding: 5%; }
        h1 { text-align: center; color: #2c3e50; margin-top: 1.5em; margin-bottom: 1.5em; }
        p { text-indent: 1.5em; margin-bottom: 0.8em; text-align: justify; }
        '''
        default_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=style
        )
        book.add_item(default_css)

        chapter_folders = []
        for entry in os.listdir(chapters_dir):
            full_p = os.path.join(chapters_dir, entry)
            if os.path.isdir(full_p) and entry.isdigit():
                chapter_folders.append((int(entry), full_p))

        chapter_folders.sort(key=lambda x: x[0])
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

            chap_title = lines[0]
            title_with_pause = f"{chap_title} [pause 1000ms]"
            body_paragraphs = lines[1:]

            html_content = [f'<html><head><link rel="stylesheet" href="style/nav.css" type="text/css"/></head><body>']
            html_content.append(f'<h1>{title_with_pause}</h1>')

            for p in body_paragraphs:
                safe_p = p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html_content.append(f'<p>{safe_p}</p>')
            html_content.append('</body></html>')

            chapter_item = epub.EpubHtml(
                title=chap_title,
                file_name=f'chap_{chap_num}.xhtml',
                lang='vi'
            )
            chapter_item.content = "".join(html_content)
            chapter_item.add_item(default_css)

            book.add_item(chapter_item)
            toc_chapters.append(chapter_item)
            spine.append(chapter_item)

        book.toc = tuple(toc_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        epub.write_epub(output_epub_path, book, {})
        print(f"✅ Đã tạo thành công file EPUB: {output_epub_path}")
        return output_epub_path

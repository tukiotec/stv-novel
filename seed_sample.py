import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stv_novel_app.db import STVDatabase
from stv_novel_app.api import fetch_book_metadata, fetch_chapter_list

def seed():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stv_novel.db")
    db = STVDatabase(db_path)

    host = "qidian"
    book_id = "1050754857"

    meta = fetch_book_metadata(host, book_id)
    chapters = fetch_chapter_list(host, book_id)

    print(f"Adding book: {meta['title']} ({len(chapters)} chapters)")
    book_fk = db.add_or_update_book(
        host=host,
        book_id=book_id,
        title=meta['title'],
        author=meta.get('author', ''),
        intro=meta.get('intro', ''),
        cover_url=meta.get('cover_url', ''),
        total_chapters=len(chapters)
    )
    db.sync_chapter_list(book_fk, chapters)

    # If chapter_1_clean.txt exists in g:\AI, inject it as downloaded!
    c1_file = "g:/AI/chapter_1_clean.txt"
    if os.path.exists(c1_file):
        with open(c1_file, "r", encoding="utf-8") as f:
            c1_text = f.read()
        db.save_chapter_content(book_fk, "926800288", c1_text, "Chương 1: Thần Vương phân thân là ta chỗ dựa")
        print("Pre-loaded Chapter 1 into offline storage!")

    # Set as active read
    db.update_last_read(book_fk, "926800288", "Chương 1: Thần Vương phân thân là ta chỗ dựa")
    print("Database successfully seeded.")

if __name__ == "__main__":
    seed()

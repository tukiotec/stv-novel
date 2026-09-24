import sys
import os
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"g:\AI")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from stv_novel_app.db import STVDatabase
from stv_novel_app.downloader import ChapterDownloaderWorker

def test_downloader():
    app = QApplication(sys.argv)
    db_path = r"g:\AI\stv_novel_app\stv_novel.db"
    db = STVDatabase(db_path)

    book = db.get_book_by_id(1)
    # Let's download chapter 2 and 3
    chapters_to_dl = [
        ("926846708", "Chương 02: Hoắc Vũ Hạo: Trắng ách đại ca thế thân thôi"),
        ("926896396", "Chương 03: Mười hai tuổi Hồn Tông mang tới xung kích!")
    ]

    print(f"Starting downloader for {len(chapters_to_dl)} chapters...")
    worker = ChapterDownloaderWorker(
        host=book['host'],
        book_id=book['book_id'],
        book_fk=1,
        chapters_to_download=chapters_to_dl,
        db=db
    )

    def on_saved(c_id, title, count):
        print(f"  [SAVED] {c_id}: {title} ({count} chars)")

    def on_finished(succ, fail):
        print(f"FINISHED: {succ} success, {fail} failed")
        # Check DB
        c2 = db.get_chapter_by_id(1, "926846708")
        c3 = db.get_chapter_by_id(1, "926896396")
        print("C2 in DB:", bool(c2 and c2['is_downloaded']), "length:", len(c2['content']) if c2 else 0)
        print("C3 in DB:", bool(c3 and c3['is_downloaded']), "length:", len(c3['content']) if c3 else 0)
        app.quit()

    worker.sig_chapter_saved.connect(on_saved)
    worker.sig_finished.connect(on_finished)
    worker.start()

    app.exec()

if __name__ == "__main__":
    test_downloader()

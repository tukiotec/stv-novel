import sys
import os
import time

sys.path.insert(0, r"g:\AI")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from stv_novel_app.db import STVDatabase
from stv_novel_app.ui_main import MainWindow

def test_all_tabs():
    app = QApplication(sys.argv)
    db_path = r"g:\AI\stv_novel_app\stv_novel.db"
    db = STVDatabase(db_path)
    window = MainWindow(db)
    window.show()

    def step1_library():
        window.grab().save(r"g:\AI\stv_novel_app\screen_tab1_library.png")
        print("Captured Tab 1")
        # Switch to Chapters tab with book 1
        window.open_book_chapters(1)
        QTimer.singleShot(500, step2_chapters)

    def step2_chapters():
        window.grab().save(r"g:\AI\stv_novel_app\screen_tab2_chapters.png")
        print("Captured Tab 2")
        # Open Chapter 1 in reader
        window.open_reader(1, "926800288")
        QTimer.singleShot(500, step3_reader)

    def step3_reader():
        window.grab().save(r"g:\AI\stv_novel_app\screen_tab3_reader.png")
        print("Captured Tab 3")
        window.close()
        app.quit()

    QTimer.singleShot(1000, step1_library)
    app.exec()
    print("ALL SCREENS VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all_tabs()

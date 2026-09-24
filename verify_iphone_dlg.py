import sys
import os

sys.path.insert(0, r"g:\AI")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from stv_novel_app.db import STVDatabase
from stv_novel_app.ui_main import MainWindow

def test_iphone_dialog():
    app = QApplication(sys.argv)
    db = STVDatabase(r"g:\AI\stv_novel_app\stv_novel.db")
    window = MainWindow(db)
    window.show()

    def open_dialog():
        # Trigger button
        QTimer.singleShot(300, capture_dialog)
        window._show_iphone_dialog()

    def capture_dialog():
        for top in QApplication.topLevelWidgets():
            if top.inherits("QDialog"):
                top.grab().save(r"g:\AI\stv_novel_app\screen_iphone_dialog.png")
                print("Captured iPhone dialog screenshot!")
                top.accept()
                window.close()
                app.quit()
                break

    QTimer.singleShot(500, open_dialog)
    app.exec()
    print("Test finished successfully!")

if __name__ == "__main__":
    test_iphone_dialog()

import sys
import os
import ctypes

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set explicit Windows AppUserModelID before QApplication initialization
try:
    myappid = "ares.stv.novel.studio.v1"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from stv_novel_app.db import STVDatabase
from stv_novel_app.ui_main import MainWindow
from stv_novel_app.create_shortcut import create_desktop_shortcut

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("STV Novel Studio")
    app.setOrganizationName("AresEnterprise")

    # Assets & Icons
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(base_dir, "assets", "stv_icon.ico")
    png_path = os.path.join(base_dir, "assets", "stv_icon.png")

    if os.path.exists(ico_path):
        app_icon = QIcon(ico_path)
    elif os.path.exists(png_path):
        app_icon = QIcon(png_path)
    else:
        app_icon = None

    if app_icon:
        app.setWindowIcon(app_icon)

    # Initialize Database
    db_path = os.path.join(base_dir, "stv_novel.db")
    db = STVDatabase(db_path)

    # Auto create shortcut if not exists
    desktop_lnk = os.path.join(os.path.expanduser("~"), "Desktop", "STV Novel Studio.lnk")
    if not os.path.exists(desktop_lnk):
        try:
            create_desktop_shortcut()
        except Exception:
            pass

    # Launch Main Window
    window = MainWindow(db, app_icon_path=ico_path if os.path.exists(ico_path) else "")
    if app_icon:
        window.setWindowIcon(app_icon)

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

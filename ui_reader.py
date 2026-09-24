import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextBrowser, QSlider, QComboBox, QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

from .db import STVDatabase

class STVReaderWidget(QWidget):
    sig_back_to_list = pyqtSignal()
    sig_chapter_changed = pyqtSignal(str, str) # chapter_id, chapter_title

    def __init__(self, db: STVDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_book = None
        self.current_chapter = None
        self.font_size = 18
        self.font_family = "Segoe UI"
        self.line_height_percent = 180
        self.bg_mode = "white" # white, sepia, soft

        self._init_ui()
        self._init_shortcuts()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top Control Toolbar
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #e2e8f0;
                padding: 6px 12px;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 6, 12, 6)
        top_layout.setSpacing(10)

        self.btn_back = QPushButton("⬅ Quay lại danh sách")
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        self.btn_back.clicked.connect(self.sig_back_to_list.emit)
        top_layout.addWidget(self.btn_back)

        self.lbl_book_title = QLabel("Chưa chọn truyện")
        self.lbl_book_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 14px;")
        top_layout.addWidget(self.lbl_book_title, 1)

        # Reading status badge
        self.lbl_offline_badge = QLabel("Chưa lưu")
        self.lbl_offline_badge.setStyleSheet("""
            QLabel {
                background-color: #f1f5f9;
                color: #64748b;
                font-size: 12px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 4px;
            }
        """)
        top_layout.addWidget(self.lbl_offline_badge)

        # Font Family selector
        self.combo_font = QComboBox()
        self.combo_font.addItems(["Segoe UI", "Georgia", "Arial", "Times New Roman", "Consolas"])
        self.combo_font.currentTextChanged.connect(self._on_font_family_changed)
        self.combo_font.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
        top_layout.addWidget(self.combo_font)

        # Font Size Controls
        self.btn_font_dec = QPushButton("A-")
        self.btn_font_dec.setFixedWidth(32)
        self.btn_font_dec.setStyleSheet("font-weight: bold; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px;")
        self.btn_font_dec.clicked.connect(self._decrease_font)
        top_layout.addWidget(self.btn_font_dec)

        self.lbl_font_size = QLabel(f"{self.font_size}px")
        self.lbl_font_size.setStyleSheet("color: #475569; font-weight: 600;")
        top_layout.addWidget(self.lbl_font_size)

        self.btn_font_inc = QPushButton("A+")
        self.btn_font_inc.setFixedWidth(32)
        self.btn_font_inc.setStyleSheet("font-weight: bold; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px;")
        self.btn_font_inc.clicked.connect(self._increase_font)
        top_layout.addWidget(self.btn_font_inc)

        # Background mode toggle (White / Sepia / Soft)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Sáng Trắng", "Giấy Vàng (Sepia)", "Xám Êm Mắt"])
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        self.combo_theme.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
        top_layout.addWidget(self.combo_theme)

        # Export TXT Button
        self.btn_export = QPushButton("📥 Xuất file TXT")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_export.clicked.connect(self._export_current_chapter)
        top_layout.addWidget(self.btn_export)

        main_layout.addWidget(top_bar)

        # Chapter Content TextBrowser
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                color: #0f172a;
                border: none;
                padding: 30px 60px;
                selection-background-color: #bfdbfe;
            }
        """)
        main_layout.addWidget(self.text_browser, 1)

        # Bottom Navigation Bar
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-top: 1px solid #e2e8f0;
                padding: 8px 16px;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 8, 16, 8)
        bottom_layout.setSpacing(12)

        self.btn_prev = QPushButton("⏮ Chương trước (Phím ←)")
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #0f172a;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
            QPushButton:disabled {
                color: #94a3b8;
                border-color: #e2e8f0;
            }
        """)
        self.btn_prev.clicked.connect(self._goto_prev_chapter)
        bottom_layout.addWidget(self.btn_prev)

        self.lbl_chapter_counter = QLabel("Chương 0 / 0")
        self.lbl_chapter_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chapter_counter.setStyleSheet("color: #475569; font-weight: 600; font-size: 13px;")
        bottom_layout.addWidget(self.lbl_chapter_counter, 1)

        self.btn_next = QPushButton("Chương sau ⏭ (Phím →)")
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #cbd5e1;
                color: #64748b;
            }
        """)
        self.btn_next.clicked.connect(self._goto_next_chapter)
        bottom_layout.addWidget(self.btn_next)

        main_layout.addWidget(bottom_bar)

    def _init_shortcuts(self):
        # Keyboard shortcuts for reading comfort
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._goto_prev_chapter)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._goto_next_chapter)
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self, self._goto_prev_chapter)
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, self._goto_next_chapter)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self._toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, lambda: self.window().showNormal() if self.window() and self.window().isFullScreen() else None)

    def _toggle_fullscreen(self):
        win = self.window()
        if win:
            if win.isFullScreen():
                win.showNormal()
            else:
                win.showFullScreen()

    def load_chapter(self, book_fk: int, chapter_id: str):
        book = self.db.get_book_by_id(book_fk)
        if not book:
            return
        self.current_book = book
        self.lbl_book_title.setText(f"📖 {book['title']}")

        chapter = self.db.get_chapter_by_id(book_fk, chapter_id)
        if not chapter:
            return
        self.current_chapter = chapter

        # Update last read bookmark
        self.db.update_last_read(book_fk, chapter['chapter_id'], chapter['chapter_title'])

        # Update offline badge
        if chapter['is_downloaded']:
            self.lbl_offline_badge.setText("✅ Đã lưu Offline")
            self.lbl_offline_badge.setStyleSheet("""
                background-color: #dcfce7;
                color: #15803d;
                font-size: 12px;
                font-weight: 700;
                padding: 3px 8px;
                border-radius: 4px;
            """)
        else:
            self.lbl_offline_badge.setText("⚠️ Chưa lưu nội dung")
            self.lbl_offline_badge.setStyleSheet("""
                background-color: #fef3c7;
                color: #b45309;
                font-size: 12px;
                font-weight: 700;
                padding: 3px 8px;
                border-radius: 4px;
            """)

        # Counter and Prev/Next button status
        c_idx = chapter['chapter_index']
        total = book['total_chapters'] or 1
        self.lbl_chapter_counter.setText(f"Chương {c_idx} / {total}")
        self.btn_prev.setEnabled(c_idx > 1)
        self.btn_next.setEnabled(c_idx < total)

        self._render_text()
        # Scroll to top
        self.text_browser.verticalScrollBar().setValue(0)
        self.sig_chapter_changed.emit(chapter['chapter_id'], chapter['chapter_title'])

    def _render_text(self):
        if not self.current_chapter:
            return

        title = self.current_chapter['chapter_title']
        content = self.current_chapter['content']
        if not content:
            content = "<i>(Nội dung chương này chưa được tải về máy. Hãy ra mục Danh Sách Chương và bấm 'Tải chương' để lưu đọc offline.)</i>"

        # Format paragraphs into clean HTML
        paragraphs = content.split('\n\n')
        html_paras = []
        for p in paragraphs:
            p_clean = p.strip()
            if p_clean:
                # Replace single line breaks with <br>
                p_html = p_clean.replace('\n', '<br>')
                html_paras.append(f"<p style='margin-bottom: 1.4em; text-indent: 1.8em;'>{p_html}</p>")

        # Theme color mapping
        bg_color = "#ffffff"
        text_color = "#0f172a"
        if self.bg_mode == "sepia":
            bg_color = "#fbf0d9"
            text_color = "#2d241e"
        elif self.bg_mode == "soft":
            bg_color = "#f8fafc"
            text_color = "#1e293b"

        self.text_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                padding: 30px 80px;
                selection-background-color: #bfdbfe;
            }}
        """)

        full_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: '{self.font_family}', 'Segoe UI', sans-serif;
                    font-size: {self.font_size}px;
                    line-height: {self.line_height_percent / 100:.2f};
                    color: {text_color};
                    background-color: {bg_color};
                    margin: 0;
                }}
                h1 {{
                    font-size: {int(self.font_size * 1.4)}px;
                    font-weight: 700;
                    margin-bottom: 24px;
                    color: {text_color};
                    text-align: center;
                    padding-bottom: 16px;
                    border-bottom: 2px solid #e2e8f0;
                }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            {''.join(html_paras)}
        </body>
        </html>
        """
        self.text_browser.setHtml(full_html)

    def _increase_font(self):
        if self.font_size < 36:
            self.font_size += 2
            self.lbl_font_size.setText(f"{self.font_size}px")
            self._render_text()

    def _decrease_font(self):
        if self.font_size > 12:
            self.font_size -= 2
            self.lbl_font_size.setText(f"{self.font_size}px")
            self._render_text()

    def _on_font_family_changed(self, family: str):
        self.font_family = family
        self._render_text()

    def _on_theme_changed(self, index: int):
        modes = ["white", "sepia", "soft"]
        self.bg_mode = modes[index]
        self._render_text()

    def _goto_prev_chapter(self):
        if not self.current_book or not self.current_chapter:
            return
        c_idx = self.current_chapter['chapter_index']
        if c_idx > 1:
            prev_chap = self.db.get_chapter_by_index(self.current_book['id'], c_idx - 1)
            if prev_chap:
                self.load_chapter(self.current_book['id'], prev_chap['chapter_id'])

    def _goto_next_chapter(self):
        if not self.current_book or not self.current_chapter:
            return
        c_idx = self.current_chapter['chapter_index']
        next_chap = self.db.get_chapter_by_index(self.current_book['id'], c_idx + 1)
        if next_chap:
            self.load_chapter(self.current_book['id'], next_chap['chapter_id'])

    def _export_current_chapter(self):
        if not self.current_chapter:
            return
        title = self.current_chapter['chapter_title']
        content = self.current_chapter['content']
        if not content:
            QMessageBox.warning(self, "Chưa có nội dung", "Chương này chưa được tải về, không thể xuất file!")
            return

        # Sanitize filename
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_']).strip()
        default_name = f"{safe_title}.txt"
        file_path, _ = QFileDialog.getSaveFileName(self, "Xuất chương ra file TXT", default_name, "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"{title}\n\n{content}")
                QMessageBox.information(self, "Thành công", f"Đã xuất chương thành công ra:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể ghi file: {e}")

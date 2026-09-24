import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QMessageBox, QFrame, QSplitter,
    QSpinBox, QFileDialog, QAbstractItemView, QMenu, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap

from .db import STVDatabase
from .api import parse_story_input, fetch_book_metadata, fetch_chapter_list, search_stv, DEFAULT_BASE
from .downloader import ChapterDownloaderWorker
from .ui_reader import STVReaderWidget

class FetchMetaThread(QThread):
    sig_result = pyqtSignal(dict, list)
    sig_error = pyqtSignal(str)

    def __init__(self, host: str, book_id: str, base_url: str):
        super().__init__()
        self.host = host
        self.book_id = book_id
        self.base_url = base_url

    def run(self):
        try:
            meta = fetch_book_metadata(self.host, self.book_id, self.base_url)
            chapters = fetch_chapter_list(self.host, self.book_id, self.base_url)
            self.sig_result.emit(meta, chapters)
        except Exception as e:
            self.sig_error.emit(str(e))

class SearchThread(QThread):
    sig_result = pyqtSignal(list)
    sig_error = pyqtSignal(str)

    def __init__(self, query: str, base_url: str):
        super().__init__()
        self.query = query
        self.base_url = base_url

    def run(self):
        try:
            results = search_stv(self.query, self.base_url)
            self.sig_result.emit(results)
        except Exception as e:
            self.sig_error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self, db: STVDatabase, app_icon_path: str = ""):
        super().__init__()
        self.db = db
        self.app_icon_path = app_icon_path
        self.base_url = DEFAULT_BASE
        self.current_book_fk = None
        self.download_worker = None
        self.search_thread = None
        self.fetch_thread = None
        self.search_results_data = []

        self.setWindowTitle("STV Novel Studio - Trình Đọc & Tải Tiểu Thuyết Sáng Tác Việt (PC Offline)")
        self.resize(1240, 840)
        self.setMinimumSize(980, 660)

        if app_icon_path and os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))

        self._apply_global_styles()
        self._init_ui()
        self._load_library()

    def _apply_global_styles(self):
        # 100% Enterprise Light Theme (White background, Charcoal text)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            QWidget {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                font-size: 13px;
                color: #0f172a;
            }
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                background: #ffffff;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                font-weight: 600;
                padding: 10px 22px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #2563eb;
                border-top: 3px solid #2563eb;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff;
                selection-color: #1e3a8a;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                font-weight: 700;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                color: #0f172a;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
            QPushButton {
                font-weight: 600;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QProgressBar {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                text-align: center;
                background-color: #f1f5f9;
                color: #0f172a;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 5px;
            }
        """)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title & Quick Search Bar
        header = QFrame()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        lbl_app = QLabel("📚 STV NOVEL STUDIO")
        lbl_app.setStyleSheet("font-size: 18px; font-weight: 800; color: #1e3a8a;")
        header_layout.addWidget(lbl_app)

        lbl_sub = QLabel("— Tìm kiếm, tải chương & đọc offline trực tiếp trên máy tính")
        lbl_sub.setStyleSheet("font-size: 13px; color: #64748b; font-weight: 500;")
        header_layout.addWidget(lbl_sub, 1)

        # Smart Universal Search / Add Box
        self.txt_url_input = QLineEdit()
        self.txt_url_input.setPlaceholderText("🔍 Tìm tên truyện (Đấu la, Phàm nhân...) hoặc dán link truyện...")
        self.txt_url_input.setFixedWidth(460)
        self.txt_url_input.returnPressed.connect(self._on_header_search_clicked)
        header_layout.addWidget(self.txt_url_input)

        self.btn_header_search = QPushButton("🔍 Tìm Kiếm / Thêm")
        self.btn_header_search.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_header_search.clicked.connect(self._on_header_search_clicked)
        header_layout.addWidget(self.btn_header_search)

        main_layout.addWidget(header)

        # Main Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        # Tab 0: Search
        self.tab_search = QWidget()
        self._init_search_tab()
        self.tabs.addTab(self.tab_search, "🔍 Tìm Kiếm Truyện")

        # Tab 1: Library
        self.tab_library = QWidget()
        self._init_library_tab()
        self.tabs.addTab(self.tab_library, "📚 Tủ Sách Của Tôi")

        # Tab 2: Chapter Manager
        self.tab_chapters = QWidget()
        self._init_chapters_tab()
        self.tabs.addTab(self.tab_chapters, "📑 Quản Lý & Tải Chương")

        # Tab 3: Offline Reader
        self.reader_widget = STVReaderWidget(self.db)
        self.reader_widget.sig_back_to_list.connect(lambda: self.tabs.setCurrentIndex(2))
        self.tabs.addTab(self.reader_widget, "📖 Trình Đọc Truyện")

        # Tab 4: Export & Settings
        self.tab_settings = QWidget()
        self._init_settings_tab()
        self.tabs.addTab(self.tab_settings, "💾 Xuất File & Cài Đặt")

    def _init_search_tab(self):
        layout = QVBoxLayout(self.tab_search)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search Controls Card
        search_box = QFrame()
        search_box.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        sb_layout = QVBoxLayout(search_box)
        sb_layout.setSpacing(10)

        row1 = QHBoxLayout()
        self.txt_search_kw = QLineEdit()
        self.txt_search_kw.setPlaceholderText("Nhập từ khóa tìm kiếm (tên truyện, tác giả, nhân vật trên Sáng Tác Việt)...")
        self.txt_search_kw.setStyleSheet("font-size: 14px; padding: 10px 14px;")
        self.txt_search_kw.returnPressed.connect(self._on_search_clicked)
        row1.addWidget(self.txt_search_kw, 1)

        self.btn_search = QPushButton("🔍 Tìm Kiếm")
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 700;
                font-size: 14px;
                padding: 10px 24px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_search.clicked.connect(self._on_search_clicked)
        row1.addWidget(self.btn_search)
        sb_layout.addLayout(row1)

        # Quick Search Suggestion Chips
        chips_row = QHBoxLayout()
        chips_row.addWidget(QLabel("Gợi ý tìm nhanh:"))
        quick_tags = ["Đấu La", "Phàm Nhân Tu Tiên", "Vạn Cổ", "Thôn Phệ Tinh Không", "Tiên Nghịch", "Đại Phụng"]
        for tag in quick_tags:
            btn_tag = QPushButton(tag)
            btn_tag.setStyleSheet("""
                QPushButton {
                    background: #ffffff;
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #eff6ff;
                    color: #2563eb;
                    border-color: #93c5fd;
                }
            """)
            btn_tag.clicked.connect(lambda _, t=tag: self._trigger_quick_search(t))
            chips_row.addWidget(btn_tag)
        chips_row.addStretch(1)
        sb_layout.addLayout(chips_row)

        layout.addWidget(search_box)

        # Status text
        self.lbl_search_status = QLabel("Nhập từ khóa và bấm Tìm Kiếm để tìm truyện từ hệ thống Sáng Tác Việt.")
        self.lbl_search_status.setStyleSheet("color: #64748b; font-weight: 500;")
        layout.addWidget(self.lbl_search_status)

        # Search Results Table
        self.table_search = QTableWidget()
        self.table_search.setColumnCount(6)
        self.table_search.setHorizontalHeaderLabels([
            "STT", "Tên Truyện", "Nguồn", "Tác Giả", "Mã Truyện", "Thao Tác"
        ])
        self.table_search.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_search.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_search.verticalHeader().setDefaultSectionSize(46)
        self.table_search.setColumnWidth(0, 50)
        self.table_search.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_search.setColumnWidth(2, 100)
        self.table_search.setColumnWidth(3, 160)
        self.table_search.setColumnWidth(4, 120)
        self.table_search.setColumnWidth(5, 280)
        self.table_search.doubleClicked.connect(self._on_search_row_double_clicked)
        layout.addWidget(self.table_search, 1)

    def _trigger_quick_search(self, keyword: str):
        self.txt_search_kw.setText(keyword)
        self._on_search_clicked()

    def _on_header_search_clicked(self):
        raw = self.txt_url_input.text().strip()
        if not raw:
            return

        parsed = parse_story_input(raw)
        if parsed:
            # It's an exact URL or host/id -> fetch directly
            host, book_id = parsed
            self._fetch_and_add_book(host, book_id)
            self.txt_url_input.clear()
        else:
            # It's a search term -> switch to search tab and search
            self.tabs.setCurrentIndex(0)
            self.txt_search_kw.setText(raw)
            self._on_search_clicked()
            self.txt_url_input.clear()

    def _on_search_clicked(self):
        kw = self.txt_search_kw.text().strip()
        if not kw:
            QMessageBox.warning(self, "Chưa nhập từ khóa", "Vui lòng nhập tên truyện hoặc tác giả cần tìm!")
            return

        self.btn_search.setEnabled(False)
        self.btn_search.setText("Đang tìm kiếm...")
        self.lbl_search_status.setText(f"Đang tìm kiếm truyện cho từ khóa: '{kw}'...")
        self.table_search.setRowCount(0)

        self.search_thread = SearchThread(kw, self.base_url)
        self.search_thread.sig_result.connect(self._on_search_success)
        self.search_thread.sig_error.connect(self._on_search_error)
        self.search_thread.start()

    def _on_search_success(self, results: list):
        self.btn_search.setEnabled(True)
        self.btn_search.setText("🔍 Tìm Kiếm")
        self.search_results_data = results
        self.table_search.setRowCount(len(results))

        if not results:
            self.lbl_search_status.setText("Không tìm thấy kết quả nào phù hợp. Vui lòng thử từ khóa khác!")
            return

        self.lbl_search_status.setText(f"Đã tìm thấy {len(results)} truyện phù hợp:")

        for row, item in enumerate(results):
            self.table_search.setItem(row, 0, QTableWidgetItem(str(row + 1)))

            title_item = QTableWidgetItem(item['title'])
            title_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table_search.setItem(row, 1, title_item)

            host_item = QTableWidgetItem(item['host'].upper() if item['host'] else "STV")
            host_item.setForeground(QColor("#2563eb"))
            self.table_search.setItem(row, 2, host_item)

            self.table_search.setItem(row, 3, QTableWidgetItem(item['author'] or "Chưa rõ"))
            self.table_search.setItem(row, 4, QTableWidgetItem(item['book_id'] or "-"))

            # Action Buttons
            btn_panel = QWidget()
            h = QHBoxLayout(btn_panel)
            h.setContentsMargins(4, 2, 4, 2)
            h.setSpacing(6)

            btn_add = QPushButton("➕ Thêm Vào Tủ & Tải")
            btn_add.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    font-weight: 700;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
            item_data = item
            btn_add.clicked.connect(lambda _, it=item_data: self._on_add_from_search(it, open_reader_immediately=False))
            h.addWidget(btn_add)

            btn_read_now = QPushButton("📖 Đọc")
            btn_read_now.setStyleSheet("""
                QPushButton {
                    background-color: #10b981;
                    color: #ffffff;
                    font-weight: 700;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #059669;
                }
            """)
            btn_read_now.clicked.connect(lambda _, it=item_data: self._on_add_from_search(it, open_reader_immediately=True))
            h.addWidget(btn_read_now)

            self.table_search.setCellWidget(row, 5, btn_panel)

    def _on_search_error(self, err: str):
        self.btn_search.setEnabled(True)
        self.btn_search.setText("🔍 Tìm Kiếm")
        self.lbl_search_status.setText(f"Lỗi tìm kiếm: {err}")
        QMessageBox.critical(self, "Lỗi kết nối", f"Không thể tra cứu từ máy chủ: {err}")

    def _on_search_row_double_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self.search_results_data):
            self._on_add_from_search(self.search_results_data[row], open_reader_immediately=False)

    def _on_add_from_search(self, item: dict, open_reader_immediately: bool = False):
        host = item.get('host')
        book_id = item.get('book_id')

        if not host or not book_id:
            parsed = parse_story_input(item.get('href', ''))
            if parsed:
                host, book_id = parsed

        if not host or not book_id:
            QMessageBox.warning(self, "Lỗi dữ liệu", "Không xác định được mã định danh của truyện!")
            return

        self._fetch_and_add_book(host, book_id, open_reader_immediately=open_reader_immediately)

    def _fetch_and_add_book(self, host: str, book_id: str, open_reader_immediately: bool = False):
        self.lbl_search_status.setText(f"Đang đồng bộ thông tin và danh sách chương của [{host.upper()}:{book_id}]...")
        self.btn_header_search.setEnabled(False)

        self.fetch_thread = FetchMetaThread(host, book_id, self.base_url)
        self.fetch_thread.sig_result.connect(lambda meta, chaps: self._on_book_fetched_custom(meta, chaps, open_reader_immediately))
        self.fetch_thread.sig_error.connect(self._on_book_fetch_error)
        self.fetch_thread.start()

    def _on_book_fetched_custom(self, meta: dict, chapters: list, open_reader_immediately: bool):
        self.btn_header_search.setEnabled(True)
        self.lbl_search_status.setText("Sẵn sàng.")

        if not chapters:
            QMessageBox.warning(self, "Thông báo", f"Không lấy được danh sách chương cho truyện '{meta.get('title')}'!")
            return

        book_fk = self.db.add_or_update_book(
            host=meta['host'],
            book_id=meta['book_id'],
            title=meta['title'],
            author=meta.get('author', ''),
            intro=meta.get('intro', ''),
            cover_url=meta.get('cover_url', ''),
            total_chapters=len(chapters)
        )
        self.db.sync_chapter_list(book_fk, chapters)
        self._load_library()

        if open_reader_immediately:
            # Open first chapter in reader
            first_chap_id = chapters[0][0]
            self.open_book_chapters(book_fk)
            self.open_reader(book_fk, first_chap_id)
        else:
            # Switch to chapter manager tab
            self.open_book_chapters(book_fk)

    def _on_add_book_clicked(self):
        self._on_header_search_clicked()

    def _on_book_fetch_error(self, err: str):
        self.btn_header_search.setEnabled(True)
        self.lbl_search_status.setText(f"Lỗi: {err}")
        QMessageBox.critical(self, "Lỗi kết nối", f"Không thể lấy thông tin truyện: {err}")

    def _init_library_tab(self):
        layout = QVBoxLayout(self.tab_library)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Toolbar
        top_row = QHBoxLayout()
        lbl_hint = QLabel("Danh sách các bộ truyện đã lưu trong cơ sở dữ liệu nội bộ máy tính:")
        lbl_hint.setStyleSheet("font-weight: 600; color: #334155;")
        top_row.addWidget(lbl_hint, 1)

        btn_go_search = QPushButton("🔍 Tìm truyện mới")
        btn_go_search.setStyleSheet("background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; font-weight: 700;")
        btn_go_search.clicked.connect(lambda: self.tabs.setCurrentIndex(0))
        top_row.addWidget(btn_go_search)

        btn_refresh = QPushButton("🔄 Làm mới")
        btn_refresh.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1;")
        btn_refresh.clicked.connect(self._load_library)
        top_row.addWidget(btn_refresh)
        layout.addLayout(top_row)

        # Books Table
        self.table_books = QTableWidget()
        self.table_books.setColumnCount(7)
        self.table_books.setHorizontalHeaderLabels([
            "ID", "Nguồn", "Tên Truyện", "Tác Giả", "Tiến Độ Lưu", "Đang Đọc", "Thao Tác"
        ])
        self.table_books.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_books.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_books.verticalHeader().setDefaultSectionSize(44)
        self.table_books.setColumnWidth(0, 50)
        self.table_books.setColumnWidth(1, 90)
        self.table_books.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_books.setColumnWidth(3, 140)
        self.table_books.setColumnWidth(4, 120)
        self.table_books.setColumnWidth(5, 180)
        self.table_books.setColumnWidth(6, 170)
        self.table_books.doubleClicked.connect(self._on_book_double_clicked)
        layout.addWidget(self.table_books)

    def _init_chapters_tab(self):
        layout = QVBoxLayout(self.tab_chapters)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Selected book summary header
        self.box_selected_book = QFrame()
        self.box_selected_book.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        book_info_layout = QHBoxLayout(self.box_selected_book)
        book_info_layout.setContentsMargins(12, 6, 12, 6)

        self.lbl_active_book_title = QLabel("Chưa chọn bộ truyện nào")
        self.lbl_active_book_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e3a8a;")
        book_info_layout.addWidget(self.lbl_active_book_title, 1)

        self.lbl_active_book_stats = QLabel("0 / 0 chương đã tải")
        self.lbl_active_book_stats.setStyleSheet("font-weight: 600; color: #059669; font-size: 13px;")
        book_info_layout.addWidget(self.lbl_active_book_stats)

        layout.addWidget(self.box_selected_book)

        # Action Toolbar for Downloading
        bar_actions = QHBoxLayout()
        bar_actions.setSpacing(8)

        self.btn_dl_missing = QPushButton("⬇ Tải các chương chưa lưu")
        self.btn_dl_missing.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_dl_missing.clicked.connect(self._download_missing_chapters)
        bar_actions.addWidget(self.btn_dl_missing)

        self.btn_dl_all = QPushButton("⬇ Tải toàn bộ truyện")
        self.btn_dl_all.setStyleSheet("background-color: #0284c7; color: white; font-weight: 700;")
        self.btn_dl_all.clicked.connect(self._download_all_chapters)
        bar_actions.addWidget(self.btn_dl_all)

        # Range download
        bar_actions.addWidget(QLabel("Khoảng:"))
        self.spin_from = QSpinBox()
        self.spin_from.setMinimum(1)
        self.spin_from.setMaximum(99999)
        self.spin_from.setValue(1)
        bar_actions.addWidget(self.spin_from)

        bar_actions.addWidget(QLabel("đến:"))
        self.spin_to = QSpinBox()
        self.spin_to.setMinimum(1)
        self.spin_to.setMaximum(99999)
        self.spin_to.setValue(50)
        bar_actions.addWidget(self.spin_to)

        self.btn_dl_range = QPushButton("⬇ Tải theo khoảng")
        self.btn_dl_range.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; font-weight: 700;")
        self.btn_dl_range.clicked.connect(self._download_range_chapters)
        bar_actions.addWidget(self.btn_dl_range)

        bar_actions.addStretch(1)

        self.btn_stop_dl = QPushButton("🛑 Dừng Tải")
        self.btn_stop_dl.setStyleSheet("background-color: #ef4444; color: white;")
        self.btn_stop_dl.setEnabled(False)
        self.btn_stop_dl.clicked.connect(self._stop_download)
        bar_actions.addWidget(self.btn_stop_dl)

        layout.addLayout(bar_actions)

        # Progress bar and status
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Sẵn sàng.")
        self.lbl_status.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        # Chapter Filter / Search
        filter_layout = QHBoxLayout()
        self.txt_filter_chapter = QLineEdit()
        self.txt_filter_chapter.setPlaceholderText("🔍 Tìm nhanh chương trong danh sách theo số hoặc tên...")
        self.txt_filter_chapter.textChanged.connect(self._filter_chapters_table)
        filter_layout.addWidget(self.txt_filter_chapter)
        layout.addLayout(filter_layout)

        # Chapters Table
        self.table_chapters = QTableWidget()
        self.table_chapters.setColumnCount(5)
        self.table_chapters.setHorizontalHeaderLabels(["STT", "ID Chương", "Tên Chương", "Trạng Thái", "Thao Tác"])
        self.table_chapters.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_chapters.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_chapters.verticalHeader().setDefaultSectionSize(40)
        self.table_chapters.setColumnWidth(0, 60)
        self.table_chapters.setColumnWidth(1, 110)
        self.table_chapters.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_chapters.setColumnWidth(3, 150)
        self.table_chapters.setColumnWidth(4, 100)
        self.table_chapters.doubleClicked.connect(self._on_chapter_double_clicked)
        layout.addWidget(self.table_chapters)

    def _init_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        lbl_sec1 = QLabel("📦 XUẤT TRỌN BỘ TRUYỆN ĐÃ LƯU")
        lbl_sec1.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e3a8a;")
        layout.addWidget(lbl_sec1)

        box_export = QFrame()
        box_export.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px;")
        exp_layout = QVBoxLayout(box_export)

        lbl_exp_desc = QLabel("Xuất toàn bộ các chương đã tải của bộ truyện đang chọn ra 1 file text (.txt) duy nhất để copy vào điện thoại, máy đọc sách Kindle, Kobo hoặc đọc offline.")
        lbl_exp_desc.setWordWrap(True)
        lbl_exp_desc.setStyleSheet("color: #334155; margin-bottom: 8px;")
        exp_layout.addWidget(lbl_exp_desc)

        btn_export_all = QPushButton("📥 Xuất toàn bộ các chương đã lưu ra file TXT")
        btn_export_all.setStyleSheet("background-color: #2563eb; color: white; padding: 10px 20px; font-weight: 700;")
        btn_export_all.clicked.connect(self._export_full_book_txt)
        exp_layout.addWidget(btn_export_all, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(box_export)

        # Section 2: Config
        lbl_sec2 = QLabel("⚙️ CẤU HÌNH HỆ THỐNG")
        lbl_sec2.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e3a8a; margin-top: 16px;")
        layout.addWidget(lbl_sec2)

        box_cfg = QFrame()
        box_cfg.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px;")
        cfg_layout = QVBoxLayout(box_cfg)

        row_ip = QHBoxLayout()
        row_ip.addWidget(QLabel("Máy chủ Sáng Tác Việt (Base URL):"))
        self.txt_base_url = QLineEdit(self.base_url)
        self.txt_base_url.setFixedWidth(280)
        row_ip.addWidget(self.txt_base_url)
        btn_save_url = QPushButton("Lưu")
        btn_save_url.clicked.connect(self._on_save_base_url)
        row_ip.addWidget(btn_save_url)
        row_ip.addStretch(1)
        cfg_layout.addLayout(row_ip)

        lbl_db_info = QLabel(f"📁 Đường dẫn cơ sở dữ liệu SQLite: {self.db.db_path}")
        lbl_db_info.setStyleSheet("color: #64748b; font-size: 12px; margin-top: 8px;")
        cfg_layout.addWidget(lbl_db_info)

        layout.addWidget(box_cfg)
        layout.addStretch(1)

    def _on_save_base_url(self):
        new_url = self.txt_base_url.text().strip().rstrip('/')
        if new_url:
            self.base_url = new_url
            QMessageBox.information(self, "Đã cập nhật", f"Máy chủ được đặt thành: {self.base_url}")

    def _load_library(self):
        books = self.db.get_books()
        self.table_books.setRowCount(len(books))

        for row, b in enumerate(books):
            self.table_books.setItem(row, 0, QTableWidgetItem(str(b['id'])))
            self.table_books.setItem(row, 1, QTableWidgetItem(b['host'].upper()))
            self.table_books.setItem(row, 2, QTableWidgetItem(b['title']))
            self.table_books.setItem(row, 3, QTableWidgetItem(b['author'] or "Chưa rõ"))

            # Progress item
            dl = b['downloaded_count'] or 0
            tot = b['total_chapters'] or 1
            pct = int((dl / tot) * 100) if tot > 0 else 0
            prog_text = f"{dl} / {tot} ({pct}%)"
            item_prog = QTableWidgetItem(prog_text)
            if dl == tot and tot > 0:
                item_prog.setForeground(QColor("#15803d"))
            self.table_books.setItem(row, 4, item_prog)

            last_read = b['last_read_chapter_title'] or "Chưa đọc"
            self.table_books.setItem(row, 5, QTableWidgetItem(last_read))

            # Action button widget
            btn_panel = QWidget()
            h = QHBoxLayout(btn_panel)
            h.setContentsMargins(4, 2, 4, 2)
            h.setSpacing(6)

            btn_open = QPushButton("📑 Quản lý & Tải")
            btn_open.setStyleSheet("background: #2563eb; color: white; padding: 4px 8px; font-weight: 600;")
            b_fk = b['id']
            btn_open.clicked.connect(lambda _, x=b_fk: self.open_book_chapters(x))
            h.addWidget(btn_open)

            btn_del = QPushButton("🗑 Xóa")
            btn_del.setStyleSheet("background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; padding: 4px 8px;")
            btn_del.clicked.connect(lambda _, x=b_fk: self._delete_book(x))
            h.addWidget(btn_del)

            self.table_books.setCellWidget(row, 6, btn_panel)

    def _delete_book(self, book_fk: int):
        book = self.db.get_book_by_id(book_fk)
        if not book:
            return
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa truyện '{book['title']}' cùng toàn bộ chương đã lưu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_book(book_fk)
            self._load_library()
            if self.current_book_fk == book_fk:
                self.current_book_fk = None
                self.table_chapters.setRowCount(0)
                self.lbl_active_book_title.setText("Chưa chọn bộ truyện nào")

    def _on_book_double_clicked(self, index):
        row = index.row()
        b_id_item = self.table_books.item(row, 0)
        if b_id_item:
            self.open_book_chapters(int(b_id_item.text()))

    def open_book_chapters(self, book_fk: int):
        self.current_book_fk = book_fk
        book = self.db.get_book_by_id(book_fk)
        if not book:
            return

        self.lbl_active_book_title.setText(f"📖 [{book['host'].upper()}] {book['title']}")
        dl = book['downloaded_count'] or 0
        tot = book['total_chapters'] or 0
        self.lbl_active_book_stats.setText(f"{dl} / {tot} chương đã lưu")

        self.spin_from.setValue(1)
        self.spin_to.setMaximum(tot if tot > 0 else 99999)
        self.spin_to.setValue(min(50, tot if tot > 0 else 50))

        self._load_chapters_table(book_fk)
        self.tabs.setCurrentIndex(2) # Switch to chapters tab

    def _load_chapters_table(self, book_fk: int):
        chapters = self.db.get_chapters(book_fk)
        self.table_chapters.setRowCount(len(chapters))

        for row, c in enumerate(chapters):
            self.table_chapters.setItem(row, 0, QTableWidgetItem(str(c['chapter_index'])))
            self.table_chapters.setItem(row, 1, QTableWidgetItem(c['chapter_id']))
            self.table_chapters.setItem(row, 2, QTableWidgetItem(c['chapter_title']))

            # Status badge
            if c['is_downloaded']:
                status_item = QTableWidgetItem("✅ Đã lưu Offline")
                status_item.setForeground(QColor("#15803d"))
            else:
                status_item = QTableWidgetItem("⏳ Chưa lưu")
                status_item.setForeground(QColor("#94a3b8"))
            self.table_chapters.setItem(row, 3, status_item)

            # Read button
            btn_read = QPushButton("Đọc")
            btn_read.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; padding: 4px 8px; font-weight: 600;")
            c_id = c['chapter_id']
            btn_read.clicked.connect(lambda _, x=book_fk, y=c_id: self.open_reader(x, y))
            self.table_chapters.setCellWidget(row, 4, btn_read)

    def _filter_chapters_table(self, text: str):
        query = text.strip().lower()
        for r in range(self.table_chapters.rowCount()):
            idx_item = self.table_chapters.item(r, 0)
            title_item = self.table_chapters.item(r, 2)
            match = True
            if query:
                idx_match = query in idx_item.text().lower() if idx_item else False
                title_match = query in title_item.text().lower() if title_item else False
                match = idx_match or title_match
            self.table_chapters.setRowHidden(r, not match)

    def _on_chapter_double_clicked(self, index):
        if not self.current_book_fk:
            return
        row = index.row()
        c_id_item = self.table_chapters.item(row, 1)
        if c_id_item:
            self.open_reader(self.current_book_fk, c_id_item.text())

    def open_reader(self, book_fk: int, chapter_id: str):
        self.reader_widget.load_chapter(book_fk, chapter_id)
        self.tabs.setCurrentIndex(3) # Switch to Reader tab

    def _download_missing_chapters(self):
        if not self.current_book_fk:
            QMessageBox.warning(self, "Chưa chọn truyện", "Vui lòng chọn một bộ truyện từ Tủ Sách trước!")
            return
        missing = self.db.get_undownloaded_chapters(self.current_book_fk)
        if not missing:
            QMessageBox.information(self, "Đã đủ", "Tất cả các chương của bộ truyện này đã được lưu đầy đủ!")
            return
        items = [(c['chapter_id'], c['chapter_title']) for c in missing]
        self._start_download_task(items)

    def _download_all_chapters(self):
        if not self.current_book_fk:
            QMessageBox.warning(self, "Chưa chọn truyện", "Vui lòng chọn một bộ truyện từ Tủ Sách trước!")
            return
        chapters = self.db.get_chapters(self.current_book_fk)
        items = [(c['chapter_id'], c['chapter_title']) for c in chapters]
        self._start_download_task(items)

    def _download_range_chapters(self):
        if not self.current_book_fk:
            QMessageBox.warning(self, "Chưa chọn truyện", "Vui lòng chọn một bộ truyện từ Tủ Sách trước!")
            return
        f_idx = self.spin_from.value()
        t_idx = self.spin_to.value()
        if f_idx > t_idx:
            QMessageBox.warning(self, "Sai khoảng", "Số chương bắt đầu phải nhỏ hơn hoặc bằng số chương kết thúc!")
            return

        chapters = self.db.get_chapters(self.current_book_fk)
        items = [
            (c['chapter_id'], c['chapter_title'])
            for c in chapters
            if f_idx <= c['chapter_index'] <= t_idx
        ]
        if not items:
            QMessageBox.warning(self, "Không có chương", "Không tìm thấy chương nào trong khoảng chỉ định!")
            return
        self._start_download_task(items)

    def _start_download_task(self, items):
        if self.download_worker and self.download_worker.isRunning():
            QMessageBox.warning(self, "Đang bận", "Một tiến trình tải khác đang chạy!")
            return

        book = self.db.get_book_by_id(self.current_book_fk)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(items))
        self.progress_bar.setValue(0)
        self.btn_stop_dl.setEnabled(True)
        self.btn_dl_missing.setEnabled(False)
        self.btn_dl_all.setEnabled(False)
        self.btn_dl_range.setEnabled(False)

        self.download_worker = ChapterDownloaderWorker(
            host=book['host'],
            book_id=book['book_id'],
            book_fk=self.current_book_fk,
            chapters_to_download=items,
            db=self.db,
            base_url=self.base_url
        )
        self.download_worker.sig_progress.connect(self._on_dl_progress)
        self.download_worker.sig_chapter_saved.connect(self._on_dl_chapter_saved)
        self.download_worker.sig_status.connect(self._on_dl_status)
        self.download_worker.sig_finished.connect(self._on_dl_finished)
        self.download_worker.start()

    def _on_dl_progress(self, current: int, total: int, title: str):
        self.progress_bar.setValue(current)

    def _on_dl_chapter_saved(self, c_id: str, title: str, count: int):
        for r in range(self.table_chapters.rowCount()):
            item = self.table_chapters.item(r, 1)
            if item and item.text() == c_id:
                st = self.table_chapters.item(r, 3)
                if st:
                    st.setText("✅ Đã lưu Offline")
                    st.setForeground(QColor("#15803d"))
                break

    def _on_dl_status(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_dl_finished(self, success: int, fail: int):
        self.progress_bar.setVisible(False)
        self.btn_stop_dl.setEnabled(False)
        self.btn_dl_missing.setEnabled(True)
        self.btn_dl_all.setEnabled(True)
        self.btn_dl_range.setEnabled(True)

        if self.current_book_fk:
            book = self.db.get_book_by_id(self.current_book_fk)
            if book:
                dl = book['downloaded_count'] or 0
                tot = book['total_chapters'] or 0
                self.lbl_active_book_stats.setText(f"{dl} / {tot} chương đã lưu")

        self._load_library()
        QMessageBox.information(
            self, "Hoàn tất tải chương",
            f"Quá trình tải hoàn tất:\n- Thành công: {success} chương\n- Thất bại: {fail} chương"
        )

    def _stop_download(self):
        if self.download_worker:
            self.download_worker.stop()
            self.btn_stop_dl.setEnabled(False)

    def _export_full_book_txt(self):
        if not self.current_book_fk:
            QMessageBox.warning(self, "Chưa chọn truyện", "Vui lòng chọn một bộ truyện cần xuất trước!")
            return

        book = self.db.get_book_by_id(self.current_book_fk)
        chapters = self.db.get_chapters(self.current_book_fk, only_downloaded=True)
        if not chapters:
            QMessageBox.warning(self, "Chưa có chương", "Bộ truyện này chưa có chương nào được lưu offline để xuất!")
            return

        safe_title = "".join([c for c in book['title'] if c.isalpha() or c.isdigit() or c in ' -_']).strip()
        default_filename = f"{safe_title}_Full_{len(chapters)}_chuong.txt"

        file_path, _ = QFileDialog.getSaveFileName(self, "Xuất toàn bộ truyện ra file TXT", default_filename, "Text Files (*.txt)")
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"=== {book['title']} ===\n")
                f.write(f"Tác giả: {book['author'] or 'Chưa rõ'}\n")
                f.write(f"Nguồn: Sáng Tác Việt ({book['host'].upper()})\n")
                f.write(f"Tổng số chương đã lưu: {len(chapters)}\n")
                f.write("=" * 40 + "\n\n")

                for c in chapters:
                    full_c = self.db.get_chapter_by_id(self.current_book_fk, c['chapter_id'])
                    f.write(f"\n\n{'=' * 30}\n")
                    f.write(f"{c['chapter_title']}\n")
                    f.write(f"{'=' * 30}\n\n")
                    f.write(full_c['content'] if full_c else "")

            QMessageBox.information(
                self, "Xuất file thành công",
                f"Đã xuất trọn bộ {len(chapters)} chương vào:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất file", f"Không thể xuất file: {e}")

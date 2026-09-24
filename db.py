import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stv_novel.db")

class STVDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host TEXT NOT NULL,
                    book_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT DEFAULT '',
                    intro TEXT DEFAULT '',
                    cover_url TEXT DEFAULT '',
                    total_chapters INTEGER DEFAULT 0,
                    downloaded_count INTEGER DEFAULT 0,
                    last_read_chapter_id TEXT DEFAULT '',
                    last_read_chapter_title TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(host, book_id)
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_fk INTEGER NOT NULL,
                    chapter_id TEXT NOT NULL,
                    chapter_index INTEGER NOT NULL,
                    chapter_title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    is_downloaded INTEGER DEFAULT 0,
                    downloaded_at TIMESTAMP,
                    FOREIGN KEY (book_fk) REFERENCES books(id) ON DELETE CASCADE,
                    UNIQUE(book_fk, chapter_id)
                );

                CREATE INDEX IF NOT EXISTS idx_chap_book ON chapters(book_fk, chapter_index);
            ''')

    def add_or_update_book(self, host: str, book_id: str, title: str, author: str = '',
                           intro: str = '', cover_url: str = '', total_chapters: int = 0) -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO books (host, book_id, title, author, intro, cover_url, total_chapters, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(host, book_id) DO UPDATE SET
                    title = excluded.title,
                    author = CASE WHEN excluded.author != '' THEN excluded.author ELSE books.author END,
                    intro = CASE WHEN excluded.intro != '' THEN excluded.intro ELSE books.intro END,
                    cover_url = CASE WHEN excluded.cover_url != '' THEN excluded.cover_url ELSE books.cover_url END,
                    total_chapters = CASE WHEN excluded.total_chapters > 0 THEN excluded.total_chapters ELSE books.total_chapters END,
                    updated_at = CURRENT_TIMESTAMP
            ''', (host, book_id, title, author, intro, cover_url, total_chapters))
            
            cursor.execute("SELECT id FROM books WHERE host = ? AND book_id = ?", (host, book_id))
            row = cursor.fetchone()
            return row['id'] if row else cursor.lastrowid

    def sync_chapter_list(self, book_fk: int, chapters_data: List[Tuple[str, str]]) -> int:
        """
        chapters_data: List of (chapter_id, chapter_title)
        """
        added = 0
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for idx, (c_id, c_title) in enumerate(chapters_data, start=1):
                cursor.execute('''
                    INSERT INTO chapters (book_fk, chapter_id, chapter_index, chapter_title)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(book_fk, chapter_id) DO UPDATE SET
                        chapter_index = excluded.chapter_index,
                        chapter_title = excluded.chapter_title
                ''', (book_fk, c_id, idx, c_title))
                added += 1

            # Update book total chapters and downloaded count
            self._update_book_counts(conn, book_fk)
        return added

    def save_chapter_content(self, book_fk: int, chapter_id: str, content: str, title: str = '') -> bool:
        if not content:
            return False
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if title:
                cursor.execute('''
                    UPDATE chapters SET
                        content = ?,
                        chapter_title = ?,
                        is_downloaded = 1,
                        downloaded_at = CURRENT_TIMESTAMP
                    WHERE book_fk = ? AND chapter_id = ?
                ''', (content, title, book_fk, chapter_id))
            else:
                cursor.execute('''
                    UPDATE chapters SET
                        content = ?,
                        is_downloaded = 1,
                        downloaded_at = CURRENT_TIMESTAMP
                    WHERE book_fk = ? AND chapter_id = ?
                ''', (content, book_fk, chapter_id))
            
            self._update_book_counts(conn, book_fk)
            return cursor.rowcount > 0

    def _update_book_counts(self, conn: sqlite3.Connection, book_fk: int):
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM chapters WHERE book_fk = ?", (book_fk,))
        total = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as dl FROM chapters WHERE book_fk = ? AND is_downloaded = 1", (book_fk,))
        dl = cursor.fetchone()['dl']
        cursor.execute('''
            UPDATE books SET total_chapters = ?, downloaded_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (total, dl, book_fk))

    def get_books(self) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books ORDER BY updated_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def get_book_by_id(self, book_fk: int) -> Optional[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books WHERE id = ?", (book_fk,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_book_by_host_and_id(self, host: str, book_id: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books WHERE host = ? AND book_id = ?", (host, book_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_book(self, book_fk: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM books WHERE id = ?", (book_fk,))

    def get_chapters(self, book_fk: int, only_downloaded: bool = False) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if only_downloaded:
                cursor.execute('''
                    SELECT id, book_fk, chapter_id, chapter_index, chapter_title, is_downloaded, downloaded_at
                    FROM chapters
                    WHERE book_fk = ? AND is_downloaded = 1
                    ORDER BY chapter_index ASC
                ''', (book_fk,))
            else:
                cursor.execute('''
                    SELECT id, book_fk, chapter_id, chapter_index, chapter_title, is_downloaded, downloaded_at
                    FROM chapters
                    WHERE book_fk = ?
                    ORDER BY chapter_index ASC
                ''', (book_fk,))
            return [dict(r) for r in cursor.fetchall()]

    def get_undownloaded_chapters(self, book_fk: int, limit: Optional[int] = None) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            query = '''
                SELECT id, book_fk, chapter_id, chapter_index, chapter_title
                FROM chapters
                WHERE book_fk = ? AND is_downloaded = 0
                ORDER BY chapter_index ASC
            '''
            if limit:
                query += f" LIMIT {int(limit)}"
            cursor.execute(query, (book_fk,))
            return [dict(r) for r in cursor.fetchall()]

    def get_chapter_by_id(self, book_fk: int, chapter_id: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM chapters WHERE book_fk = ? AND chapter_id = ?
            ''', (book_fk, chapter_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_chapter_by_index(self, book_fk: int, chapter_index: int) -> Optional[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM chapters WHERE book_fk = ? AND chapter_index = ?
            ''', (book_fk, chapter_index))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_last_read(self, book_fk: int, chapter_id: str, chapter_title: str):
        with self._get_conn() as conn:
            conn.execute('''
                UPDATE books SET
                    last_read_chapter_id = ?,
                    last_read_chapter_title = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (chapter_id, chapter_title, book_fk))

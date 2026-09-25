import os
import asyncio
import json
import logging
from typing import List, Tuple, Optional
try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    class QThread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
    class FakeSignal:
        def emit(self, *args, **kwargs): pass
        def connect(self, *args, **kwargs): pass
    def pyqtSignal(*args, **kwargs):
        return FakeSignal()

try:
    from .api import clean_chapter_content
    from .db import STVDatabase
except (ImportError, ValueError):
    try:
        from stv_novel_app.api import clean_chapter_content
        from stv_novel_app.db import STVDatabase
    except (ImportError, ValueError):
        from api import clean_chapter_content
        from db import STVDatabase


logger = logging.getLogger("STVDownloader")

class ChapterDownloaderWorker(QThread):
    sig_progress = pyqtSignal(int, int, str)          # current, total, chapter_title
    sig_chapter_saved = pyqtSignal(str, str, int)     # chapter_id, title, char_count
    sig_status = pyqtSignal(str)                      # general status message
    sig_finished = pyqtSignal(int, int)               # success_count, fail_count

    def __init__(self, host: str, book_id: str, book_fk: int,
                 chapters_to_download: List[Tuple[str, str]],
                 db: STVDatabase,
                 base_url: str = "http://14.225.254.182"):
        super().__init__()
        self.host = host
        self.book_id = book_id
        self.book_fk = book_fk
        self.chapters = chapters_to_download
        self.db = db
        self.base_url = base_url
        self._is_running = True

    def stop(self):
        self._is_running = False
        self.sig_status.emit("Đang dừng quá trình tải...")

    def run(self):
        if not self.chapters:
            self.sig_finished.emit(0, 0)
            return

        asyncio.run(self._async_download_loop())

    async def _async_download_loop(self):
        from playwright.async_api import async_playwright

        success_count = 0
        fail_count = 0
        total = len(self.chapters)

        self.sig_status.emit(f"Khởi động trình duyệt tải ngầm cho {total} chương...")

        pw = None
        browser = None
        try:
            ares_chrome = r'D:\ares_chromium_build\src\out\Release\chrome.exe'
            launch_args = {
                'headless': True,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-gpu'
                ]
            }
            if os.path.exists(ares_chrome):
                launch_args['executable_path'] = ares_chrome

            pw = await async_playwright().start()
            browser = await pw.chromium.launch(**launch_args)


            for idx, (c_id, c_title) in enumerate(self.chapters, start=1):
                if not self._is_running:
                    self.sig_status.emit("Đã tạm dừng tải theo yêu cầu.")
                    break

                self.sig_progress.emit(idx, total, c_title)
                self.sig_status.emit(f"[{idx}/{total}] Đang tải: {c_title}...")

                content = await self._fetch_single_chapter(browser, self.host, self.book_id, c_id)
                if content:
                    # Save to DB
                    self.db.save_chapter_content(self.book_fk, c_id, content, c_title)
                    success_count += 1
                    self.sig_chapter_saved.emit(c_id, c_title, len(content))
                else:
                    fail_count += 1
                    logger.warning(f"Failed to fetch chapter {c_id}: {c_title}")

                # Micro pause to prevent rate limiting
                await asyncio.sleep(0.3)

        except Exception as e:
            self.sig_status.emit(f"Lỗi phiên tải: {e}")
            logger.error(f"Downloader loop exception: {e}")
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if pw:
                try:
                    await pw.stop()
                except Exception:
                    pass

        self.sig_status.emit(f"Hoàn tất tải: {success_count} thành công, {fail_count} thất bại.")
        self.sig_finished.emit(success_count, fail_count)

    async def _fetch_single_chapter(self, browser, host: str, book_id: str, chapter_id: str, timeout: int = 12) -> Optional[str]:
        return await fetch_single_chapter_content(browser, host, book_id, chapter_id, self.base_url, timeout)

async def fetch_single_chapter_content(browser, host: str, book_id: str, chapter_id: str, base_url: str = "http://14.225.254.182", timeout: int = 12) -> Optional[str]:
    ctx = None
    try:
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        # Pre-seed essential STV cookies
        try:
            await ctx.add_cookies([
                {'name': 'lang', 'value': 'vi', 'domain': '14.225.254.182', 'path': '/'},
                {'name': 'hideavatar', 'value': 'false', 'domain': '14.225.254.182', 'path': '/'},
                {'name': 'cookieenabled', 'value': 'true', 'domain': '14.225.254.182', 'path': '/'}
            ])
        except Exception:
            pass

        page = await ctx.new_page()

        # Block media, fonts, images and analytics to boost download speed 5-10x and save memory
        async def block_junk(route):
            rtype = route.request.resource_type
            u = route.request.url
            if rtype in ['image', 'media', 'font'] or 'google' in u or 'facebook' in u or 'tts' in u:
                await route.abort()
            else:
                await route.continue_()

        await page.route('**/*', block_junk)

        chapter_data = None
        ev = asyncio.Event()

        async def on_resp(res):
            nonlocal chapter_data
            if 'sajax' in res.url or 'readc' in res.url or 'readchapter' in res.url:
                try:
                    text = await res.text()
                    if '"code":"0"' in text or '"code":0' in text:
                        chapter_data = json.loads(text)
                        ev.set()
                except Exception:
                    pass

        page.on('response', on_resp)
        url = f"{base_url}/truyen/{host}/1/{book_id}/{chapter_id}/"

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=10000)
        except Exception:
            pass

        # 1. Dismiss language modal if it appears
        try:
            vi_btn = await page.wait_for_selector('text=Tiếng Việt', timeout=1500)
            if vi_btn:
                await vi_btn.click()
        except Exception:
            pass

        # 2. Trigger fetch via gotox() if available
        try:
            await page.evaluate('if(typeof gotox === "function") gotox();')
        except Exception:
            pass

        # 3. Wait for AJAX response or DOM text
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

        # 5. Extract content from AJAX or fallback to DOM
        if chapter_data and 'data' in chapter_data:
            cleaned = clean_chapter_content(chapter_data['data'])
            if cleaned and len(cleaned) > 50:
                return cleaned

        # Fallback: check DOM #content-container
        try:
            c_el = await page.query_selector('#content-container')
            if c_el:
                dom_text = await c_el.inner_text()
                if dom_text and len(dom_text.strip()) > 100:
                    cleaned_dom = clean_chapter_content(dom_text)
                    return cleaned_dom
        except Exception:
            pass

        return None

    except Exception as e:
        logger.error(f"Error fetching chapter {chapter_id}: {e}")
        return None
    finally:
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass



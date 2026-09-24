import os
import sys
import socket
import uvicorn
import qrcode
import asyncio
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stv_novel_app.db import STVDatabase
from stv_novel_app.api import parse_story_input, fetch_book_metadata, fetch_chapter_list, search_stv, fetch_book_details_and_comments
from stv_novel_app.downloader import fetch_single_chapter_content
from stv_novel_app.epub_builder import create_epub

app = FastAPI(title="STV Novel Mobile Server")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "stv_novel.db")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
db = STVDatabase(DB_PATH)

# Global background download status tracker
# key: book_fk -> dict
download_states: Dict[int, dict] = {}
cancel_flags: Dict[int, bool] = {}

class AddBookReq(BaseModel):
    url: Optional[str] = None
    host: Optional[str] = None
    book_id: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    cover_url: Optional[str] = None

class DownloadReq(BaseModel):
    mode: str = "missing" # missing | all | range
    start_idx: Optional[int] = 1
    end_idx: Optional[int] = 50

@app.get("/manifest.json")
def get_manifest():
    return JSONResponse({
        "name": "STV Novel Studio",
        "short_name": "STV Novel",
        "description": "Đọc và tải truyện Sáng Tác Việt ngoại tuyến 100% trên iPhone",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "icons": [
            {
                "src": "/icon.png",
                "sizes": "256x256",
                "type": "image/png"
            }
        ]
    })

@app.get("/icon.png")
def get_icon():
    icon_path = os.path.join(ASSETS_DIR, "stv_icon.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Icon not found")

@app.get("/sw.js")
def get_service_worker():
    sw_path = os.path.join(BASE_DIR, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")

@app.get("/STVNovel.ipa")
def download_ipa():
    ipa_path = r"g:\AI\STVNovel.ipa"
    if os.path.exists(ipa_path):
        return FileResponse(ipa_path, media_type="application/octet-stream", filename="STVNovel.ipa")
    raise HTTPException(status_code=404, detail="IPA not found")

@app.get("/api/books")
def list_books():
    books = db.get_books()
    return JSONResponse(books)

@app.get("/api/search")
def api_search(
    query: str = "",
    host: str = "",
    category: str = "",
    sort: str = "",
    step: str = "",
    minc: str = "0",
    type_val: str = "",
    page: int = 1
):
    try:
        results = search_stv(
            query=query,
            host=host,
            category=category,
            sort=sort,
            step=step,
            minc=minc,
            type_val=type_val,
            page=page
        )
        return JSONResponse({"status": "success", "count": len(results), "page": page, "results": results})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e), "page": page, "results": []})

@app.post("/api/add_book")
def api_add_book(req: AddBookReq):
    host = req.host
    book_id = req.book_id
    if req.url:
        parsed = parse_story_input(req.url)
        if parsed:
            host, book_id = parsed

    if not host or not book_id:
        raise HTTPException(status_code=400, detail="Không tìm thấy thông tin host hoặc mã truyện (book_id)!")

    # Check if book already exists in DB
    existing_books = db.get_books()
    for b in existing_books:
        if b['host'].lower() == host.lower() and str(b['book_id']) == str(book_id):
            return JSONResponse({
                "status": "success",
                "book_id": b['id'],
                "title": b['title'],
                "total": b['total_chapters'],
                "host": host,
                "book_code": book_id,
                "already_exists": True
            })

    meta = fetch_book_metadata(host, book_id)
    title = req.title or meta.get('title') or f"{host.upper()} #{book_id}"
    author = req.author or meta.get('author') or ""
    intro = meta.get('intro') or ""
    cover_url = req.cover_url or meta.get('cover_url') or ""

    chaps = fetch_chapter_list(host, book_id)
    total_chaps = len(chaps)

    book_fk = db.add_or_update_book(host, book_id, title, author, intro, cover_url, total_chaps)
    if chaps:
        db.sync_chapter_list(book_fk, chaps)

    return JSONResponse({
        "status": "success",
        "book_id": book_fk,
        "title": title,
        "total": total_chaps,
        "host": host,
        "book_code": book_id,
        "already_exists": False
    })

@app.get("/api/book/{book_fk}")
def get_book_details(book_fk: int):
    book = db.get_book_by_id(book_fk)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db.get_chapters(book_fk)
    return JSONResponse({
        "book": book,
        "chapters": chapters
    })

@app.get("/api/book_preview/{host}/{book_id}")
def get_book_preview(host: str, book_id: str):
    try:
        preview = fetch_book_details_and_comments(host, book_id)
        # Check if already in user's library
        existing_books = db.get_books()
        in_library_id = None
        for b in existing_books:
            if b['host'].lower() == host.lower() and str(b['book_id']) == str(book_id):
                in_library_id = b['id']
                break
        preview['in_library_id'] = in_library_id
        return JSONResponse(preview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải thông tin truyện: {str(e)}")


@app.post("/api/delete_book/{book_fk}")
@app.delete("/api/book/{book_fk}")
def delete_book(book_fk: int):
    book = db.get_book_by_id(book_fk)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete_book(book_fk)
    
    # Clean export files if exist
    for f_pattern in [f"book_{book_fk}.epub", f"export_{book_fk}.txt"]:
        f_path = os.path.join(BASE_DIR, f_pattern)
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
            except Exception:
                pass
                
    return JSONResponse({"status": "success", "message": f"Đã xóa truyện '{book['title']}' khỏi tủ sách!"})

def get_browser_launch_kwargs():
    ares_chrome = r'D:\ares_chromium_build\src\out\Release\chrome.exe'
    kwargs = {
        'headless': True,
        'args': ['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
    }
    if os.path.exists(ares_chrome):
        kwargs['executable_path'] = ares_chrome
    return kwargs

@app.get("/api/chapter/{book_fk}/{chapter_id}")
async def get_chapter(book_fk: int, chapter_id: str):
    chap = db.get_chapter_by_id(book_fk, chapter_id)
    if not chap:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # If not downloaded yet, auto-fetch on the fly in real-time!
    if not chap.get('content') or not chap.get('is_downloaded'):
        book = db.get_book_by_id(book_fk)
        if book:
            from playwright.async_api import async_playwright
            pw = None
            browser = None
            try:
                pw = await async_playwright().start()
                browser = await pw.chromium.launch(**get_browser_launch_kwargs())
                content = await fetch_single_chapter_content(browser, book['host'], book['book_id'], chapter_id)
                if content:
                    db.save_chapter_content(book_fk, chapter_id, content, chap['chapter_title'])
                    chap['content'] = content
                    chap['is_downloaded'] = 1
            except Exception as e:
                print(f"Auto-fetch chapter error: {e}")
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

    return JSONResponse(chap)

async def run_batch_download(book_fk: int, items: list):
    from playwright.async_api import async_playwright

    book = db.get_book_by_id(book_fk)
    if not book:
        return

    cancel_flags[book_fk] = False
    download_states[book_fk] = {
        "status": "running",
        "current": 0,
        "total": len(items),
        "current_title": "Đang khởi động trình duyệt...",
        "success": 0,
        "fail": 0
    }

    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(**get_browser_launch_kwargs())

        for idx, (c_id, c_title) in enumerate(items, start=1):
            if cancel_flags.get(book_fk):
                break

            download_states[book_fk]["current"] = idx
            download_states[book_fk]["current_title"] = c_title

            content = await fetch_single_chapter_content(browser, book['host'], book['book_id'], c_id)
            if content:
                db.save_chapter_content(book_fk, c_id, content, c_title)
                download_states[book_fk]["success"] += 1
            else:
                download_states[book_fk]["fail"] += 1

            await asyncio.sleep(0.3)

    except Exception as e:
        download_states[book_fk]["error"] = str(e)
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

    download_states[book_fk]["status"] = "finished"

@app.post("/api/start_download/{book_fk}")
async def start_download(book_fk: int, req: DownloadReq, bg_tasks: BackgroundTasks):
    book = db.get_book_by_id(book_fk)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    cur_state = download_states.get(book_fk, {})
    if cur_state.get("status") == "running":
        return JSONResponse({"status": "running", "message": "Đang trong tiến trình tải!"})

    if req.mode == "missing":
        missing = db.get_undownloaded_chapters(book_fk)
        items = [(c['chapter_id'], c['chapter_title']) for c in missing]
    elif req.mode == "all":
        chapters = db.get_chapters(book_fk)
        items = [(c['chapter_id'], c['chapter_title']) for c in chapters]
    elif req.mode == "range":
        chapters = db.get_chapters(book_fk)
        items = [
            (c['chapter_id'], c['chapter_title'])
            for c in chapters
            if (req.start_idx or 1) <= c['chapter_index'] <= (req.end_idx or 99999)
        ]
    else:
        items = []

    if not items:
        return JSONResponse({"status": "empty", "message": "Không có chương nào cần tải!"})

    # Run in background asyncio
    asyncio.create_task(run_batch_download(book_fk, items))

    return JSONResponse({"status": "started", "total": len(items)})

@app.get("/api/download_status/{book_fk}")
def get_download_status(book_fk: int):
    st = download_states.get(book_fk, {"status": "idle", "current": 0, "total": 0, "current_title": "", "success": 0, "fail": 0})
    return JSONResponse(st)

@app.post("/api/cancel_download/{book_fk}")
def cancel_download(book_fk: int):
    cancel_flags[book_fk] = True
    if book_fk in download_states:
        download_states[book_fk]["status"] = "canceled"
    return JSONResponse({"status": "canceled"})

@app.get("/api/sync_offline/{book_fk}")
def sync_offline(book_fk: int):
    """
    Returns all downloaded chapters with full text for client-side offline storage on iPhone.
    """
    chapters = db.get_chapters(book_fk, only_downloaded=True)
    full_data = []
    for c in chapters:
        row = db.get_chapter_by_id(book_fk, c['chapter_id'])
        if row and row.get('content'):
            full_data.append({
                "chapter_id": c['chapter_id'],
                "chapter_index": c['chapter_index'],
                "chapter_title": c['chapter_title'],
                "content": row['content']
            })
    return JSONResponse({"book_id": book_fk, "total": len(full_data), "chapters": full_data})

@app.get("/api/export_epub/{book_fk}")
def export_epub(book_fk: int):
    book = db.get_book_by_id(book_fk)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    chapters = db.get_chapters(book_fk, only_downloaded=True)
    if not chapters:
        raise HTTPException(status_code=400, detail="Chưa có chương nào được tải về!")

    full_chaps = []
    for c in chapters:
        full = db.get_chapter_by_id(book_fk, c['chapter_id'])
        if full and full.get('content'):
            full_chaps.append({'title': c['chapter_title'], 'content': full['content']})

    epub_name = f"book_{book_fk}.epub"
    epub_path = os.path.join(BASE_DIR, epub_name)
    create_epub(book['title'], book['author'], full_chaps, epub_path)

    import urllib.parse
    ascii_title = "".join([c for c in book['title'] if c.isascii() and (c.isalnum() or c in ' -_')]).strip() or f"book_{book_fk}"
    ascii_filename = f"{ascii_title}.epub"
    encoded_filename = urllib.parse.quote(f"{book['title']}.epub")

    return FileResponse(
        epub_path,
        media_type="application/epub+zip",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        }
    )

@app.get("/api/export_txt/{book_fk}")
def export_txt(book_fk: int):
    book = db.get_book_by_id(book_fk)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    chapters = db.get_chapters(book_fk, only_downloaded=True)
    if not chapters:
        raise HTTPException(status_code=400, detail="Chưa có chương nào được tải về!")

    import urllib.parse
    ascii_title = "".join([c for c in book['title'] if c.isascii() and (c.isalnum() or c in ' -_')]).strip() or f"book_{book_fk}"
    ascii_filename = f"{ascii_title}.txt"
    encoded_filename = urllib.parse.quote(f"{book['title']}.txt")
    txt_path = os.path.join(BASE_DIR, f"export_{book_fk}.txt")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"=== {book['title']} ===\n")
        f.write(f"Tác giả: {book['author'] or 'Chưa rõ'}\n")
        f.write(f"Nguồn: Sáng Tác Việt ({book['host'].upper()})\n\n")
        for c in chapters:
            full = db.get_chapter_by_id(book_fk, c['chapter_id'])
            f.write(f"\n\n{'=' * 30}\n{c['chapter_title']}\n{'=' * 30}\n\n")
            f.write(full['content'] if full else "")

    return FileResponse(
        txt_path,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        }
    )

# Mobile PWA HTML Client
INDEX_HTML_PATH = os.path.join(BASE_DIR, "mobile_index.html")
@app.get("/", response_class=HTMLResponse)
def index_page():
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>STV Novel Server Running</h1>")

@app.get("/sw.js")
def service_worker():
    sw_code = """
    const CACHE_NAME = 'stv-mobile-v2';
    self.addEventListener('install', (e) => {
        e.waitUntil(
            caches.open(CACHE_NAME).then((cache) => cache.addAll(['/', '/manifest.json', '/icon.png']))
        );
    });
    self.addEventListener('fetch', (e) => {
        e.respondWith(
            fetch(e.request).catch(() => caches.match(e.request))
        );
    });
    """
    return Response(content=sw_code, media_type="application/javascript")

def generate_qr_code(url: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qr_path = os.path.join(ASSETS_DIR, "iphone_qr.png")
    img.save(qr_path)
    return qr_path

def start_server(port=8899):
    lan_ip = "192.168.0.51"
    mobile_url = f"http://{lan_ip}:{port}"
    qr_file = generate_qr_code(mobile_url)
    print("=" * 60)
    print("STV NOVEL IPHONE MOBILE SERVER READY!")
    print(f"URL for iPhone Safari: {mobile_url}")
    print(f"QR Code image: {qr_file}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == "__main__":
    start_server()

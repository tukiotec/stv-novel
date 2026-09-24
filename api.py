import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Optional

DEFAULT_BASE = "http://14.225.254.182"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8'
}

def parse_story_input(raw_input: str) -> Optional[Tuple[str, str]]:
    """
    Parses user input into (host, book_id).
    Accepts:
      - Full URL: http://14.225.254.182/truyen/qidian/1/1050754857/
      - Chapter URL: http://14.225.254.182/truyen/qidian/1/1050754857/926800288/
      - Domain URL: https://sangtacviet.com/truyen/qidian/1/1050754857/
      - Short form: qidian/1050754857 or qidian:1050754857
    """
    text = raw_input.strip()
    if not text:
        return None

    # Match /truyen/{host}/1/{book_id}
    m = re.search(r'/truyen/([a-zA-Z0-9_\-]+)/[0-9]+/([a-zA-Z0-9_\-]+)', text)
    if m:
        return m.group(1).lower(), m.group(2)

    # Match host/book_id or host:book_id
    m = re.match(r'^([a-zA-Z0-9_\-]+)[:/]([a-zA-Z0-9_\-]+)$', text)
    if m:
        return m.group(1).lower(), m.group(2)

    return None

def search_stv(
    query: str = "",
    host: str = "",
    category: str = "",
    sort: str = "",
    step: str = "",
    minc: str = "0",
    type_val: str = "",
    page: int = 1,
    base_url: str = DEFAULT_BASE
) -> List[Dict]:
    """
    Searches Sáng Tác Việt for books matching query and facets.
    Supports all web filter options:
      - query: keyword to match in title
      - host: 'qidian', 'fanqie', 'faloo', 'biqubao', '69shu', 'uukanshu', 'qimao', 'zongheng', 'sfacg'...
      - category: 'hh' (huyền huyễn), 'dt' (đô thị), 'dn' (đồng nhân), 'kh' (khoa huyễn), 'ls' (lịch sử), 'vd' (võng du), 'nt' (ngôn tình), 'dna' (dị năng), 'ld' (linh dị), 'ln' (light novel)...
      - sort: 'view' (lượt đọc), 'update' (mới cập nhật), 'viewweek', 'like', 'auto', 'new'...
      - step: '3' (hoàn thành), '1' (còn tiếp / đang ra), '2' (tạm ngưng)
      - minc: '0', '50', '100', '200', '500', '1000', '2000'
      - type_val: '' (tất cả), 'dich' (truyện dịch), 'sangtac', 'txt'
    """
    params = []
    clean_q = query.strip() if query else ""
    if clean_q:
        params.append(f"findinname={urllib.parse.quote(clean_q)}")
    else:
        params.append("findinname=")
    params.append("find=")
    if host:
        params.append(f"host={urllib.parse.quote(host.strip())}")
    if category:
        params.append(f"category={urllib.parse.quote(category.strip())}")
    if sort:
        params.append(f"sort={urllib.parse.quote(sort.strip())}")
    if step:
        params.append(f"step={urllib.parse.quote(step.strip())}")
    if minc and str(minc) != "0":
        params.append(f"minc={urllib.parse.quote(str(minc).strip())}")
    if type_val:
        params.append(f"type={urllib.parse.quote(type_val.strip())}")
    if page and int(page) > 1:
        params.append(f"p={int(page)}")

    q_str = "&".join(params)
    url = f"{base_url}/io/searchtp/searchBooks?{q_str}"
    hdrs = dict(HEADERS)
    hdrs['Referer'] = f"{base_url}/?find=&{q_str}"

    try:
        resp = requests.get(url, headers=hdrs, timeout=12)
        raw_html = resp.content.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error searching STV: {e}")
        return []

    soup = BeautifulSoup(raw_html, 'html.parser')
    results = []
    items = soup.find_all('a', class_='booksearch')
    for a in items:
        href = a.get('href', '')
        img = a.find('img')
        cover = img.get('src') if img else ''
        title_tag = a.find(class_='searchbooktitle')
        title = title_tag.get_text(strip=True) if title_tag else ''
        author_tag = a.find(class_='searchbookauthor')
        author = author_tag.get_text(strip=True) if author_tag else ''

        m = href.strip('/').split('/')
        if len(m) >= 4 and m[0] == 'truyen':
            h = m[1].lower()
            b_id = m[3]
        else:
            h = ""
            b_id = ""

        views, likes, chapters, status_text = '', '', '', ''
        info = a.find(class_='info')
        if info:
            for s in info.find_all('span'):
                icon = s.find('i')
                if icon:
                    cls = icon.get('class', [])
                    txt = s.get_text(strip=True)
                    if 'fa-eye' in cls:
                        views = txt
                    elif 'fa-thumbs-up' in cls:
                        likes = txt
                    elif 'fa-copyright' in cls:
                        chapters = txt

        star_tag = a.find(lambda el: el.name == 'span' and el.find('i', class_='fa-star'))
        if star_tag:
            status_text = star_tag.get_text(strip=True)

        if title and (h and b_id or href):
            results.append({
                'title': title,
                'author': author,
                'cover_url': cover,
                'href': href,
                'host': h,
                'book_id': b_id,
                'views': views,
                'likes': likes,
                'chapters': chapters,
                'status': status_text
            })
    return results

def fetch_book_metadata(host: str, book_id: str, base_url: str = DEFAULT_BASE) -> Dict:
    url = f"{base_url}/truyen/{host}/1/{book_id}/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        html = resp.content.decode('utf-8', errors='ignore')
    except Exception as e:
        return {'title': f'{host.upper()} #{book_id}', 'author': '', 'intro': '', 'cover_url': '', 'error': str(e)}

    soup = BeautifulSoup(html, 'html.parser')
    
    meta_map = {}
    for meta in soup.find_all('meta'):
        prop = meta.get('property') or meta.get('name') or meta.get('itemprop')
        if prop and meta.get('content'):
            meta_map[prop.lower()] = meta['content'].strip()

    title = meta_map.get('og:novel:book_name') or meta_map.get('og:title')
    if not title:
        h1 = soup.find('h1')
        title = h1.text.strip() if h1 else f"{host.upper()} #{book_id}"

    # Clean title suffix if exists
    title = re.sub(r'\s*-\s*[0-9]+\s*chương.*$', '', title, flags=re.IGNORECASE).strip()

    author = meta_map.get('og:novel:author', '')
    intro = meta_map.get('og:description', '')
    cover_url = meta_map.get('og:image') or meta_map.get('thumbnail', '')

    return {
        'host': host,
        'book_id': book_id,
        'title': title,
        'author': author,
        'intro': intro,
        'cover_url': cover_url
    }

def fetch_chapter_list(host: str, book_id: str, base_url: str = DEFAULT_BASE) -> List[Tuple[str, str]]:
    """
    Returns list of (chapter_id, chapter_title)
    """
    api_url = f"{base_url}/index.php?ngmar=chapterlist&h={host}&bookid={book_id}&sajax=getchapterlist"
    referer_url = f"{base_url}/truyen/{host}/1/{book_id}/"
    hdrs = dict(HEADERS)
    hdrs['Referer'] = referer_url
    
    try:
        resp = requests.get(api_url, headers=hdrs, timeout=12)
        data = resp.json()
        if data.get('code') != 1 or not data.get('data'):
            return []
        
        raw_data = data['data']
        chapters = []
        for item in raw_data.split('-//-'):
            if not item.strip():
                continue
            parts = item.split('-/-')
            if len(parts) >= 2:
                c_id = parts[1].strip()
                c_title = parts[2].strip() if len(parts) > 2 else f"Chương {len(chapters) + 1}"
                chapters.append((c_id, c_title))
            elif len(parts) == 1:
                chapters.append((parts[0].strip(), f"Chương {len(chapters) + 1}"))

        return chapters
    except Exception as e:
        print(f"Error fetching chapter list: {e}")
        return []

def clean_chapter_content(raw_html: str) -> str:
    """
    Cleans chapter text from raw HTML payload returned by Sáng Tác Việt.
    Strips watermark badges, translates breaks to clean paragraphs,
    and strips out ruby/annotation tags while keeping inner text.
    """
    if not raw_html:
        return ""
        
    # Remove system watermarks
    clean = re.sub(r'<p><span[^>]*>@Bạn đang đọc[^<]*</span></p>', '', raw_html, flags=re.IGNORECASE)
    clean = re.sub(r'<span[^>]*style=[\'"][^\'"]*color:gray[^\'"]*[\'"][^>]*>.*?</span>', '', clean, flags=re.IGNORECASE)
    
    # Replace paragraphs and breaks with newlines
    clean = clean.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    clean = clean.replace('</p>', '\n\n')
    
    # BeautifulSoup parsing to get clean text
    soup = BeautifulSoup(clean, 'html.parser')
    text = soup.get_text()
    
    # Normalize unicode spaces and quotes
    text = text.replace('\xa0', ' ')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def fetch_book_details_and_comments(host: str, book_id: str, base_url: str = DEFAULT_BASE) -> Dict:
    """
    Fetches full book details (title, author, cover, intro, stats)
    and real-time reader comments from Sáng Tác Việt.
    """
    url = f"{base_url}/truyen/{host}/1/{book_id}/"
    headers = dict(HEADERS)
    
    title = f"{host.upper()} #{book_id}"
    author = ""
    cover_url = ""
    intro = ""
    views = ""
    likes = ""
    in_library = ""
    following = ""

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        html = resp.content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')

        # 1. Title
        h1 = soup.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            meta_t = soup.find('meta', property='og:title')
            title = meta_t['content'].strip() if meta_t else title
        title = re.sub(r'\s*-\s*[0-9]+\s*chương.*$', '', title, flags=re.IGNORECASE).strip()

        # 2. Author
        meta_a = soup.find('meta', property='og:novel:author')
        if meta_a:
            author = meta_a.get('content', '').strip()

        # 3. Cover
        meta_c = soup.find('meta', property='og:image')
        if meta_c:
            cover_url = meta_c.get('content', '').strip()

        # 4. Intro
        sum_el = soup.find(id='book-sumary') or soup.find(class_='blk-body')
        if sum_el:
            intro = sum_el.text.strip()
        if not intro:
            og_d = soup.find('meta', property='og:description')
            intro = og_d.get('content', '').strip() if og_d else ''
        intro = re.sub(r'\n{3,}', '\n\n', intro)

    except Exception as e:
        print(f"Error fetching book details: {e}")

    # 5. Comments from STV API
    comments = []
    try:
        cmt_url = f"{base_url}/io/comment/webComments"
        c_hdrs = dict(HEADERS)
        c_hdrs['Referer'] = url
        c_hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
        c_data = {
            'start': '0',
            'objectid': str(book_id),
            'objecttype': str(host)
        }
        cr = requests.post(cmt_url, headers=c_hdrs, data=c_data, timeout=8)
        c_soup = BeautifulSoup(cr.text, 'html.parser')
        for sec in c_soup.find_all('div', class_='flex'):
            top = sec.find(class_='sec-top')
            c_text = top.text.strip() if top else ''
            user_a = sec.find('a')
            user_name = user_a.text.strip() if user_a else 'Bạn đọc'
            av_img = sec.find('img', class_='comment-avatar')
            av_url = av_img.get('src', '') if av_img else ''
            t_span = sec.find(class_='timeelap')
            time_val = t_span.text.strip() if t_span else ''

            if c_text:
                comments.append({
                    'user': user_name,
                    'avatar': av_url,
                    'content': c_text,
                    'time': time_val
                })
    except Exception as e:
        print(f"Error fetching comments: {e}")

    return {
        'status': 'success',
        'host': host,
        'book_id': book_id,
        'title': title,
        'author': author,
        'cover_url': cover_url,
        'intro': intro or 'Chưa có tóm tắt giới thiệu cho bộ truyện này.',
        'comments': comments
    }

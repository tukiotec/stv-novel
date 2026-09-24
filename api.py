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

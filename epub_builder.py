import os
import zipfile
import html
from datetime import datetime
from typing import List, Dict

def create_epub(title: str, author: str, chapters: List[Dict[str, str]], output_path: str, cover_path: str = ""):
    """
    Creates a standard EPUB 3.0 file that opens natively in Apple Books on iPhone.
    chapters: list of dict {'title': str, 'content': str}
    """
    safe_title = html.escape(title)
    safe_author = html.escape(author or "Sáng Tác Việt")
    book_id = f"urn:uuid:stv-{abs(hash(title))}"

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 1. mimetype (must be first, uncompressed)
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        # 2. META-INF/container.xml
        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        z.writestr("META-INF/container.xml", container_xml)

        # 3. CSS
        css = '''body {
    font-family: -apple-system, "SF Pro Text", "Helvetica Neue", sans-serif;
    line-height: 1.8;
    margin: 1.5em;
    color: #1a1a1a;
    background-color: #ffffff;
}
h1 {
    font-size: 1.5em;
    font-weight: bold;
    text-align: center;
    margin-top: 1.5em;
    margin-bottom: 1.5em;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 0.5em;
}
p {
    text-indent: 1.5em;
    margin-bottom: 1.2em;
    text-align: justify;
}
'''
        z.writestr("OEBPS/style.css", css)

        # 4. Chapters XHTML
        manifest_items = [
            '<item id="css" href="style.css" media-type="text/css"/>',
            '<item id="toc" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        ]
        spine_items = [
            '<itemref idref="toc"/>'
        ]
        ncx_navpoints = []
        nav_li = []

        for idx, ch in enumerate(chapters, start=1):
            ch_id = f"chap_{idx}"
            ch_filename = f"chapter_{idx}.xhtml"
            ch_title = html.escape(ch.get('title', f'Chương {idx}'))
            content_raw = ch.get('content', '')

            # Build HTML paragraphs
            paras = []
            for p in content_raw.split('\n\n'):
                p_text = p.strip()
                if p_text:
                    p_esc = html.escape(p_text).replace('\n', '<br/>')
                    paras.append(f"<p>{p_esc}</p>")

            ch_xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{ch_title}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <h1>{ch_title}</h1>
    {''.join(paras)}
</body>
</html>'''
            z.writestr(f"OEBPS/{ch_filename}", ch_xhtml)

            manifest_items.append(f'<item id="{ch_id}" href="{ch_filename}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{ch_id}"/>')

            ncx_navpoints.append(f'''<navPoint id="np_{idx}" playOrder="{idx}">
                <navLabel><text>{ch_title}</text></navLabel>
                <content src="{ch_filename}"/>
            </navPoint>''')

            nav_li.append(f'<li><a href="{ch_filename}">{ch_title}</a></li>')

        # 5. OEBPS/toc.xhtml (EPUB3 Nav)
        toc_xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>Mục Lục</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>Mục Lục</h1>
        <ol>
            {''.join(nav_li)}
        </ol>
    </nav>
</body>
</html>'''
        z.writestr("OEBPS/toc.xhtml", toc_xhtml)

        # 6. OEBPS/toc.ncx (EPUB2 compatibility)
        toc_ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>{safe_title}</text></docTitle>
    <navMap>
        {''.join(ncx_navpoints)}
    </navMap>
</ncx>'''
        z.writestr("OEBPS/toc.ncx", toc_ncx)

        # 7. OEBPS/content.opf
        now_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        content_opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:identifier id="BookId">{book_id}</dc:identifier>
        <dc:title>{safe_title}</dc:title>
        <dc:creator>{safe_author}</dc:creator>
        <dc:language>vi</dc:language>
        <meta property="dcterms:modified">{now_str}</meta>
    </metadata>
    <manifest>
        {''.join(manifest_items)}
    </manifest>
    <spine toc="ncx">
        {''.join(spine_items)}
    </spine>
</package>'''
        z.writestr("OEBPS/content.opf", content_opf)

    print(f"Generated clean EPUB 3.0: {output_path}")
    return output_path

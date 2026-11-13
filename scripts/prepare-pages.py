"""Post-process the static export for a GitHub Pages project site.

Prefixes raw public asset URLs with the base path (Next.js only rewrites
router-generated URLs) and removes secrets that get baked into client props.
"""
from pathlib import Path
import json
from html import escape, unescape
import re
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
out = root / 'out'
base = '/ReadingRecord'

names = [p.name for p in (root / 'public').iterdir() if not p.name.startswith('_')]
pattern = re.compile(
    r"""(?<=["'\`(=])/(""" + '|'.join(re.escape(n) for n in names) + r""")(?=[/"'\`)?#\s])"""
)

# Also prefix raw Notion page-ID links (32-char hex, e.g. /339bb804...) \
# so they resolve under the /ReadingRecord subpath on GitHub Pages.
page_pattern = re.compile(
    r"""(?<=["'\`(=])/[0-9a-f]{32}(?=[/"'\`)?#\s])"""
)

modified_references = 0
for f in out.rglob('*'):
    if f.is_file() and f.suffix in {'.html', '.js', '.css', '.json', '.xml'}:
        s = f.read_text()
        t, n_assets = pattern.subn(lambda m: base + m.group(0), s)
        # Prefix raw Notion page-ID links too, so gallery cards stay under
        # the /ReadingRecord project-site subpath on GitHub Pages.
        t, n_pages = page_pattern.subn(lambda m: base + m.group(0), t)
        if t != s:
            f.write_text(t)
            modified_references += n_assets + n_pages
        else:
            f.write_text(t)

# Next.js static export does not emit routes for Notion collection rows. The
# photo page links to those rows by page ID, so materialize each linked album
# as a tiny static page containing its Notion image blocks.
photo_page = out / 'photo.html'
album_links = re.findall(
    r'<a\b(?=[^>]*\bclass="[^"]*\bnotion-collection-card\b)[^>]*\bhref="/ReadingRecord/([0-9a-f]{32})"[^>]*>(.*?)</a>',
    photo_page.read_text() if photo_page.exists() else '',
    re.I | re.S,
)
albums_written = 0
for page_id, card_html in album_links:
    title_match = re.search(r'class="notion-page-title-text">(.*?)</span>', card_html, re.S)
    title = unescape(re.sub(r'<[^>]+>', '', title_match.group(1)).strip()) if title_match else '相册'
    payload = json.dumps({
        'pageId': '-'.join([page_id[:8], page_id[8:12], page_id[12:16], page_id[16:20], page_id[20:]]),
        'limit': 100,
        'chunkNumber': 0,
        'cursor': {'stack': []},
        'verticalColumns': False,
    }).encode()
    request = Request(
        'https://www.notion.so/api/v3/loadCachedPageChunk',
        data=payload,
        headers={'Content-Type': 'application/json', 'User-Agent': 'ReadingRecord-static-export/1.0'},
    )
    with urlopen(request, timeout=30) as response:
        record_map = json.loads(response.read())['recordMap']['block']
    page = record_map.get('-'.join([page_id[:8], page_id[8:12], page_id[12:16], page_id[16:20], page_id[20:]]), {}).get('value', {}).get('value', {})
    image_urls = []
    for block_id in page.get('content', []):
        block = record_map.get(block_id, {}).get('value', {}).get('value', {})
        if block.get('type') != 'image':
            continue
        rows = block.get('properties', {}).get('source', [])
        if rows and rows[0] and rows[0][0].startswith(('https://', 'http://')):
            image_urls.append(rows[0][0])
    images = '\n'.join(
        f'<figure><img src="{escape(src, quote=True)}" alt="{escape(title, quote=True)} photo {index}" loading="lazy"></figure>'
        for index, src in enumerate(image_urls, 1)
    ) or '<p class="empty">这个子相册暂时没有照片。</p>'
    album_html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · 相册</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#111;color:#f5f5f5;font:16px/1.6 system-ui,sans-serif}}
header{{max-width:1100px;margin:auto;padding:24px 20px}}a{{color:#ddd}}h1{{font-size:1.6rem;margin:0 0 8px}}
main{{max-width:1100px;margin:0 auto;padding:0 16px 40px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:14px}}
figure{{margin:0;background:#222;border-radius:8px;overflow:hidden}}img{{display:block;width:100%;height:auto}}.empty{{grid-column:1/-1;color:#aaa}}
</style></head><body><header><a href="/ReadingRecord/photo">← 返回相册</a><h1>{escape(title)}</h1><div>{len(image_urls)} 张照片</div></header><main>{images}</main></body></html>'''
    album_dir = out / page_id
    album_dir.mkdir(parents=True, exist_ok=True)
    (album_dir / 'index.html').write_text(album_html)
    albums_written += 1

# Notion config currently leaks a Mailchimp key into client-side props.
secret = re.compile(r'[0-9a-f]{32}-us\d+', re.I)
redacted = 0
for f in out.rglob('*'):
    if f.is_file() and f.suffix in {'.html', '.js', '.json', '.xml'}:
        s = f.read_text()
        t, n = secret.subn('REDACTED', s)
        if n:
            f.write_text(t)
            redacted += n

(out / '.nojekyll').touch()
print(json.dumps({'modified_references': modified_references, 'redacted': redacted,
                  'albums_written': albums_written,
                  'html_files': len(list(out.rglob('*.html')))}, indent=2))

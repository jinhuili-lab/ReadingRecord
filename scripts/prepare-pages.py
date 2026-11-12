"""Post-process the static export for a GitHub Pages project site.

Prefixes raw public asset URLs with the base path (Next.js only rewrites
router-generated URLs) and removes secrets that get baked into client props.
"""
from pathlib import Path
import json
import re

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

prefixed_references = 0
for f in out.rglob('*'):
    if f.is_file() and f.suffix in {'.html', '.js', '.css', '.json', '.xml'}:
        s = f.read_text()
        t, n_assets = pattern.subn(lambda m: base + m.group(0), s)
        # Prefix raw Notion page-ID links too, so gallery cards stay under
        # the /ReadingRecord project-site subpath on GitHub Pages.
        t, n_pages = page_pattern.subn(lambda m: base + m.group(0), t)
        if t != s:
            f.write_text(t)
            prefixed_references += n_assets + n_pages
        else:
            f.write_text(t)

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
print(json.dumps({'prefixed_references': prefixed_references, 'redacted': redacted,
                  'html_files': len(list(out.rglob('*.html')))}, indent=2))

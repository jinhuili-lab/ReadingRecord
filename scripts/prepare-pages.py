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

changed = 0
for f in out.rglob('*'):
    if f.is_file() and f.suffix in {'.html', '.js', '.css', '.json', '.xml'}:
        s = f.read_text()
        t = pattern.sub(lambda m: base + m.group(0), s)
        if t != s:
            f.write_text(t)
            changed += 1

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
print(json.dumps({'asset_files': changed, 'redacted': redacted,
                  'html_files': len(list(out.rglob('*.html')))}, indent=2))

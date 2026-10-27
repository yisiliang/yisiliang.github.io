#!/usr/bin/env python3
"""Publication check for the GitHub Pages output in docs/.

Verifies local links and anchors, duplicate IDs, single-sidebar markup, ZIP
retirement, metadata coverage, sitemap targets and required root files.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json, re, sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
SITE = 'https://yisiliang.github.io'
TOPICS = json.loads((DOCS / 'topics/topics.json').read_text())
CATALOG = json.loads((ROOT / 'tools/homepage/catalog.json').read_text())


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag in ('a', 'link', 'img', 'script', 'source', 'iframe', 'video', 'audio'):
            for key in ('href', 'src'):
                if attrs.get(key):
                    self.links.append(attrs[key])


def public_pages():
    pages = [DOCS / 'index.html', DOCS / 'topics/index.html']
    for group in CATALOG:
        if group.get('layout') == 'topics':
            continue
        pages += [DOCS / book['path'] / 'index.html' for book in group['books']]
    pages += [DOCS / 'topics' / topic['slug'] / 'index.html' for topic in TOPICS]
    return pages


def main():
    html_files = sorted(p for p in DOCS.rglob('*.html') if '.git' not in p.parts)
    parsed = {}
    for path in html_files:
        page = Page()
        page.feed(path.read_text(encoding='utf-8', errors='replace'))
        parsed[path] = page

    broken, missing_anchors, duplicates, zip_links = [], [], [], []
    for path, page in parsed.items():
        rel = path.relative_to(DOCS)
        for dup in sorted({x for x in page.ids if page.ids.count(x) > 1}):
            duplicates.append((str(rel), dup))
        for link in page.links:
            link = link.strip()
            if not link or link.startswith(('mailto:', 'tel:', 'javascript:', 'data:')):
                continue
            if link.lower().split('#')[0].endswith('.zip'):
                zip_links.append((str(rel), link))
            parts = urlsplit(link)
            if parts.scheme == 'http' and parts.netloc == 'yisiliang.github.io':
                parts = parts._replace(scheme='', netloc='')
            if parts.scheme or parts.netloc:
                continue
            target_path = unquote(parts.path)
            if target_path.startswith('/'):
                target = DOCS / target_path.lstrip('/')
            elif target_path:
                target = (path.parent / target_path).resolve()
            else:
                target = path
            if target_path.endswith('/') or target.is_dir():
                target = target / 'index.html'
            if not target.exists():
                broken.append((str(rel), link))
                continue
            if parts.fragment and target.suffix == '.html' and target in parsed:
                if unquote(parts.fragment) not in parsed[target].ids:
                    missing_anchors.append((str(rel), link))

    metadata_gaps = []
    for path in public_pages():
        if not path.is_file():
            metadata_gaps.append((str(path.relative_to(DOCS)), 'missing page'))
            continue
        head = path.read_text(encoding='utf-8').split('</head>')[0]
        for pattern in ('name="description"', 'rel="canonical"', 'property="og:title"',
                        'name="twitter:card"', 'rel="icon"'):
            count = head.count(pattern)
            if (count < 1) if pattern == 'rel="icon"' else (count != 1):
                metadata_gaps.append((str(path.relative_to(DOCS)), pattern, count))

    sidebar = [str(path.relative_to(DOCS)) for path, page in parsed.items()
               if 'id="right-toc"' in path.read_text(encoding='utf-8', errors='replace')]
    required = [DOCS / name for name in ('sitemap.xml', 'robots.txt', 'favicon.svg', '404.html')]
    missing_files = [str(path.relative_to(DOCS)) for path in required if not path.is_file()]

    sitemap_bad = []
    if (DOCS / 'sitemap.xml').is_file():
        tree = ET.parse(DOCS / 'sitemap.xml')
        for loc in tree.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
            url = loc.text.strip()
            local = DOCS / url[len(SITE):].lstrip('/')
            if url.endswith('/'):
                local = local / 'index.html'
            if not local.is_file():
                sitemap_bad.append(url)

    failures = {
        'broken links': broken,
        'missing anchors': missing_anchors,
        'duplicate ids': duplicates,
        'zip links': zip_links,
        'metadata gaps': metadata_gaps,
        'right sidebar markup': sidebar,
        'missing root files': missing_files,
        'sitemap targets': sitemap_bad,
    }
    for label, items in failures.items():
        print(f'{label}: {len(items)}')
        for item in items[:20]:
            print('   ', item)
    if any(failures.values()):
        return 1
    print(f'PASS: {len(html_files)} HTML pages, {len(public_pages())} public content pages, '
          'links, anchors, single sidebar, metadata, sitemap and root files')
    return 0


if __name__ == '__main__':
    sys.exit(main())

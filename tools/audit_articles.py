#!/usr/bin/env python3
"""Check every catalog article for local links, anchors and duplicate IDs.

This is a publication check, not a proof of technical explanations or runtime behavior.
Run per-book source verifiers separately with the matching upstream checkouts.
"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BOOKS = tuple(b['path'] for group in json.loads((ROOT/'tools/homepage/catalog.json').read_text()) if group.get('layout')!='topics' for b in group['books'])


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.body = [], [], []
        self.assets = []
        self.in_main = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag in ('a', 'img', 'script', 'link'):
            url = attrs.get('href') or attrs.get('src')
            if url:
                self.links.append(url)
                if tag != 'a':
                    self.assets.append(url)
        if tag == 'main':
            self.in_main = True
        # Download/navigation labels legitimately differ in offline editions.
        if tag in ('script', 'style', 'button', 'a'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag == 'main':
            self.in_main = False
        if tag in ('script', 'style', 'button', 'a'):
            self.skip -= 1

    def handle_data(self, data):
        if self.in_main and not self.skip:
            self.body.append(data)


def parse(source, label):
    page = Page()
    page.feed(source)
    duplicates = [x for x, n in Counter(page.ids).items() if n > 1]
    assert not duplicates, (label, 'duplicate IDs', duplicates)
    for url in page.links:
        parts = urlsplit(url)
        if not parts.path and not parts.scheme and not parts.netloc and parts.fragment:
            assert unquote(parts.fragment) in page.ids, (label, 'missing anchor', url)
    return page


def verify(name):
    folder = ROOT / 'docs' / name
    source = (folder / 'index.html').read_text()
    page = parse(source, name)
    assert source.count('cloud.umami.is/script.js') == 1, (name, 'tracker count')
    for url in page.links:
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not parts.path:
            continue
        path = unquote(parts.path)
        target = ROOT / 'docs' / path.lstrip('/') if path.startswith('/') else folder / path
        assert target.exists(), (name, 'missing local file', url)
    return {'article': name, 'ids': len(page.ids), 'links': len(page.links), 'status': 'PASS'}


if __name__ == '__main__':
    print(json.dumps([verify(name) for name in BOOKS], ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""Check all eight reviewed articles and the content of their existing offline ZIPs.

This is a publication check, not a proof of technical explanations or runtime behavior.
Run per-book source verifiers separately with the matching upstream checkouts.
"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ('mysql', 'nginx', 'springboot', 'nacos', 'distributed',
         'transformer', 'jvm', 'jdk-source')


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


def body(page):
    return re.sub(r'\s+', '', ''.join(page.body))


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
    archives = []
    for archive in sorted(folder.glob('*offline*.zip')):
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.testzip() is None, (name, 'ZIP integrity')
            names = set(zipped.namelist())
            indexes = [x for x in names if x.endswith('index.html')]
            assert len(indexes) == 1, (name, 'offline index count')
            index = indexes[0]
            offline = zipped.read(index).decode()
            assert 'cloud.umami.is' not in offline, (name, 'offline tracker')
            offline_page = parse(offline, str(archive))
            assert not any(urlsplit(x).scheme in ('http', 'https') or x.startswith('//')
                           for x in offline_page.assets), (name, 'offline network dependency')
            assert body(page) == body(offline_page), (name, 'online/offline body mismatch')
            for url in offline_page.links:
                parts = urlsplit(url)
                if parts.scheme or parts.netloc or not parts.path:
                    continue
                member = str(Path(index).parent / unquote(parts.path))
                assert member in names, (name, 'missing offline member', member)
            for member in names:
                local = folder / Path(member).relative_to(Path(index).parent)
                if local.is_file() and member != index:
                    assert zipped.read(member) == local.read_bytes(), (name, 'stale ZIP member', member)
            archives.append(archive.name)
    return {'article': name, 'ids': len(page.ids), 'links': len(page.links),
            'offline': archives or 'not provided in current checkout', 'status': 'PASS'}


if __name__ == '__main__':
    print(json.dumps([verify(name) for name in BOOKS], ensure_ascii=False, indent=2))

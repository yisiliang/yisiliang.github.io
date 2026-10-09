#!/usr/bin/env python3
"""Publication checks: fixed-source equality, anchors, assets, math and ZIP."""
from pathlib import Path
from html.parser import HTMLParser
from hashlib import sha256
from collections import Counter
import json, re, zipfile, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.codes, self.chapters, self.text = [], [], {}, [], []
        self.source = None
        self.in_code = False
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag in ('script','style'):
            self.ignored += 1
        if 'data-source' in a:
            self.source = a['data-source']
        if tag == 'code' and self.source:
            self.in_code = True
            self.codes[self.source] = ''
        if tag == 'article' and a.get('class') == 'chapter':
            self.chapters.append(a['id'])
        for attr in ('href','src'):
            if attr in a:
                self.links.append((tag,attr,a[attr]))

    def handle_endtag(self, tag):
        if tag == 'code':
            self.in_code = False
            self.source = None
        if tag in ('script','style'):
            self.ignored -= 1

    def handle_data(self, text):
        if self.in_code:
            self.codes[self.source] += text
        if not self.ignored:
            self.text.append(text)


def check_page(data, exists, offline=False):
    p = Page()
    p.feed(data)
    assert len(p.ids) == len(set(p.ids)), Counter(p.ids)
    assert len(p.chapters) == 11, p.chapters
    assert not re.search(r'面试|面试官|候选人|备考|interview', ''.join(p.text), re.I)
    for tag,attr,url in p.links:
        if url.startswith('#'):
            assert url[1:] in p.ids, url
        elif url.startswith('./'):
            target = url[2:].split('#')[0].split('?')[0]
            assert exists(target), target
        if offline and attr == 'src':
            assert not re.match(r'^(?:https?:)?//',url), url
    if offline:
        assert 'umami' not in data
    return p


def main():
    html = (ROOT/'index.html').read_text()
    p = check_page(html, lambda name: (ROOT/name).exists())
    assert 'cloud.umami.is/script.js' in html
    manifest = json.loads((ROOT/'source-evidence.json').read_text())
    original = (ROOT/manifest['file']).read_bytes()
    assert sha256(original).hexdigest() == manifest['sha256']
    lines = original.decode().splitlines(keepends=True)
    markdown = (ROOT/'handbook.md').read_text()
    assert len(manifest['windows']) == len(p.codes) == 10
    for entry in manifest['windows']:
        expected = ''.join(lines[entry['start']-1:entry['end']])
        assert p.codes[entry['id']] == expected, entry['id']
        md = re.search(r'<!-- source-window:'+re.escape(entry['id'])+r' -->.*?```c\n(.*?)```', markdown, re.S)
        assert md and md[1] == expected, ('Markdown',entry['id'])
        assert sha256(expected.encode()).hexdigest() == entry['sha256']
        assert f'#L{entry["start"]}-L{entry["end"]}' in html
    metadata = json.loads((ROOT/'metadata.json').read_text())
    assert p.chapters == [s['id'] for s in metadata['sections']]
    for name in ['flow','timeline']:
        svg = ET.fromstring((ROOT/f'diagrams/{name}.svg').read_bytes())
        ns = {'svg':'http://www.w3.org/2000/svg'}
        assert svg.find('svg:title',ns) is not None and svg.find('svg:desc',ns) is not None
    for name in ['lab.py','run-lab.py','build.py','verify.py']:
        compile((ROOT/name).read_text(), name, 'exec')
    # The simultaneous fresh-key table: first request has E=0; rejected
    # candidate remains uncommitted. Delay threshold and recovery are separate.
    candidates = [n*1000 for n in range(7)]
    assert [max(0,e)*1000//10000 if e <= 5000 else None for e in candidates] == [0,100,200,300,400,500,None]
    assert [max(0,e-2000)*1000//10000 if e <= 5000 else None for e in candidates] == [0,0,0,100,200,300,None]
    assert max(0,4000-10000*200//1000+1000) == 3000
    assert max(0,5000-10000*100//1000+1000) == 5000
    with zipfile.ZipFile(ROOT/'nginx-rate-limiting-offline.zip') as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        offline = archive.read('index.html').decode()
        op = check_page(offline, lambda name: name in names, offline=True)
        assert op.codes == p.codes
        assert 'href="../' not in offline
        for name in names-{'index.html','handbook.md'}:
            assert archive.read(name) == (ROOT/name).read_bytes(), name
        assert archive.read('handbook.md').decode() == (ROOT/'handbook.md').read_text().replace('(../nginx/#chapter-15)','(https://yisiliang.github.io/nginx/#chapter-15)')
    catalog = json.loads((ROOT.parents[1]/'tools/homepage/catalog.json').read_text())
    topic = next(b for g in catalog if g['id']=='topics' for b in g['books'] if b['path']=='nginx-rate-limiting')
    assert topic['topics'][0]['anchor'] in p.ids
    assert './nginx-rate-limiting/#principle' in (ROOT.parent/'index.html').read_text()
    print('PASS: 11 sections, 10 exact windows, 2 SVGs, math, public anchors/assets, standalone offline ZIP, homepage topic')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Structural publication checks for the four new source handbooks."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import json,re,zipfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.refs=[];self.assets=[];self.codes=0;self.svg=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a' and a.get('href','').startswith('#') and len(a['href'])>1:self.refs.append(a['href'][1:])
        if tag in ('img','script','link'):
            u=a.get('src') or a.get('href')
            if u and not u.startswith(('http:','https:','data:','#','//')):self.assets.append(u)
        if tag=='pre':self.codes+=1
        if tag=='svg':self.svg+=1

def verify(name):
    folder=ROOT/'docs'/name
    for required in ('index.html','handbook.md','VERIFICATION.md','metadata.json'):
        assert (folder/required).is_file(),f'{name}: missing {required}'
    assert not (folder/'handbook.md').read_text().startswith('---\n'),f'{name}: Jekyll would consume raw Markdown'
    source=(folder/'index.html').read_text();p=Page();p.feed(source)
    assert not [k for k,v in Counter(p.ids).items() if v>1],f'{name}: duplicate IDs'
    assert all(x in p.ids for x in p.refs),f'{name}: unresolved internal anchors'
    assert all((folder/u.split('#')[0].split('?')[0]).is_file() for u in p.assets),f'{name}: missing assets {p.assets}'
    assert source.count('cloud.umami.is/script.js')==1,f'{name}: tracker count'
    assert not re.search(r'/Users/|/private/tmp/|/tmp/codex-',source),f'{name}: local path published'
    for svg in folder.rglob('*.svg'):ET.parse(svg)
    packages=list(folder.glob('*offline*.zip'))
    assert packages,f'{name}: offline archive missing'
    for archive in packages:
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None,f'{name}: invalid archive'
            htmlfiles=[n for n in z.namelist() if n.endswith('.html')]
            assert htmlfiles,f'{name}: offline HTML missing'
            for n in htmlfiles:
                content=z.read(n).decode()
                assert 'cloud.umami.is/script.js' not in content,f'{name}: offline tracker'
    meta=json.loads((folder/'metadata.json').read_text())
    assert p.codes==meta['excerpts'],f'{name}: excerpt count differs from HTML'
    assert p.svg==meta['diagrams'],f'{name}: diagram count differs from HTML'
    assert re.fullmatch('[0-9a-f]{40}',meta['sha']),f'{name}: fixed SHA missing'
    return {'handbook':name,'metadata':meta,'html_pre_blocks':p.codes,'inline_svg':p.svg,'svg_files':len(list(folder.rglob('*.svg'))),'anchors':len(p.ids),'offline':[x.name for x in packages]}
if __name__=='__main__':
    output=[verify(name) for name in ('springboot','mysql','nginx','nacos')]
    print(json.dumps(output,ensure_ascii=False,indent=2))

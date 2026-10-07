#!/usr/bin/env python3
"""Validate guide assets. Optional fixed-source roots enable byte-for-byte checks."""
import argparse, hashlib, json, re, subprocess, zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

HERE=Path(__file__).resolve().parent

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.links=[];self.scripts=[];self.in_code=False;self.code=[];self.current=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):self.ids.append(a['id'])
        if tag in ('a','img') and a.get('href',a.get('src')):self.links.append(a.get('href',a.get('src')))
        if tag=='script' and a.get('src'):self.scripts.append(a['src'])
        if tag=='code' and a.get('class')=='language-java':self.in_code=True;self.current=[]
    def handle_endtag(self,tag):
        if tag=='code' and self.in_code:self.code.append(''.join(self.current));self.in_code=False
    def handle_data(self,data):
        if self.in_code:self.current.append(data)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source3',type=Path);ap.add_argument('--source2',type=Path);a=ap.parse_args()
    roots={'3.2.4':a.source3,'2.5.4':a.source2};m=json.loads((HERE/'source-manifest.json').read_text());meta=json.loads((HERE/'metadata.json').read_text());chapters=json.loads((HERE/'chapters.json').read_text())
    assert len(chapters)==meta['chapterCount']==28
    assert len(m)==meta['excerptCount']
    checked=0
    for version,root in roots.items():
        if root:
            actual=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
            assert actual==next(x['sha'] for x in m if x['version']==version)
    for s in m:
        code=(HERE/s['file']).read_text();assert hashlib.sha256(code.encode()).hexdigest()==s['sha256']
        if roots[s['version']]:
            original=(roots[s['version']]/s['path']).read_text().splitlines();assert code=='\n'.join(original[s['start']-1:s['end']])+'\n';checked+=1
        assert code.strip() and len(code.splitlines())>=3
    if (HERE/'offline.html').exists():
        offline_text=(HERE/'offline.html').read_text()
    else:
        with zipfile.ZipFile(HERE/'nacos-offline.zip') as archive:
            offline_text=archive.read('index.html').decode()
    public_text=(HERE/'index.html').read_text()
    index_tracker=0 if public_text==offline_text else 1
    for filename,text,tracker in [('index.html',public_text,index_tracker),('offline.html',offline_text,0)]:
        page=Page();page.feed(text)
        assert len(page.ids)==len(set(page.ids)),filename
        assert 'null' not in page.ids
        assert len(page.code)==len(m)
        assert {hashlib.sha256(x.encode()).hexdigest() for x in page.code}=={x['sha256'] for x in m},'HTML source text changed'
        for link in page.links:
            if link.startswith('#'):assert link[1:] in page.ids,link
            elif not link.startswith(('http:','https:','/')):assert (HERE/link.split('#')[0]).exists(),link
        assert text.count('data-website-id=')==tracker
        assert len(page.scripts)==tracker
        assert '/Users/' not in text and '/tmp/' not in text
        assert all(f'id="{c["id"]}"' in text for c in chapters)
    svgs=list((HERE/'diagrams').glob('*.svg'));assert len(svgs)==meta['diagramCount'];ids=[]
    for p in svgs:
        tree=ET.fromstring(p.read_text());ns={'s':'http://www.w3.org/2000/svg'}
        assert tree.find('s:title',ns) is not None and tree.find('s:desc',ns) is not None
        local={e.attrib['id'] for e in tree.iter() if 'id' in e.attrib};assert len(local)==sum('id' in e.attrib for e in tree.iter())
        for ref in re.findall(r'url\(#([^)]*)\)',p.read_text()):assert ref in local
        ids+=list(local)
    assert len(ids)==len(set(ids))
    if (HERE/'nacos-offline.zip').exists():
        with zipfile.ZipFile(HERE/'nacos-offline.zip') as z:
            assert z.testzip() is None
            p=Page();p.feed(z.read('index.html').decode());assert not p.scripts
            for link in p.links:
                if not link.startswith(('http:','https:','#','/')):assert link.split('#')[0] in z.namelist() or link.endswith('.zip'),link
            for name in z.namelist():
                if name.endswith('.html'):assert b'cloud.umami.is' not in z.read(name)
            assert z.read('apache-license.txt')==(HERE/'apache-license.txt').read_bytes()
            assert z.read('nacos-notice.txt')==(HERE/'nacos-notice.txt').read_bytes()
    print(json.dumps({'chapters':len(chapters),'diagrams':len(svgs),'excerpts':len(m),'fixed_source_windows_verified':checked,'html_anchor_svg_zip':'PASS'},ensure_ascii=False))

if __name__=='__main__':main()

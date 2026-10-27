#!/usr/bin/env python3
"""Validate guide assets. Optional fixed-source roots enable byte-for-byte checks."""
import argparse, hashlib, json, re, subprocess
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
    public_text=(HERE/'index.html').read_text()
    page=Page();page.feed(public_text)
    assert len(page.ids)==len(set(page.ids)),'index.html'
    assert 'null' not in page.ids
    assert len(page.code)==len(m)
    assert {hashlib.sha256(x.encode()).hexdigest() for x in page.code}=={x['sha256'] for x in m},'HTML source text changed'
    for link in page.links:
        if link.startswith('#'):assert link[1:] in page.ids,link
        elif not link.startswith(('http:','https:','/')):assert (HERE/link.split('#')[0]).exists(),link
    assert public_text.count('data-website-id=')==1
    assert len(page.scripts)==1
    assert '/Users/' not in public_text and '/tmp/' not in public_text
    assert all(f'id="{c["id"]}"' in public_text for c in chapters)
    svgs=list((HERE/'diagrams').glob('*.svg'));assert len(svgs)==meta['diagramCount'];ids=[]
    for p in svgs:
        tree=ET.fromstring(p.read_text());ns={'s':'http://www.w3.org/2000/svg'}
        assert tree.find('s:title',ns) is not None and tree.find('s:desc',ns) is not None
        local={e.attrib['id'] for e in tree.iter() if 'id' in e.attrib};assert len(local)==sum('id' in e.attrib for e in tree.iter())
        for ref in re.findall(r'url\(#([^)]*)\)',p.read_text()):assert ref in local
        ids+=list(local)
    assert len(ids)==len(set(ids))
    print(json.dumps({'chapters':len(chapters),'diagrams':len(svgs),'excerpts':len(m),'fixed_source_windows_verified':checked,'html_anchor_svg':'PASS'},ensure_ascii=False))

if __name__=='__main__':main()

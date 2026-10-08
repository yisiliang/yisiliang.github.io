#!/usr/bin/env python3
"""Apply the distributed article design without serializing handbook/source HTML.
Run after any handbook generator. CSS/JS are inlined for self-contained offline use.
"""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / 'tools/reader/style.css').read_text()
JS = (ROOT / 'tools/reader/controls.js').read_text()
BOOKS = {b['path']: b for c in json.loads((ROOT/'tools/homepage/catalog.json').read_text()) for b in c['books'] if b['path'] != 'distributed' and b.get('kind', 'source') == 'source'}

class Elements(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.offsets = [0]
        for line in source.splitlines(keepends=True): self.offsets.append(self.offsets[-1] + len(line))
        self.stack = []; self.found = []
    def position(self):
        row,col = self.getpos(); return self.offsets[row-1] + col
    def handle_starttag(self, tag, attrs):
        if tag not in ('div','header','aside','main','nav'): return
        self.stack.append((tag,dict(attrs),self.position(),self.position()+len(self.get_starttag_text())))
    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag: return
        t,a,start,inner = self.stack.pop(); self.found.append((t,a,start,inner,self.position(),self.position()+len(tag)+3))

def transform(source, name, offline=False):
    # Existing transformed pages only need refreshed shared CSS and controls.
    if 'class="reader-header"' not in source:
        p=Elements(source);p.feed(source)
        header=next(e for e in p.found if e[0]=='header')
        main=next(e for e in p.found if e[0]=='main')
        book=BOOKS[name]
        edits=[]
        hero=next((e for e in p.found if e[0]=='div' and 'hero' in e[1].get('class','').split()),None)
        if hero:
            content=source[hero[3]:hero[4]]
            content=re.sub(r'<h1>(.*?)</h1>',r'<p class="lead">\1</p>',content,count=1,flags=re.S)
            marker=re.search(r'</(?:div|small)>',content)
            assert marker, name
            content=content[:marker.end()]+f'<h1>{book["name"]}</h1>'+content[marker.end():]
            edits.append((hero[2],hero[5],''))
        elif name=='nacos':
            content=source[header[3]:header[4]]
        elif name=='nginx':
            content='<p class="eyebrow">NETWORK / TRAFFIC</p><h1>NGINX</h1><p class="lead">沿一条HTTP请求，读懂事件驱动与流量治理。</p><p>从连接与事件循环，到代理、路由、缓存和限流，追踪真实调用链与失败边界。</p><div class="hero-meta"><span>NGINX1.28.0</span><span>24章机制分析</span><span>24幅图解</span><span>24段真实源码</span></div>'
        else:
            raise ValueError(f'{name}: reader layout needs an explicit adapter')
        if 'offline.zip' not in content and name not in ('jvm','nacos'):
            content+=f'<div class="links"><a href="./{name}-offline.zip" download>下载离线阅读包 ↓</a><a href="./handbook.md">Markdown手册</a></div>'
        home='https://yisiliang.github.io/' if offline else '../'
        replacement=f'<header class="reader-header"><div class="reader-wrap"><a class="home" href="{home}">← 源码学习库</a><div class="hero">{content}</div></div></header>'
        edits.append((header[2],header[5],replacement))
        # Move functional controls to the reading sidebar, preserving their IDs.
        if name!='nacos':
            aside=next(e for e in p.found if e[0]=='aside')
            old=source[header[3]:header[4]]
            search=next((e for e in p.found if e[0]=='div' and e[1].get('class')=='search'),None)
            button_source=old
            if search:button_source=button_source.replace(source[search[2]:search[5]],'')
            buttons=''.join(re.findall(r'<button\b[^>]*>.*?</button>',button_source,re.S))
            controls='<div class="reader-tools">'+buttons+'</div>'
            if search: controls+=source[search[2]:search[5]]
            if 'id="progress"' in old:controls+='<div id="progress"></div>'
            edits.append((aside[3],aside[3],controls))
        else:
            nav=next(e for e in p.found if e[0]=='nav')
            edits.append((nav[2],nav[2],'<aside>'))
            edits.append((nav[5],nav[5],'</aside>'))
        layout=next((e for e in p.found if e[0]=='div' and e[1].get('class')=='layout'),None)
        if layout:
            edits.append((layout[2],layout[3],'<div class="reader-layout reader-wrap">'))
        else:
            aside=next(e for e in p.found if e[0]=='aside')
            edits.append((aside[2],aside[2],'<div class="reader-layout reader-wrap">'))
            edits.append((main[5],main[5],'</div>'))
        if 'id' not in main[1]:
            edits.append((main[2],main[3],'<main id="reader-content">'))
        for start,end,value in sorted(edits,reverse=True):source=source[:start]+value+source[end:]
        source=source.replace('<body>','<body class="reader-page"><a class="reader-skip" href="#reader-content">跳至正文</a>',1)
    source=source.replace('<body class="reader-page">',f'<body class="reader-page" data-reader="{name}">',1)
    if 'id="theme"' not in source:
        source=source.replace('<aside>','<aside><div class="reader-tools"><button id="menu" aria-label="展开目录">展开目录</button><button id="theme" aria-label="切换明暗主题">浅色阅读</button></div>',1)
    source=re.sub(r'<style id="reader-design">.*?</style>','',source,flags=re.S)
    source=re.sub(r'<script id="reader-controls">.*?</script>','',source,flags=re.S)
    source=source.replace('</head>',f'<style id="reader-design">{CSS}</style></head>',1)
    source=source.replace('</body>',f'<script id="reader-controls">{JS}</script></body>',1)
    if offline:
        source=re.sub(r'<a\b[^>]*href="(?:\./)?'+re.escape(name)+r'-offline\.zip"[^>]*>.*?</a>','',source,flags=re.S)
    return source

def main():
    for name in BOOKS:
        folder=ROOT/'docs'/name
        for page in [folder/'index.html',folder/'offline.html',folder/'offline-index.html']:
            if page.exists():
                old=page.read_text();new=transform(old,name,page.name!='index.html')
                if old!=new:page.write_text(new)
        for archive in folder.glob('*offline*.zip'):
            with zipfile.ZipFile(archive) as z:
                entries=[(i,z.read(i.filename)) for i in z.infolist()]
            changed=False; rebuilt=[]
            for info,data in entries:
                if info.filename.endswith('.html'):
                    new=transform(data.decode(),name,True).encode();changed |= new!=data;data=new
                rebuilt.append((info,data))
            if changed:
                with zipfile.ZipFile(archive,'w') as z:
                    for info,data in rebuilt:z.writestr(info,data)
        print(f'{name}: public and available offline readers styled')

if __name__=='__main__':main()

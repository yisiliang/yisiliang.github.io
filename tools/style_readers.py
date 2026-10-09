#!/usr/bin/env python3
"""Unify catalog readers with the technical-topic layout, preserving raw source/SVG.

Run after a book generator. HTML adapters preserve old anchors, downloadable
resources and byte-exact code. Shared CSS/JS are inlined for existing offline ZIPs.
"""
from html.parser import HTMLParser
from pathlib import Path
import html,json,re,zipfile
from reader.learning_words import html_wording
ROOT=Path(__file__).resolve().parents[1]
CSS=(ROOT/'tools/reader/theme.css').read_text()+(ROOT/'tools/reader/style.css').read_text()
JS=(ROOT/'tools/reader/controls.js').read_text()
THEME=(ROOT/'tools/reader/theme.js').read_text()
BOOKS={b['path']:b for c in json.loads((ROOT/'tools/homepage/catalog.json').read_text()) for b in c['books']}
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

def esc(value):return html.escape(str(value),quote=True)
def text(value):return html.unescape(re.sub('<[^>]+>','',value)).strip()

class Elements(HTMLParser):
    def __init__(self,source):
        super().__init__(convert_charrefs=False)
        self.source=source;self.offsets=[0]
        for line in source.splitlines(keepends=True):self.offsets.append(self.offsets[-1]+len(line))
        self.stack=[];self.nodes=[]
    def position(self):
        row,col=self.getpos();return self.offsets[row-1]+col
    def handle_starttag(self,tag,attrs):
        start=self.position();node={'tag':tag,'attrs':dict(attrs),'start':start,'inner':start+len(self.get_starttag_text()),'parent':self.stack[-1] if self.stack else None,'children':[]}
        if self.stack:self.stack[-1]['children'].append(node)
        self.nodes.append(node)
        if tag in VOID:node.update(close=node['inner'],end=node['inner'])
        else:self.stack.append(node)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:
            node=self.stack.pop();node.update(close=node['inner'],end=node['inner'])
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]['tag']==tag:
                node=self.stack[i];node.update(close=self.position(),end=self.position()+len(tag)+3);del self.stack[i:];return


def refresh(source,offline):
    if 'id="diagram-dialog"' not in source:
        source=source.replace('</body>','<dialog id="diagram-dialog" aria-label="图解放大"><div id="diagram-actions"><button id="zoom-in" type="button">放大</button><button id="zoom-out" type="button">缩小</button><button id="zoom-reset" type="button">重置</button><button id="diagram-close" type="button">关闭</button></div><div id="diagram-content"></div></dialog></body>',1)
    elif 'id="zoom-in"' not in source:
        source=source.replace('<button id="diagram-close" type="button">关闭</button>','<div id="diagram-actions"><button id="zoom-in" type="button">放大</button><button id="zoom-out" type="button">缩小</button><button id="zoom-reset" type="button">重置</button><button id="diagram-close" type="button">关闭</button></div>',1)
    # The reference originally had no viewer; controls must run after its markup.
    viewer=re.search(r'<dialog id="diagram-dialog".*?</dialog>',source,re.S)
    if viewer and '<script id="reader-controls">' in source:
        fragment=viewer.group();source=source[:viewer.start()]+source[viewer.end():]
        source=source.replace('<script id="reader-controls">',fragment+'<script id="reader-controls">',1)
    for label,tag,content in [('reader-design','style',CSS),('reader-theme','script',THEME),('reader-controls','script',JS)]:
        pattern=rf'<{tag} id="{label}">.*?</{tag}>'
        fragment=f'<{tag} id="{label}">{content}</{tag}>'
        if re.search(pattern,source,re.S):source=re.sub(pattern,lambda _:fragment,source,flags=re.S)
        else:source=source.replace('</head>' if tag=='style' or label=='reader-theme' else '</body>',fragment+('</head>' if tag=='style' or label=='reader-theme' else '</body>'),1)
    source=html_wording(source)
    source=re.sub(r'(<div class="reader-downloads">)(.*?)(</div>)',lambda m:m[1]+m[2].replace(' · ','')+m[3],source,flags=re.S)
    if offline:
        source=re.sub(r'<script\b[^>]*src="https://cloud\.umami\.is/script\.js"[^>]*></script>','',source)
        source=source.replace('href="../"','href="https://yisiliang.github.io/"')
        source=re.sub(r'href="\.\./([a-z][a-z-]*)/([^" ]*)"',r'href="https://yisiliang.github.io/\1/\2"',source)
        source=re.sub(r'<a\b[^>]*href="[^" ]*offline[^" ]*\.zip"[^>]*>.*?</a>','',source,flags=re.S)
    return source


def transform(source,name,offline=False):
    if 'data-layout="learning-v2"' in source:return refresh(source,offline)
    book=BOOKS[name]
    if name=='java-architect-interview':
        # The chosen reference already has chapter, search, progress and drawer markup.
        source=re.sub(r'<link\b[^>]*href="\./style.css[^" ]*"[^>]*>','',source)
        source=re.sub(r'<script\b[^>]*src="\./(?:app|theme).js[^" ]*"[^>]*></script>','',source)
        source=source.replace('<body>','<body class="learning-reader" data-layout="learning-v2" data-reader="java-architect-interview">',1)
        source=source.replace('<div class="brand">','<div class="brand"><a class="library-home" href="../">← 学习库</a>',1)
        return refresh(source,offline)
    parser=Elements(source);parser.feed(source)
    nodes=parser.nodes
    main=next(n for n in nodes if n['tag']=='main')
    head=next(n for n in nodes if n['tag']=='head')
    header=next(n for n in nodes if n['tag']=='header')
    # Existing long readers wrap their content in one plain article.
    root=next((n for n in main['children'] if n['tag']=='article'),main)
    children=root['children']
    flat=[n for n in nodes if n['tag'] in ('a','h1','h2') and re.fullmatch(r'chapter-\d+',n['attrs'].get('id','')) and (n['parent'] is root or (n['parent']['tag']=='p' and n['parent']['parent'] is root))]
    chapters=[]
    if flat:
        boundaries=[(n['parent']['start'] if n['parent']['tag']=='p' else n['start'],n) for n in flat]
        for n in children:
            if n['tag']=='section' and any(x['attrs'].get('id','').startswith('appendix-') for x in n['children']):
                start=n['start'];marker=source.rfind('<!--',root['inner'],start)
                if marker>=0 and source[marker:start].strip().endswith('-->'):start=marker
                boundaries.append((start,n))
        boundaries.sort(key=lambda pair:pair[0])
        preface=source[root['inner']:boundaries[0][0]]
        for i,(start,node) in enumerate(boundaries):
            end=boundaries[i+1][0] if i+1<len(boundaries) else root['close']
            heading=next(n for n in nodes if n['tag'] in ('h1','h2') and start<=n['start']<end)
            title=text(source[heading['inner']:heading['close']])
            identifier=f'reading-{i:03d}'
            if node['tag']=='section':
                title_html=source[heading['start']:heading['end']]
                study=source[start:heading['start']]+source[heading['end']:end]
            else:
                title_html=source[start:heading['end']]
                study=source[heading['end']:end]
            chapters.append((identifier,title,title_html,study))
    else:
        sections=[n for n in children if n['tag']=='section' and ('chapter' in n['attrs'].get('class','').split() or n['attrs'].get('id','').startswith('chapter-') or name in ('distributed','transformer'))]
        if not sections:raise ValueError(f'{name}: no chapter adapter')
        preface=source[root['inner']:sections[0]['start']]
        for i,node in enumerate(sections,1):
            heading=next(n for n in nodes if n['tag'] in ('h1','h2') and node['inner']<=n['start']<node['close'])
            title=text(source[heading['inner']:heading['close']])
            identifier=f'reading-{i:03d}'
            # Keep the original section and IDs inside study; only its duplicate heading moves.
            opening=source[node['start']:node['inner']]
            opening=re.sub(r'class="([^"]*)"',lambda m:'class="'+re.sub(r'\bchapter\b','original-chapter',m[1])+'"',opening)
            study=opening+source[node['inner']:heading['start']]+source[heading['end']:node['end']]
            chapters.append((identifier,title,source[heading['start']:heading['end']],study))
        # Trailing main-level material belongs to the final chapter.
        chapters[-1]=(*chapters[-1][:3],chapters[-1][3]+source[sections[-1]['end']:root['close']])
    # Preserve old footers and downloads; discard obsolete controls and handlers.
    footer=next((n for n in nodes if n['tag']=='footer'),None)
    footer_html=source[footer['start']:footer['end']] if footer else ''
    downloads=[]
    for n in nodes:
        if n['tag']=='a' and header['start']<n['start']<header['end'] and not n['attrs'].get('href','').startswith(('#','../','https://yisiliang.github.io/')):
            downloads.append(source[n['start']:n['end']])
    hero=next((n for n in nodes if n['tag']=='div' and 'hero' in n['attrs'].get('class','').split() and header['start']<n['start']<header['end']),header)
    lead=next((n for n in nodes if n['tag']=='p' and 'lead' in n['attrs'].get('class','').split() and hero['start']<n['start']<hero['end']),None)
    introduction=source[lead['inner']:lead['close']] if lead else book.get('detail','')
    intro=f'<section class="intro"><h1>{esc(book["name"])}学习手册</h1><p>{introduction}</p><div class="reader-downloads">'+ ''.join(downloads)+'</div>'
    if preface.strip():intro+=f'<details class="reader-preface"><summary>版本、来源与学习路线</summary>{preface}</details>'
    intro+='</section>'
    nav=[];articles=[]
    for i,(identifier,title,title_html,study) in enumerate(chapters,1):
        p=Elements(study);p.feed(study)
        sub=[]
        for h in p.nodes:
            if h['tag']=='h2' and h['attrs'].get('id'):
                sub.append(f'<a href="#{esc(h["attrs"]["id"])}">{source_title(study,h)}</a>')
        nav.append(f'<details class="chapter-nav" data-chapter="{identifier}"><summary><a href="#{identifier}"><span>{i:02d}</span>{esc(title)}</a></summary><div>'+''.join(sub)+'</div></details>')
        articles.append(f'<article class="chapter" id="{identifier}" data-title="{esc(title)}"><div class="chapter-title"><p class="eyebrow">章节{i:02d} / 完整阅读</p>{title_html}</div><div class="study">{study}</div></article>')
    # Retain each book's original code-card styles; new reader rules follow them.
    head_html=source[:head['close']]
    head_html=re.sub(r'<style id="reader-design">.*?</style>','',head_html,flags=re.S)
    head_html=re.sub(r'<script(?![^>]*cloud\.umami)[^>]*>.*?</script>','',head_html,flags=re.S)
    attention='<script defer src="./attention.js"></script>' if name=='transformer' else ''
    page=head_html+attention+'</head><body class="learning-reader" data-layout="learning-v2" data-reader="'+name+'">'
    page+='<a class="skip" href="#main">跳到正文</a><header class="topbar"><button id="menu" class="mobile" aria-label="打开章节导航" aria-expanded="false" aria-controls="left-nav">目录</button><div class="brand"><a class="library-home" href="../">← 学习库</a>'+esc(book['name'])+'学习手册<span>'+esc(book['version'])+'</span></div><div class="tools"><button id="search-open" aria-label="打开全文搜索">搜索 <kbd>/</kbd></button><button id="print" type="button">打印</button><button id="theme" aria-label="切换主题">主题：系统</button></div></header><div class="progress-track" aria-hidden="true"><div id="progress-bar"></div></div><div id="drawer-backdrop" hidden></div>'
    alias=f'<span id="{esc(main["attrs"]["id"])}"></span>' if main['attrs'].get('id') and main['attrs']['id']!='main' else ''
    page+='<div class="layout"><nav id="left-nav" aria-label="章节目录"><p class="nav-label">学习目录 / '+str(len(chapters))+'章</p>'+''.join(nav)+'</nav><main id="main" tabindex="-1">'+alias+intro+''.join(articles)+'</main><aside id="right-toc" aria-label="当前章节目录"><div class="reading"><span id="progress-text">阅读进度0%</span><span id="current-label"></span></div><p class="nav-label">本篇目录</p><nav id="toc"></nav></aside></div>'
    page+='<dialog id="search-dialog" aria-labelledby="search-title"><div class="search-head"><h2 id="search-title">全文搜索</h2><button id="search-close" aria-label="关闭搜索">关闭</button></div><label for="search-input">搜索关键词、源码方法或原理问题</label><input id="search-input" type="search" placeholder="输入关键词，搜索完整正文" autocomplete="off"><p id="search-status" role="status" aria-live="polite">输入关键词，搜索完整正文。</p><div id="search-results"></div></dialog><div id="toast" role="status" aria-live="polite"></div><dialog id="diagram-dialog" aria-label="图解放大"><button id="diagram-close" type="button">关闭</button><div id="diagram-content"></div></dialog>'+footer_html+'</body></html>'
    return refresh(page,offline)

def source_title(source,node):return esc(text(source[node['inner']:node['close']]))

def main():
    for name in BOOKS:
        folder=ROOT/'docs'/name
        for page in [folder/'index.html',folder/'offline.html',folder/'offline-index.html']:
            if page.exists():
                old=page.read_text();new=transform(old,name,page.name!='index.html')
                if new!=old:page.write_text(new)
        for archive in folder.glob('*offline*.zip'):
            with zipfile.ZipFile(archive) as z:entries=[(info,z.read(info.filename)) for info in z.infolist()]
            index=next(info.filename for info,data in entries if info.filename.endswith('index.html'))
            rebuilt=[];changed=False
            for info,data in entries:
                if info.filename.endswith('.html'):
                    new=transform(data.decode(),name,True).encode();changed|=new!=data;data=new
                elif not info.is_dir():
                    local=folder/Path(info.filename).relative_to(Path(index).parent)
                    if local.is_file():
                        new=local.read_bytes();changed|=new!=data;data=new
                rebuilt.append((info,data))
            if changed:
                with zipfile.ZipFile(archive,'w') as z:
                    for info,data in rebuilt:z.writestr(info,data)
        print(name+': learning layout applied to public and existing offline pages')
    # The reference keeps its local assets usable for standalone generation.
    folder=ROOT/'docs/java-architect-interview'
    for file,content in [('style.css',CSS),('app.js',JS),('theme.js',THEME)]:
        (folder/file).write_text(content)

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Build this article with the shared reader; do not rewrite other readers."""
from pathlib import Path
import html
import re
import sys
import zipfile
import markdown
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from style_readers import refresh


def build():
    source = (HERE / 'article.md').read_text()
    for name, caption in [
        ('address', '同一个下标 4：正确读取 chars[4..7]，旧 C2 的错误缩放读到 chars[16..19]。'),
        ('patch', '补丁在指令匹配时拒绝访问宽度与缩放量不一致的组合。'),
    ]:
        figure = f'<figure class="diagram"><img src="./diagrams/{name}.svg" width="860" height="420" alt="{html.escape(caption)}"><figcaption>{caption}</figcaption></figure>'
        source = source.replace(f'<!-- diagram:{name} -->', figure)
    body = BeautifulSoup(markdown.markdown(source, extensions=['fenced_code', 'tables', 'attr_list']), 'html.parser')
    title = body.h1.get_text()
    body.h1.decompose()
    headings = list(body.find_all('h2', recursive=False))
    nav, chapters = [], []
    for i, heading in enumerate(headings, 1):
        anchor, text = heading['id'], heading.get_text()
        nodes = []
        for node in list(heading.next_siblings):
            if getattr(node, 'name', None) == 'h2':
                break
            nodes.append(node)
        content = BeautifulSoup(''.join(str(n) for n in nodes), 'html.parser')
        for j, sub in enumerate(content.select('h3'), 1):
            sub['id'] = f'{anchor}-s{j}'
        nav_title = re.sub(r'^\d+\.\s*', '', text)
        nav.append(f'<div class="chapter-nav primary-nav" data-chapter="{anchor}"><a href="#{anchor}"><span>{i:02d}</span>{html.escape(nav_title)}</a></div>')
        chapters.append(f'<article class="chapter" id="{anchor}" data-title="{html.escape(text, quote=True)}"><div class="chapter-title"><p class="eyebrow">排查记录 / {i:02d}</p><h2 id="{anchor}-heading">{html.escape(text)}</h2></div><div class="study">{content}</div></article>')
    preface = []
    for node in list(body.children):
        if getattr(node, 'name', None) == 'h2':
            break
        preface.append(str(node))
    esc = html.escape
    downloads = '<a href="./article.md" download>Markdown 原文</a><a href="./fastjson2-arm-jit-evidence.zip" download>复现与证据包</a>'
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="从 Fastjson2 2.0.61 的 ARM64 随机解析异常，定位到 OpenJDK C2 地址缩放缺陷 JDK-8267689，并用 8u292 / 8u302 验证修复边界。"><title>{esc(title)} | YiSiliang</title><script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script></head>
<body class="learning-reader" data-layout="learning-v2" data-reader="fastjson2-arm-jit" data-toc-scope="document">
<a class="skip" href="#main">跳到正文</a>
<header class="topbar"><button id="menu" class="mobile" aria-label="打开章节导航" aria-expanded="false" aria-controls="left-nav">目录</button><div class="brand"><a class="library-home" href="../">← 学习库</a>Fastjson2 与 ARM64 JIT<span>C2 编译缺陷排查 · 2026-10-27</span></div><div class="tools"><button id="search-open" aria-label="打开全文搜索">搜索 <kbd>/</kbd></button><button id="print" type="button">打印</button><button id="theme" aria-label="切换主题">主题：系统</button></div></header>
<div class="progress-track" aria-hidden="true"><div id="progress-bar"></div></div><div id="drawer-backdrop" hidden></div>
<div class="layout"><nav id="left-nav" aria-label="一级目录"><p class="nav-label">一级目录 / {len(headings)} 节</p>{''.join(nav)}</nav><main id="main" tabindex="-1"><section class="intro"><p class="eyebrow">JAVA / ARM64 / SOURCE INVESTIGATION</p><h1>{esc(title)}</h1>{''.join(preface)}<div class="reader-downloads">{downloads}</div></section>{''.join(chapters)}</main><aside id="right-toc" aria-label="全文一二级目录"><div class="reading"><span id="progress-text">阅读进度 0%</span><span id="current-label"></span></div><p class="nav-label">全文目录 / 一级与二级</p><nav id="toc"></nav></aside></div>
<dialog id="search-dialog" aria-labelledby="search-title"><div class="search-head"><h2 id="search-title">搜索这篇复盘</h2><button id="search-close" aria-label="关闭搜索">关闭</button></div><label for="search-input">搜索现象、方法名或补丁编号</label><input id="search-input" type="search" placeholder="例如 getLongLE、8u302、C2" autocomplete="off"><p id="search-status" role="status" aria-live="polite">输入关键词，搜索完整正文。</p><div id="search-results"></div></dialog><div id="toast" role="status" aria-live="polite"></div>
<footer>YiSiliang · 源码之下，系统之上 · 2026-10-27</footer></body></html>'''
    page = refresh(page, False)
    page = page.replace('</head>', '<style>figure.diagram img{display:block;width:100%;height:auto}.intro>p{max-width:none;margin:.8em 0}.intro h1{font-size:30px;line-height:1.4}.study>p,.study li{overflow-wrap:anywhere}.primary-nav>a{display:flex;gap:10px;padding:10px 0;color:var(--muted);font-size:12px;line-height:1.7}.primary-nav>a>span{font-size:11px;min-width:19px}.primary-nav.current>a{color:var(--accent);font-weight:600}@media(max-width:760px){.intro h1{font-size:26px}}</style></head>')
    (HERE / 'index.html').write_text(page)
    # Deterministic evidence bundle. Include only curated, reviewed experiment files.
    with zipfile.ZipFile(HERE / 'fastjson2-arm-jit-evidence.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted((HERE / 'evidence').rglob('*')):
            if p.is_file():
                info = zipfile.ZipInfo(str(p.relative_to(HERE / 'evidence')), date_time=(2026, 10, 27, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())
    print(f'Built {len(headings)} sections and evidence ZIP')


if __name__ == '__main__':
    build()

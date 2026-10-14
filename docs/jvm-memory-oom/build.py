#!/usr/bin/env python3
"""Build the public JVM memory and OOM technical topic page and offline bundle."""
from pathlib import Path
import re
import zipfile

import markdown
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def build():
    source = (ROOT / 'article.md').read_text()
    source = re.sub(r'(?ms)^## 目录\s*\n.*?(?=^# 1\.)', '', source)
    title_match = re.match(r'(?m)^# (.+)$', source)
    title = title_match.group(1).strip()
    source = source[title_match.end():].lstrip()
    starts = list(re.finditer(r'(?m)^# (\d+)\. (.+)$', source))
    if len(starts) != 10:
        raise ValueError(f'Expected 10 main sections, found {len(starts)}')
    preface_md = source[:starts[0].start()].strip()
    preface = markdown.markdown(preface_md, extensions=['tables', 'fenced_code'])
    chapters = []
    nav = []
    for pos, match in enumerate(starts):
        number, heading = match.group(1), match.group(2).strip()
        end = starts[pos + 1].start() if pos + 1 < len(starts) else len(source)
        body = source[match.end():end].lstrip()
        body_html = markdown.markdown(body, extensions=['tables', 'fenced_code', 'toc'])
        soup = BeautifulSoup(body_html, 'html.parser')
        for heading_node in soup.select('h2[id], h3[id]'):
            heading_node['id'] = f'chapter-{number}-{heading_node["id"]}'
        for heading_node in soup.select('h2, h3'):
            heading_node['tabindex'] = '-1'
        for image_paragraph in list(soup.find_all('p')):
            if image_paragraph.find('img') and len(image_paragraph.contents) == 1:
                figure = soup.new_tag('figure', attrs={'class': 'diagram'})
                image_paragraph.wrap(figure)
                image_paragraph.unwrap()
        chapter_id = f'chapter-{number}'
        title_id = f'{chapter_id}-title'
        chapter = (f'<article class="chapter" id="{chapter_id}" data-title="{heading}">'
                   f'<div class="chapter-title"><p class="eyebrow">第{int(number):02d}节 / 完整阅读</p>'
                   f'<h1 id="{title_id}">{heading}</h1></div><div class="study">{soup}</div></article>')
        chapters.append(chapter)
        links = []
        for h in soup.select('h2, h3'):
            label = h.get_text(' ', strip=True)
            depth = ' class="sub-subtopic"' if h.name == 'h3' else ''
            links.append(f'<a{depth} href="#{h.get("id")}">{label}</a>')
        nav.append(f'<details class="chapter-nav" data-chapter="{chapter_id}"><summary><a href="#{chapter_id}">'
                   f'<span>{int(number):02d}</span>{heading}</a></summary><div>{"".join(links)}</div></details>')

    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="从JVM内存结构、GC与常见OOM类型出发，梳理生产环境诊断、Heap Dump、Native内存、容器预算和故障案例。"><title>{title} | 技术专题</title><style>{(REPO / 'tools/reader/style.css').read_text()}</style><script>{(REPO / 'tools/reader/theme.js').read_text()}</script></head><body class="learning-reader" data-layout="learning-v2" data-reader="jvm-memory-oom">
<a class="skip" href="#main">跳到正文</a><header class="topbar"><button id="menu" class="mobile" aria-label="打开章节导航" aria-expanded="false" aria-controls="left-nav">目录</button><div class="brand"><a class="library-home" href="../">← 学习库</a>技术专题<span>HotSpot JDK8 · JVM内存与故障排查</span></div><div class="tools"><button id="search-open" aria-label="打开全文搜索">搜索 <kbd>/</kbd></button><button id="theme" aria-label="切换主题">主题：系统</button></div></header><div class="progress-track" aria-hidden="true"><div id="progress-bar"></div></div><div id="drawer-backdrop" hidden></div>
<div class="layout"><nav id="left-nav" aria-label="章节目录"><p class="nav-label">技术专题 / 10节</p>{''.join(nav)}</nav><main id="main" tabindex="-1"><section class="intro"><p class="eyebrow">TECHNICAL DEEP DIVE</p><h1>{title}</h1>{preface}<div class="meta"><span>HotSpot JDK8为主</span><span>10节实战分析</span><span>23张SVG图解</span><span>含命令与应急清单</span></div><div class="reader-downloads"><a href="./article.md" download>Markdown原文</a><a href="./jvm-memory-oom-offline.zip" download>离线阅读包</a></div></section>{''.join(chapters)}</main><aside id="right-toc" aria-label="当前章节目录"><div class="reading"><span id="progress-text">阅读进度0%</span><span id="current-label"></span></div><p class="nav-label">本节目录</p><nav id="toc"></nav></aside></div>
<dialog id="search-dialog" aria-labelledby="search-title"><div class="search-head"><h2 id="search-title">全文搜索</h2><button id="search-close" aria-label="关闭搜索">关闭</button></div><label for="search-input">搜索关键词或命令</label><input id="search-input" type="search" placeholder="输入关键词，搜索完整正文" autocomplete="off"><p id="search-status" role="status" aria-live="polite">输入关键词，搜索完整正文。</p><div id="search-results"></div></dialog><div id="toast" role="status" aria-live="polite"></div><dialog id="diagram-dialog" aria-label="图解放大"><div id="diagram-actions"><button id="zoom-in" type="button">放大</button><button id="zoom-out" type="button">缩小</button><button id="zoom-reset" type="button">重置</button><button id="diagram-close" type="button">关闭</button></div><div id="diagram-content"></div></dialog><script>{(REPO / 'tools/reader/controls.js').read_text()}</script></body></html>'''
    (ROOT / 'index.html').write_text(page)
    with zipfile.ZipFile(ROOT / 'jvm-memory-oom-offline.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in [ROOT / 'index.html', ROOT / 'article.md'] + sorted((ROOT / 'diagrams').glob('*.svg')):
            archive.write(path, path.relative_to(ROOT.parent))
    print(f'Built {len(chapters)} sections, {len(list((ROOT / "diagrams").glob("*.svg")))} SVG diagrams and offline ZIP')


if __name__ == '__main__':
    build()

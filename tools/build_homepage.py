#!/usr/bin/env python3
"""Build the static source library homepage from a small, reviewable catalog."""
from pathlib import Path
import html,json
ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'tools/homepage/catalog.json'
esc=lambda value:html.escape(str(value),quote=True)
def build():
    groups=json.loads(CATALOG.read_text())
    total=sum(len(g['books']) for g in groups)
    articles=[]
    for i,g in enumerate(groups,1):
        books=[]
        for b in g['books']:
            if not (ROOT/'docs'/b['path']/'index.html').is_file():
                raise ValueError('Published handbook missing: '+b['path'])
            books.append(f'<a class="book" href="./{esc(b["path"])}/"><div class="book-title"><strong>{esc(b["name"])}</strong><span class="arrow" aria-hidden="true">↗</span></div><span class="version">{esc(b["version"])}</span><span class="detail">{esc(b["detail"])}</span></a>')
        future=''
        if not books:
            future=f'<div class="future"><span class="future-label">后续学习方向</span><p>{esc(" / ".join(g["future"]))}</p><span class="unpublished">教程尚未发布</span></div>'
        articles.append(f'<article class="category" data-published="{str(bool(books)).lower()}"><div class="category-top"><span class="index">{i:02d}</span><span class="category-en">{esc(g["en"])}</span></div><h3>{esc(g["title"])}</h3><p class="description">{esc(g["description"])}</p><div class="books {"single" if len(books)==1 else ""}">{"".join(books)}</div>{future}</article>')
    github='https://github.com/yisiliang/yisiliang.github.io'
    page=f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><meta name="description" content="从源码出发，理解系统。JDK、JVM、框架、数据库、缓存与消息、网络及分布式系统的源码学习手册。"><title>源码之下，系统之上 | YiSiliang</title><link rel="stylesheet" href="./assets/homepage/style.css"><script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script></head><body>
<a class="skip-link" href="#library">跳至源码手册</a>
<header class="header"><div class="wrap nav"><a class="brand" href="./">YiSiliang<span> / SOURCE NOTES</span></a><nav aria-label="主导航"><a class="nav-active" href="#library">源码手册</a><a href="#categories">技术分类</a><a class="github" href="{github}" target="_blank" rel="noreferrer"><img src="./assets/homepage/github.svg" alt="">GitHub</a></nav></div></header>
<main class="wrap"><section class="hero"><div><p class="eyebrow">READ THE SOURCE. UNDERSTAND THE SYSTEM.</p><h1>源码之下，<br><span>系统之上。</span></h1></div><div class="hero-note"><p class="eyebrow">从实现，走向原理</p><p>循着真实源码，理解框架与中间件。<br>把字段、流程与边界，串成系统的全貌。</p><a href="#library">开始阅读<span aria-hidden="true"> ↗</span></a></div></section>
<section id="library" class="library"><div class="section-head"><div><p class="eyebrow">THE SOURCE LIBRARY</p><h2>源码阅读手册</h2><p class="intro">六个技术领域，一条从源码到架构的学习路径。</p></div><div class="switch" aria-label="手册显示范围"><button aria-pressed="true" class="selected" data-filter="all">全部领域 <span>{len(groups)}</span></button><button aria-pressed="false" data-filter="published">已发布手册 <span>{total}</span></button></div></div><div id="categories" class="categories">{"".join(articles)}</div><p class="library-note">已发布手册包含图解与机制分析，支持离线阅读。源码教程均标注固定版本。</p></section></main>
<footer><div class="wrap footer-inner"><span>YiSiliang <span class="dot">·</span> 源码阅读笔记</span><span>从源码出发，理解系统。</span><a href="{github}" target="_blank" rel="noreferrer">GitHub ↗</a></div></footer>
<script>
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{{document.querySelectorAll('[data-filter]').forEach(b=>{{const selected=b===button;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));}});document.querySelectorAll('.category').forEach(c=>{{c.hidden=button.dataset.filter==='published'&&c.dataset.published!=='true';}});}}));
</script></body></html>'''
    (ROOT/'docs/assets/homepage/style.css').write_text((ROOT/'tools/homepage/style.css').read_text())
    (ROOT/'docs/index.html').write_text(page)
    print(f'Built homepage: {len(groups)} categories, {total} published handbooks')
if __name__=='__main__':build()

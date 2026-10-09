#!/usr/bin/env python3
"""Build the static source library homepage from a small, reviewable catalog."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,html,json
ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'tools/homepage/catalog.json'
esc=lambda value:html.escape(str(value),quote=True)
class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
    def handle_starttag(self,tag,attrs):
        anchor=dict(attrs).get('id')
        if anchor:self.ids.add(anchor)

def build():
    groups=json.loads(CATALOG.read_text())
    style=(ROOT/'tools/reader/theme.css').read_text()+(ROOT/'tools/homepage/style.css').read_text()
    theme=(ROOT/'tools/reader/theme.js').read_text()
    theme_version=hashlib.sha256(theme.encode()).hexdigest()[:12]
    style_version=hashlib.sha256(style.encode()).hexdigest()[:12]
    total=sum(len(g['books']) for g in groups)
    domains=sum(g.get('layout')!='topics' for g in groups)
    topic_count=sum(len(b.get('topics',[])) for g in groups for b in g['books'])
    articles=[]
    for i,g in enumerate(groups,1):
        books=[]
        topics=[]
        for b in g['books']:
            if not (ROOT/'docs'/b['path']/'index.html').is_file():
                raise ValueError('Published handbook missing: '+b['path'])
            books.append(f'<a class="book" href="./{esc(b["path"])}/"><div class="book-title"><strong>{esc(b["name"])}</strong><span class="arrow" aria-hidden="true">↗</span></div><span class="version">{esc(b["version"])}</span><span class="detail">{esc(b["detail"])}</span></a>')
            if b.get('topics'):
                page_anchors=Anchors()
                page_anchors.feed((ROOT/'docs'/b['path']/'index.html').read_text())
                for n,topic in enumerate(b['topics'],len(topics)+1):
                    if topic['anchor'] not in page_anchors.ids:
                        raise ValueError('Topic anchor missing: '+b['path']+'#'+topic['anchor'])
                    topics.append(f'<li><a href="./{esc(b["path"])}/#{esc(topic["anchor"])}"><span class="topic-number" aria-hidden="true">{n:02d}</span><span>{esc(topic["title"])}</span><span class="arrow" aria-hidden="true">↗</span></a></li>')
        future=''
        if not books:
            future=f'<div class="future"><span class="future-label">后续学习方向</span><p>{esc(" / ".join(g["future"]))}</p><span class="unpublished">教程尚未发布</span></div>'
        content=f'<div class="books {"single" if len(books)==1 else ""}">{"".join(books)}</div>{future}'
        featured=g.get('layout')=='topics'
        if featured:
            content=f'<ol class="topic-links" aria-label="专题直达">{"".join(topics)}</ol>'
        articles.append(f'<article id="{esc(g["id"])}" class="category{" category-topics" if featured else ""}" data-published="{str(bool(books)).lower()}"><div class="category-top"><span class="index">{i:02d}</span><span class="category-en">{esc(g["en"])}</span></div><h3>{esc(g["title"])}</h3><p class="description">{esc(g["description"])}</p>{content}</article>')
    github='https://github.com/yisiliang/yisiliang.github.io'
    page=f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="从源码出发，理解系统。{domains}大技术领域的源码手册与AI论文解读，以及Java核心技术、Nginx流量治理与架构实践的{topic_count}个技术专题。"><title>源码之下，系统之上 | YiSiliang</title><link rel="stylesheet" href="./assets/homepage/style.css?v={style_version}"><script src="./assets/homepage/theme.js?v={theme_version}"></script><script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script></head><body>
<a class="skip-link" href="#library">跳至学习手册</a>
<header class="header"><div class="wrap nav"><a class="brand" href="./">YiSiliang<span> / SOURCE NOTES</span></a><nav aria-label="主导航"><a class="nav-active" href="#library">学习手册</a><a href="#categories">技术分类</a><a href="#topics">技术专题</a><a class="github" href="{github}" target="_blank" rel="noreferrer"><img src="./assets/homepage/github.svg" alt="">GitHub</a></nav><button id="theme" class="header-theme" type="button" aria-label="切换主题">主题：系统</button></div></header>
<main class="wrap"><section class="hero"><div><p class="eyebrow">READ THE SOURCE. UNDERSTAND THE SYSTEM.</p><h1>源码之下，<br><span>系统之上。</span></h1></div><div class="hero-note"><p class="eyebrow">从实现，走向原理</p><p>循着真实源码，理解框架与中间件。<br>把字段、流程与边界，串成系统的全貌。</p><a href="#library">开始阅读<span aria-hidden="true"> ↗</span></a></div></section>
<section id="library" class="library"><div class="section-head"><div><p class="eyebrow">THE SOURCE LIBRARY</p><h2>技术学习手册</h2><p class="intro">{domains}大技术领域与{topic_count}个技术专题，从源码机制到架构实践。</p></div><div class="switch" aria-label="手册显示范围"><button aria-pressed="true" class="selected" data-filter="all">全部分类 <span>{len(groups)}</span></button><button aria-pressed="false" data-filter="published">已发布手册 <span>{total}</span></button></div></div><div id="categories" class="categories">{"".join(articles)}</div><p class="library-note">学习资料包含图解与机制分析，提供离线包的手册可下载阅读。源码教程标注固定版本，专题与理论文章标注参考依据。</p></section></main>
<footer><div class="wrap footer-inner"><span>YiSiliang <span class="dot">·</span> 源码阅读笔记</span><span>从源码出发，理解系统。</span><a href="{github}" target="_blank" rel="noreferrer">GitHub ↗</a></div></footer>
<script>
const themeNames={{system:'系统',light:'浅色',dark:'深色'}};
function themeLabel(){{const label=themeNames[window.learningTheme.get()];const button=document.getElementById('theme');button.textContent='主题：'+label;button.setAttribute('aria-label','当前主题'+label+'，点击切换');}}
themeLabel();document.getElementById('theme').addEventListener('click',()=>window.learningTheme.cycle());window.addEventListener('learning-theme-change',themeLabel);
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{{document.querySelectorAll('[data-filter]').forEach(b=>{{const selected=b===button;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));}});document.querySelectorAll('.category').forEach(c=>{{c.hidden=button.dataset.filter==='published'&&c.dataset.published!=='true';}});}}));
</script></body></html>'''
    (ROOT/'docs/assets/homepage/style.css').write_text(style)
    (ROOT/'docs/assets/homepage/theme.js').write_text(theme)
    (ROOT/'docs/index.html').write_text(page)
    print(f'Built homepage: {len(groups)} categories, {total} published handbooks')
if __name__=='__main__':build()

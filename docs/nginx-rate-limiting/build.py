#!/usr/bin/env python3
"""Generate the public page, exact source windows, diagrams and offline bundle.

Requires markdown and beautifulsoup4 only at build time. Reader assets are a
snapshot of the site's shared reader, so building does not rewrite other pages.
"""
from pathlib import Path
from hashlib import sha256
import html, json, re, zipfile
import markdown
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SHA = '481d28cb4e04c8096b9b6134856891dc52ecc68f'
SOURCE = 'source/ngx_http_limit_req_module.c'
URL = f'https://github.com/nginx/nginx/blob/{SHA}/src/http/modules/ngx_http_limit_req_module.c'
WINDOWS = {
    'lookup': ('ngx_http_limit_req_lookup：已有Key的计算、拒绝与提交', 445, 480),
    'new-node': ('ngx_http_limit_req_lookup：新节点的首个请求', 508, 526),
    'delay-formula': ('ngx_http_limit_req_account：最后一项的初始延迟', 544, 553),
    'nodelay': ('ngx_http_limit_req：nodelay的阈值解析', 1020, 1023),
    'phase': ('ngx_http_limit_req_init：PREACCESS处理函数注册', 1086, 1102),
    'timer': ('ngx_http_limit_req_handler：挂起请求并注册定时器', 322, 328),
    'resume': ('ngx_http_limit_req_delay：恢复HTTP阶段', 350, 360),
    'lock': ('ngx_http_limit_req_handler：带共享锁的查找', 244, 250),
    'expire': ('ngx_http_limit_req_expire：淘汰条件', 651, 694),
    'account': ('ngx_http_limit_req_account：暂存节点的最终记账', 563, 605),
}
ESC = html.escape


def diagrams():
    directory = ROOT / 'diagrams'
    directory.mkdir(exist_ok=True)
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 450" role="img" aria-labelledby="title desc"><style>text{font-family:Arial,\'PingFang SC\',sans-serif;fill:#253247;font-size:17px}.small{font-size:14px;fill:#52627a}.box{fill:#edf3ff;stroke:#507bc5;stroke-width:2}.arrow{stroke:#52627a;stroke-width:2;fill:none}</style>'
    flow = head + '<title id="title">limit_req的单zone请求处理路径</title><desc id="desc">PREACCESS查找共享状态，超出burst拒绝，符合容量后记账，根据delay立即继续或注册定时器，到期恢复阶段。</desc><rect width="820" height="450" rx="12" fill="#fafbfc"/>'
    boxes = [(230, 20, 360, 52, 'PREACCESS：读取Key与共享状态'), (230, 105, 360, 52, '计算候选excess，检查burst'), (230, 190, 360, 52, '提交状态，计算等待时间'), (20, 285, 345, 52, '等待为0：继续HTTP阶段'), (450, 285, 345, 52, '等待大于0：定时器挂起请求'), (450, 380, 345, 52, '定时器到期：恢复HTTP阶段')]
    for x,y,w,h,t in boxes:
        flow += f'<rect class="box" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/><text x="{x+w/2}" y="{y+33}" text-anchor="middle">{t}</text>'
    for path in ['M410 72V105','M410 157V190','M330 242L193 285','M490 242L622 285','M622 337V380']:
        flow += f'<path class="arrow" d="{path}"/>'
    flow += '<path class="arrow" d="M590 131H710V210"/><text x="674" y="118" class="small">超过burst</text><rect x="630" y="210" width="160" height="48" rx="8" fill="#fff0ef" stroke="#c65349"/><text x="710" y="240" text-anchor="middle">拒绝</text><text x="32" y="400" class="small">等待占用请求与连接资源；Worker继续处理其他事件。</text></svg>'
    (directory/'flow.svg').write_text(flow)
    timeline = head.replace('820 450', '820 350') + '<title id="title">三种延迟配置的理论放行时间</title><desc id="desc">全新Key同一毫秒到达7个请求，rate10，burst5：默认在0到500毫秒均匀放行6次；nodelay同时放行6次；delay2先放行3次，再每100毫秒放行一次。第7次都拒绝。</desc><rect width="820" height="350" rx="12" fill="#fafbfc"/><text x="24" y="32">新Key · rate=10r/s · burst=5 · 同一毫秒到达7次</text>'
    for label, y, values in [('默认延迟',90,[0,100,200,300,400,500]), ('nodelay',180,[0]*6), ('delay=2',270,[0,0,0,100,200,300])]:
        timeline += f'<text x="24" y="{y}">{label}</text><path class="arrow" d="M205 {y}H735"/>'
        groups = {}
        for i,t in enumerate(values,1):
            groups.setdefault(t,[]).append(i)
        for t,indices in groups.items():
            x = 210+t*.9
            label = str(indices[0]) if len(indices)==1 else f'{indices[0]}–{indices[-1]}'
            timeline += f'<circle cx="{x}" cy="{y}" r="{12 if len(indices)==1 else 20}" fill="#235bb6"/><text x="{x}" y="{y+5}" text-anchor="middle" style="fill:#fff;font-size:12px">{label}</text>'
        timeline += f'<text x="748" y="{y+5}" class="small">7拒绝</text>'
    for t in range(0,501,100):
        timeline += f'<text x="{210+t*.9}" y="322" class="small" text-anchor="middle">{t}ms</text>'
    timeline += '</svg>'
    (directory/'timeline.svg').write_text(timeline)


def build():
    diagrams()
    lines = (ROOT/SOURCE).read_text().splitlines(keepends=True)
    manifest = {'version': '1.28.0', 'tag': 'release-1.28.0', 'commit': SHA,
                'file': SOURCE, 'sha256': sha256((ROOT/SOURCE).read_bytes()).hexdigest(), 'windows': []}
    article = (ROOT/'article.md').read_text()
    markdown_output = article
    for name,(title,start,end) in WINDOWS.items():
        code = ''.join(lines[start-1:end])
        manifest['windows'].append({'id': name, 'title': title, 'start': start, 'end': end, 'sha256': sha256(code.encode()).hexdigest()})
        snippet = f'<div class="source-card" data-source="{name}"><p class="source-caption"><a href="{URL}#L{start}-L{end}">{ESC(title)} · 原文件L{start}—L{end}</a></p><pre><code class="language-c">{ESC(code)}</code></pre></div>'
        article = article.replace(f'<!-- source:{name} -->', snippet)
        markdown_output = markdown_output.replace(f'<!-- source:{name} -->', f'<!-- source-window:{name} -->\n\n[{title} · 原文件L{start}—L{end}]({URL}#L{start}-L{end})\n\n```c\n{code}```')
    for name,caption in [('flow','单zone的正常流程；多zone暂存与最终记账见第6节。'),('timeline','标号代表同一毫秒内到达的次序；真实调度存在误差。')]:
        article = article.replace(f'<!-- diagram:{name} -->', f'<figure class="diagram"><img src="./diagrams/{name}.svg" alt="{ESC(caption)}" width="820" height="{450 if name=="flow" else 350}"><figcaption>{ESC(caption)}</figcaption></figure>')
        markdown_output = markdown_output.replace(f'<!-- diagram:{name} -->', f'![{caption}](./diagrams/{name}.svg)\n\n{caption}')
    (ROOT/'handbook.md').write_text(markdown_output)
    body = BeautifulSoup(markdown.markdown(article, extensions=['fenced_code','tables','attr_list']), 'html.parser')
    parts = re.split(r'(?=<h2 id=)', str(body))
    preface = BeautifulSoup(parts[0], 'html.parser')
    preface.h1.decompose()
    nav, chapters, metadata = [], [], []
    for i,part in enumerate(parts[1:],1):
        content = BeautifulSoup(part,'html.parser')
        heading = content.h2
        anchor = heading['id']
        title = re.sub(r'^\d+\s+', '', heading.get_text())
        heading.decompose()
        # Subheadings serve the current-chapter TOC and full-text search.
        for n,h in enumerate(content.select('h3'),1):
            if not h.get('id'):
                h['id'] = f'{anchor}-section-{n}'
        nav.append(f'<details class="chapter-nav" data-chapter="{anchor}"><summary><a href="#{anchor}"><span>{i:02d}</span>{ESC(title)}</a></summary><div>'+''.join(f'<a href="#{h["id"]}">{ESC(h.get_text())}</a>' for h in content.select('h3'))+'</div></details>')
        chapters.append(f'<article class="chapter" id="{anchor}" data-title="{ESC(title)}"><div class="chapter-title"><p class="eyebrow">第{i:02d}节 / 完整阅读</p><h1>{ESC(title)}</h1></div><div class="study">{content}</div></article>')
        metadata.append({'id':anchor,'title':title})
    downloads = '<a href="./handbook.md" download>Markdown原文</a><a href="./nginx-rate-limiting-offline.zip" download>离线阅读包</a><a href="./VERIFICATION.md">核验与实验记录</a>'
    intro = f'<section class="intro"><p class="eyebrow">TECHNICAL DEEP DIVE</p><h1>Nginx限流原理与工程实践</h1>{preface}<div class="meta"><span>NGINX1.28.0</span><span>11节机制分析</span><span>10段固定源码</span><span>2张图解</span></div><div class="reader-downloads">{downloads}</div></section>'
    page = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>Nginx限流原理与工程实践 | YiSiliang</title><meta name="description" content="从固定NGINX源码解释excess、rate、burst、nodelay与delay，分析共享内存、多zone记账、异步延迟和全局限流边界，附本地实验。"><link rel="stylesheet" href="./style.css"><script src="./theme.js"></script><script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script></head><body class="learning-reader" data-layout="learning-v2" data-reader="nginx-rate-limiting">'
    page += '<a class="skip" href="#main">跳到正文</a><header class="topbar"><button id="menu" class="mobile" aria-label="打开章节导航" aria-expanded="false" aria-controls="left-nav">目录</button><div class="brand"><a class="library-home" href="../">← 学习库</a>Nginx限流专题<span>NGINX1.28.0 / 漏桶与流量治理</span></div><div class="tools"><button id="search-open" aria-label="打开全文搜索">搜索 <kbd>/</kbd></button><button id="print" type="button">打印</button><button id="theme" aria-label="切换主题">主题：系统</button></div></header><div class="progress-track" aria-hidden="true"><div id="progress-bar"></div></div><div id="drawer-backdrop" hidden></div>'
    page += '<div class="layout"><nav id="left-nav" aria-label="章节目录"><p class="nav-label">学习目录 / 11节</p>'+''.join(nav)+'</nav><main id="main" tabindex="-1">'+intro+''.join(chapters)+'</main><aside id="right-toc" aria-label="当前章节目录"><div class="reading"><span id="progress-text">阅读进度0%</span><span id="current-label"></span></div><p class="nav-label">本节目录</p><nav id="toc"></nav></aside></div>'
    page += '<dialog id="search-dialog" aria-labelledby="search-title"><div class="search-head"><h2 id="search-title">全文搜索</h2><button id="search-close" aria-label="关闭搜索">关闭</button></div><label for="search-input">搜索关键词或源码方法</label><input id="search-input" type="search" placeholder="输入关键词，搜索完整正文" autocomplete="off"><p id="search-status" role="status" aria-live="polite">输入关键词，搜索完整正文。</p><div id="search-results"></div></dialog><div id="toast" role="status" aria-live="polite"></div><dialog id="diagram-dialog" aria-label="图解放大"><div id="diagram-actions"><button id="zoom-in" type="button">放大</button><button id="zoom-out" type="button">缩小</button><button id="zoom-reset" type="button">重置</button><button id="diagram-close" type="button">关闭</button></div><div id="diagram-content"></div></dialog><script src="./reader.js"></script></body></html>'
    # Match shared reader IDs so tools/style_readers.py can refresh this page
    # without creating a second set of script handlers.
    page = page.replace('<link rel="stylesheet" href="./style.css">', '<style id="reader-design">'+(ROOT/'style.css').read_text()+'</style>')
    page = page.replace('<script src="./theme.js"></script>', '<script id="reader-theme">'+(ROOT/'theme.js').read_text()+'</script>')
    page = page.replace('<script src="./reader.js"></script>', '<script id="reader-controls">'+(ROOT/'reader.js').read_text()+'</script>')
    (ROOT/'index.html').write_text(page)
    (ROOT/'source-evidence.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'metadata.json').write_text(json.dumps({'title':'Nginx限流原理与工程实践','version':'1.28.0','commit':SHA,'sections':metadata,'diagrams':2,'excerpts':10},ensure_ascii=False,indent=2)+'\n')
    offline = re.sub(r'<script[^>]*src="https://cloud\.umami\.is/script\.js"[^>]*></script>', '', page)
    offline = offline.replace('href="../"','href="https://yisiliang.github.io/"').replace('href="../nginx/#chapter-15"','href="https://yisiliang.github.io/nginx/#chapter-15"')
    offline = re.sub(r'<a[^>]*href="\./nginx-rate-limiting-offline.zip"[^>]*>.*?</a>', '', offline)
    offline_article = (ROOT/'handbook.md').read_text().replace('(../nginx/#chapter-15)', '(https://yisiliang.github.io/nginx/#chapter-15)')
    names = ['article.md','style.css','theme.js','reader.js','lab-nginx.conf','lab.py','run-lab.py','lab-results.json','VERIFICATION.md','metadata.json','source-evidence.json',SOURCE,'source/LICENSE','build.py','verify.py','diagrams/flow.svg','diagrams/timeline.svg']
    with zipfile.ZipFile(ROOT/'nginx-rate-limiting-offline.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in [('index.html',offline.encode()),('handbook.md',offline_article.encode())]+[(name,(ROOT/name).read_bytes()) for name in names]:
            info = zipfile.ZipInfo(name, date_time=(2026,10,9,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info,data)
    print('Built 11 sections, 10 exact source windows, 2 diagrams, standalone offline ZIP')


if __name__ == '__main__':
    build()

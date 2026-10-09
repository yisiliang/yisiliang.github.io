#!/usr/bin/env python3
"""Render the ThreadLocal incident appendix; preserve fixed-source JDK chapters."""
from pathlib import Path
import html
import json
import re
import subprocess
import zipfile

import markdown
from markdown.extensions.toc import slugify_unicode

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / 'docs/jdk-source'
SOURCE = BOOK / 'analysis-threadlocal-datasource.md'
START = '<!-- JDK-THREADLOCAL-APPENDIX:START -->'
END = '<!-- JDK-THREADLOCAL-APPENDIX:END -->'
ANCHOR = 'appendix-threadlocal-datasource'
TITLE = '附录A · 一次偶发SQL异常：ThreadLocal状态残留与多数据源切换'


def replace_block(text, block, boundary):
    if START in text:
        return re.sub(re.escape(START) + r'.*?' + re.escape(END),
                      lambda _: block, text, count=1, flags=re.S)
    if boundary:
        assert boundary in text
        return text.replace(boundary, block + '\n' + boundary, 1)
    return text.rstrip() + '\n\n' + block + '\n'


def build():
    article = SOURCE.read_text()
    engine = markdown.Markdown(
        extensions=['fenced_code', 'tables', 'toc'],
        extension_configs={'toc': {
            'slugify': lambda value, sep: 'threadlocal-case-' + slugify_unicode(value, sep),
            'toc_depth': '2-3',
        }},
    )
    content = engine.convert(article)
    content = re.sub(r'^<h1\b[^>]*>.*?</h1>\s*', '', content, count=1, flags=re.S)
    diagram_count = 0

    def diagram(match):
        nonlocal diagram_count
        diagram_count += 1
        path = BOOK / html.unescape(match['src'])
        svg = path.read_text()
        # IDs must be unique across all six SVGs and the rest of the reader.
        prefix = f'threadlocal-case-figure-{diagram_count}-'
        ids = re.findall(r'\bid="([^"]+)"', svg)
        for identifier in ids:
            svg = svg.replace(f'id="{identifier}"', f'id="{prefix}{identifier}"')
            svg = svg.replace(f'url(#{identifier})', f'url(#{prefix}{identifier})')
        svg = svg.replace('aria-labelledby="title desc"',
                          f'aria-labelledby="{prefix}title {prefix}desc"')
        caption = html.escape(html.unescape(match['alt']))
        return (f'<figure class="threadlocal-case-diagram">'
                f'<button class="expand" type="button" aria-label="放大{caption}">放大图解 ↗</button>'
                f'<div class="diagram-body">{svg}</div><figcaption>{caption}</figcaption></figure>')

    content = re.sub(r'<p><img alt="(?P<alt>[^"]*)" src="(?P<src>[^"]+)"\s*/></p>', diagram, content)
    assert diagram_count == 6
    pattern = r'<pre><code class="language-([^"]+)">(.*?)</code></pre>'
    fences = list(re.finditer(pattern, content, re.S))
    inputs = [{'language': 'plaintext' if m[1] == 'text' else m[1],
               'code': html.unescape(m[2])} for m in fences]
    highlighted = json.loads(subprocess.run(
        ['node', str(ROOT / 'tools/highlight_source.cjs')],
        input=json.dumps(inputs), text=True, capture_output=True, check=True,
    ).stdout)
    for match, value in reversed(list(zip(fences, highlighted))):
        content = content[:match.start()] + f'<pre><code class="hljs language-{match[1]}">{value}</code></pre>' + content[match.end():]
    section = f'''{START}
<section aria-labelledby="{ANCHOR}-title">
<a id="{ANCHOR}"></a>
<h1 id="{ANCHOR}-title">{TITLE}</h1>
<p>从ThreadLocal与线程池的源码机制，走进一次偶发线上问题的完整排查链。</p>
<p><a href="./analysis-threadlocal-datasource.md" download>下载本附录（Markdown）</a> · <a href="#chapter-14">回看ThreadLocal</a> · <a href="#chapter-25">回看线程池</a></p>
<details><summary>展开本附录目录</summary>{engine.toc}</details>
{content}
</section>
{END}'''
    page_path = BOOK / 'index.html'
    original_page = page_path.read_text()
    if 'data-layout="learning-v2"' in original_page:
        # Keep the already adapted chapter title instead of duplicating its ID.
        section = re.sub(r'<h1 id="'+re.escape(ANCHOR)+r'-title">.*?</h1>', '', section, count=1)
    page = replace_block(original_page, section, '</article>')
    # Generic type parameters in existing headings must remain text. Otherwise
    # the browser treats <U> as an unclosed underline element across the appendix.
    page = re.sub(r'<h4\b[^>]*>.*?</h4>',
                  lambda m: m[0].replace('<U>', '&lt;U&gt;'), page, flags=re.S)
    nav = f'<a href="#{ANCHOR}">附录A · ThreadLocal与偶发SQL异常</a>'
    if nav not in page and 'data-layout="learning-v2"' not in page:
        page = page.replace('</nav>', nav + '</nav>', 1)
    if f'<a href="#{ANCHOR}">附录</a>' not in page:
        page = page.replace('<a href="#chapter-38">追问检查</a></div>',
                            f'<a href="#chapter-38">追问检查</a><a href="#{ANCHOR}">附录</a></div>', 1)
    page = page.replace('124张内嵌SVG', '130张内嵌SVG')
    page = page.replace('40章 · 124张图 · 180段源码', '40章 · 1篇附录 · 130张图 · 180段源码')
    page = page.replace('40章、124张图、180段真实源码。', '40章、1篇附录、130张图、180段真实源码。')
    page = page.replace("article a[id^=\"chapter-\"]'", f"article a[id^=\"chapter-\"], article a[id=\"{ANCHOR}\"]'")
    page = page.replace('只使用公开OpenJDK源码、通用说明与虚构例子。正文不引用简历、工作项目、业务数据、聊天记录、凭据或本机目录；',
                        '源码章节使用公开OpenJDK源码、通用说明与虚构例子；附录收录经脱敏的故障复盘，不包含人员标识、真实系统名称、业务数据、凭据或本机目录。')
    page_path.write_text(page)
    handbook_path = BOOK / 'handbook.md'
    handbook = handbook_path.read_text()
    handbook = handbook.replace('只使用公开OpenJDK源码、通用说明与虚构例子。正文不引用简历、工作项目、业务数据、聊天记录、凭据或本机目录；',
                                '源码章节使用公开OpenJDK源码、通用说明与虚构例子；附录收录经脱敏的故障复盘，不包含人员标识、真实系统名称、业务数据、凭据或本机目录。')
    block = f'{START}\n<a id="{ANCHOR}"></a>\n' + re.sub(r'^# .*', '# ' + TITLE, article, count=1) + '\n' + END
    handbook = replace_block(handbook, block, None)
    link = f'\n\n**实战附录：**[ThreadLocal状态残留与偶发SQL异常](#{ANCHOR})。结合线程池复用，追踪选库状态如何从单例DAO传递到后续非单例DAO。'
    if link not in handbook:
        marker = '**阅读资源：**'
        start = handbook.index(marker)
        end = handbook.index('\n', start)
        handbook = handbook[:end] + link + handbook[end:]
    handbook_path.write_text(handbook)
    archive = BOOK / 'jdk-source-offline.zip'
    with zipfile.ZipFile(archive) as z:
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
    offline = re.sub(r'<script\b[^>]*src="https://cloud.umami.is/script.js"[^>]*></script>', '', page)
    generated = {'index.html': offline.encode(), 'handbook.md': handbook.encode(), SOURCE.name: article.encode()}
    generated.update({str(f.relative_to(BOOK)): f.read_bytes() for f in (BOOK / 'diagrams/appendix-threadlocal').glob('*.svg')})
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for info, data in entries:
            z.writestr(info, generated.pop(info.filename, data))
        for name, data in generated.items():
            z.writestr(name, data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert z.read('handbook.md') == handbook.encode()
        assert 'umami' not in z.read('index.html').decode().lower()
    print('Rendered JDK appendix with 6 inline SVGs; synchronized handbook and offline ZIP.')


if __name__ == '__main__':
    build()

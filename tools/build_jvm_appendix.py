#!/usr/bin/env python3
"""Render the reviewed XStream article into the JVM reader without rewriting existing chapters."""
from pathlib import Path
import re
import markdown
from markdown.extensions.toc import slugify_unicode

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'docs/jvm/index.html'
SOURCE = ROOT / 'docs/jvm/analysis-xstream-1.4.4-fgc.md'
START = '<!-- JVM-XSTREAM-APPENDIX:START -->'
END = '<!-- JVM-XSTREAM-APPENDIX:END -->'


def build():
    md = markdown.Markdown(extensions=['fenced_code', 'tables', 'toc'],
                           extension_configs={'toc': {'slugify': lambda value, sep: 'xstream-' + slugify_unicode(value, sep), 'toc_depth': '2-3'}})
    content = md.convert(SOURCE.read_text())
    content = re.sub(r'^<h1\b[^>]*>.*?</h1>\s*', '', content, count=1, flags=re.S)
    toc = md.toc
    section = f'''{START}
<section aria-labelledby="appendix-xstream-title">
<a id="appendix-xstream"></a>
<h1 id="appendix-xstream-title">附录A · XStream1.4.4与每请求new XStream()：周期性Full GC分析</h1>
<p><a href="./analysis-xstream-1.4.4-fgc.md" download>下载修订稿（Markdown）</a> · <a href="./xstream-lab.zip" download>下载实验与证据包</a> · <a href="./xstream-review.md">检查记录</a></p>
<details><summary>展开本附录目录</summary>{toc}</details>
{content}
</section>
{END}'''
    source = PAGE.read_text()
    if START in source:
        source = re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda _: section, source, count=1, flags=re.S)
    else:
        source = source.replace('</article>', section + '\n</article>', 1)
    nav = '<a href="#appendix-xstream">附录A · XStream1.4.4周期性Full GC分析</a>'
    if nav not in source:
        source = source.replace('</nav>', nav + '</nav>', 1)
    source = source.replace('76节 · 62张图', '76节 · 1篇附录 · 62张图')
    source = source.replace('<a href="#chapter-73">阅读案例</a></div>', '<a href="#chapter-73">阅读案例</a><a href="#appendix-xstream">附录</a></div>', 1)
    if '<span>2026年10月8日附录更新</span>' not in source:
        source = source.replace('<span>2026年10月1日修订</span>', '<span>2026年10月1日修订</span><span>2026年10月8日附录更新</span>', 1)
    source = re.sub(r'article a\[id\^="chapter-"\](?:, article a\[id="appendix-xstream"\])*', 'article a[id^="chapter-"], article a[id="appendix-xstream"]', source)
    PAGE.write_text(source)
    print(f'Rendered {SOURCE.relative_to(ROOT)} into {PAGE.relative_to(ROOT)}')


if __name__ == '__main__':
    build()

#!/usr/bin/env python3
"""Build one standalone reader page per technical topic.

Every topic is an independent HTML page under ``docs/topics/<slug>/``.
The same Markdown source is also published next to it as ``article.md``.
Adding a topic means adding one Markdown file and one entry in ``topics.json``.
"""
from pathlib import Path
import hashlib, html, json, re, sys

import markdown
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT.parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))
from reader.learning_words import html_wording
from style_readers import refresh

TOPICS = json.loads((ROOT / 'topics.json').read_text())
SOURCES = json.loads((ROOT / 'sources.json').read_text())
NOTES = json.loads((ROOT / 'source-notes.json').read_text())
ANCHORS = json.loads((ROOT / 'anchors.json').read_text())

META = {
    'mqappend': ('RocketMQ 4.9.8', 'CommitLog.asyncPutMessage', 'java'),
    'mqqueueassign': ('RocketMQ 4.9.8', 'CommitLog.DefaultAppendMessageCallback.doAppend', 'java'),
    'mqreput': ('RocketMQ 4.9.8', 'DefaultMessageStore.ReputMessageService.doReput', 'java'),
    'mqdispatch': ('RocketMQ 4.9.8', 'DefaultMessageStore.doDispatch', 'java'),
    'mqcqposition': ('RocketMQ 4.9.8', 'ConsumeQueue.putMessagePositionInfo', 'java'),
    'mqcqorder': ('RocketMQ 4.9.8', 'ConsumeQueue.putMessagePositionInfo', 'java'),
    'mqread': ('RocketMQ 4.9.8', 'DefaultMessageStore.getMessage', 'java'),
    'mqindexput': ('RocketMQ 4.9.8', 'IndexFile.putKey', 'java'),
    'mqkeyverify': ('RocketMQ 4.9.8', 'MQAdminImpl.queryMessage', 'java'),
    'mqhalf': ('RocketMQ 4.9.8', 'TransactionalMessageBridge.parseHalfMessageInner', 'java'),
    'mqrecover': ('RocketMQ 4.9.8', 'DefaultMessageStore.recover', 'java'),
    'mqcheckpoint': ('RocketMQ 4.9.8', 'StoreCheckpoint.flush', 'java'),
    'mqrecovertruncate': ('RocketMQ 4.9.8', 'CommitLog.recoverAbnormally', 'java'),
    'mqrestart': ('RocketMQ 4.9.8', 'DefaultMessageStore.start', 'java'),
    'mqindexload': ('RocketMQ 4.9.8', 'IndexService.load', 'java'),
    'aqsqueue': ('OpenJDK 8u462-b08', 'AbstractQueuedSynchronizer.acquireQueued', 'java'),
    'chmput': ('OpenJDK 8u462-b08', 'ConcurrentHashMap.putVal', 'java'),
    'xstream': ('XStream 1.4.4 / c4c7122', 'Sun14ReflectionProvider.getMungedConstructor', 'java'),
    'aqs': ('OpenJDK 8u462-b08', 'AbstractQueuedSynchronizer.acquire', 'java'),
    'lock': ('OpenJDK 8u462-b08', 'ReentrantLock.Sync.nonfairTryAcquire', 'java'),
    'pool': ('OpenJDK 8u462-b08', 'ThreadPoolExecutor.execute', 'java'),
    'hashmap': ('OpenJDK 8u462-b08', 'HashMap.hash', 'java'),
    'chm': ('OpenJDK 8u462-b08', 'ConcurrentHashMap.transfer', 'java'),
    'bits': ('OpenJDK 8u462-b08', 'Bits.tryReserveMemory', 'java'),
    'cms': ('HotSpot 8u462-b08', 'CMSCollector::collect_in_background', 'cpp'),
    'g1': ('HotSpot 8u462-b08', 'G1CollectedHeap::do_collection_pause_at_safepoint', 'cpp'),
    'beans': ('Spring Framework 5.3.31', 'DefaultSingletonBeanRegistry.getSingleton', 'java'),
    'tx': ('Spring Framework 5.3.31', 'TransactionAspectSupport.invokeWithinTransaction', 'java'),
    'boot': ('Spring Boot 2.7.18', 'AutoConfigurationImportSelector.getCandidateConfigurations', 'java'),
    'mvcc': ('MySQL 8.0.36', 'ReadView::changes_visible', 'cpp'),
    'commitlog': ('RocketMQ 4.9.8', 'CommitLog.asyncPutMessage', 'java'),
    'mqtx': ('RocketMQ 4.9.8', 'TransactionalMessageServiceImpl.check', 'java'),
    'mqsend': ('RocketMQ 4.9.8', 'DefaultMQProducerImpl.sendMessageInTransaction', 'java'),
    'redis': ('Redis 7.2.4', 'dbDelete', 'c'),
    'redislock': ('Redis 7.2.4', 'setGenericCommand', 'c'),
    'netty': ('Netty 4.1.108.Final', 'NioEventLoop.run', 'java'),
    'reactor': ('Reactor 3.4.34', 'FluxPublishOn.onNext', 'java'),
    'gateway': ('Spring Cloud Gateway 3.1.8', 'FilteringWebHandler.handle', 'java'),
    'jitsubmit': ('HotSpot 8u462-b08', 'AdvancedThresholdPolicy::submit_compile', 'cpp'),
    'jitload': ('HotSpot 8u462-b08', 'Parse::do_get_xxx / load', 'cpp'),
    'jitacquire': ('HotSpot 8u462-b08', 'Parse::do_get_xxx / acquire', 'cpp'),
    'jitrelease': ('HotSpot 8u462-b08', 'Parse::do_put_xxx / release', 'cpp'),
    'jitvolatile': ('HotSpot 8u462-b08', 'Parse::do_put_xxx / volatile', 'cpp'),
    'jitx86': ('HotSpot 8u462-b08', 'membar_volatile', 'cpp'),
    'jitdeopt': ('HotSpot 8u462-b08', 'Deoptimization::uncommon_trap', 'cpp'),
}
REFS = {
    1: ['aqs', 'lock', 'pool'], 2: ['hashmap', 'chm'], 3: ['cms', 'g1'], 4: ['bits', 'xstream'],
    5: ['beans', 'tx', 'boot'], 6: ['mvcc', 'pg', 'oracle'],
    7: ['commitlog', 'mqsend', 'mqtx', 'mqappend', 'mqqueueassign', 'mqreput', 'mqdispatch',
        'mqcqposition', 'mqcqorder', 'mqread', 'mqindexput', 'mqkeyverify', 'mqhalf', 'mqrecover',
        'mqcheckpoint', 'mqrecovertruncate', 'mqrestart', 'mqindexload'],
    8: ['redis', 'redislock'], 9: ['tx', 'mqtx'],
    10: ['netty', 'reactor', 'gateway'],
    11: ['jitsubmit', 'jitload', 'jitacquire', 'jitrelease', 'jitvolatile', 'jitx86', 'jitdeopt'],
}
EXTRA_REFS = {
    3: [('Oracle JDK8 GC Tuning Guide', 'https://docs.oracle.com/javase/8/docs/technotes/guides/vm/gctuning/')],
    4: [('Netty 引用计数指南', 'https://netty.io/wiki/reference-counted-objects.html')],
    6: [('MySQL 一致性读', 'https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html'),
        ('OceanBase 官方文档（须选择实际租户版本）', 'https://en.oceanbase.com/docs')],
    7: [('RocketMQ 5.x 事务消息与版本边界', 'https://rocketmq.apache.org/docs/featureBehavior/04transactionmessage/'),
        ('RocketMQ 5.3.4 源码对照', 'https://github.com/apache/rocketmq/tree/rocketmq-all-5.3.4')],
    8: [('Redis 分布式锁边界', 'https://redis.io/docs/latest/develop/use/patterns/distributed-locks/'),
        ('Redisson 锁与 Watchdog', 'https://redisson.pro/docs/data-and-services/locks-and-synchronizers/')],
    9: [('CAP 原论文 Gilbert/Lynch', 'https://groups.csail.mit.edu/tds/papers/Gilbert/Brewer2.pdf')],
    10: [('Reactor 3.4.34 Reference', 'https://projectreactor.io/docs/core/3.4.34/reference/')],
    11: [('JLS8 §17.3 / sleep与yield', 'https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.3'),
         ('JLS8 §17.4 / 内存模型与HB', 'https://docs.oracle.com/javase/specs/jls/se8/html/jls-17.html#jls-17.4'),
         ('Oracle HotSpot分层编译与逃逸分析', 'https://docs.oracle.com/javase/8/docs/technotes/guides/vm/performance-enhancements-7.html'),
         ('Oracle JDK8 java命令与诊断参数', 'https://docs.oracle.com/javase/8/docs/technotes/tools/unix/java.html')],
}
ROUTE = [
    ('0–8 分钟', 1, 'JMM、AQS 与线程池准入'),
    ('8–15 分钟', 2, 'CHM 迁移协议与原子 API'),
    ('15–24 分钟', 3, 'CMS/G1 正常、失败与恢复'),
    ('24–32 分钟', 4, 'OOM 分类与证据链'),
    ('32–40 分钟', 5, '代理、事务与连接预算'),
    ('40–49 分钟', 6, 'MVCC、锁与执行计划'),
    ('49–64 分钟', 7, 'RocketMQ 五类失败边界'),
    ('64–72 分钟', 8, '缓存一致性与锁租约'),
    ('72–81 分钟', 9, 'Outbox、幂等与补偿'),
    ('81–90 分钟', 10, 'EventLoop、重试与容量'),
]
ESC = lambda value: html.escape(str(value), quote=True)


def topic_source(topic):
    text = (ROOT / topic['source']).read_text()
    slug = topic['slug']
    if slug == 'nginx-rate-limiting':
        text = text.replace('](../nginx-rate-limiting/', '](../assets/nginx-rate-limiting/')
        text = text.replace('](./VERIFICATION.md)', '](../assets/nginx-rate-limiting/VERIFICATION.md)')
    elif slug == 'jvm-memory-structure-oom':
        text = text.replace('](../jvm-memory-oom/diagrams/', '](../assets/jvm-memory-structure-oom/diagrams/')
    elif slug == 'fastjson2-arm64-jit':
        text = re.sub(r' \{#[^}]+\}(?=\n|$)', '', text)
        text = text.replace('](../fastjson2-arm-jit/', '](../assets/fastjson2-arm64-jit/')
        for diagram in ['address', 'patch']:
            text = text.replace(
                f'<!-- diagram:{diagram} -->',
                f'![Fastjson2 ARM64 JIT：{diagram}](../assets/fastjson2-arm64-jit/diagrams/{diagram}.svg)')
        text = text.replace('../java-architect-interview/#c11', '../jit-jmm-memory-barriers/')
        text = text.replace('](../jdk-source/', '](../../jdk-source/')
        text = text.replace('](../jvm/', '](../../jvm/')

    def target(number, fragment):
        if int(number) == topic['n']:
            return f'#c{number}{fragment or ""}'
        return f'../{TOPICS[int(number) - 1]["slug"]}/{fragment or ""}'

    text = re.sub(r'href="#c(\d+)(-s\d+)?"',
                  lambda m: 'href="' + target(m.group(1), m.group(2)) + '"', text)
    text = re.sub(r'\]\(#c(\d+)(-s\d+)?\)',
                  lambda m: '](' + target(m.group(1), m.group(2)) + ')', text)
    return text


def insert_source(topic, text):
    def replace(match):
        key = match.group(1)
        source = SOURCES[key]
        version, method, lang = META[key]
        url = source['url'].replace('raw.githubusercontent.com/', 'github.com/', 1)
        segments = url.split('/')
        url = '/'.join(segments[:5] + ['blob'] + segments[5:]) if 'github.com' in url else url
        url += f"#L{source['line']}-L{source['end_line']}"
        return (f'\n<div class="source-caption"><code>{method}</code><span>{version} · '
                f'L{source["line"]}–L{source["end_line"]} · <a href="{url}">完整源码</a></span></div>\n\n'
                f'```{lang}\n{source["excerpt"]}\n```\n\n{NOTES[key]}\n')
    return re.sub(r'<!-- source:(\w+) -->', replace, text)


def build_body(topic, text, stats):
    body = BeautifulSoup(markdown.markdown(text, extensions=['fenced_code', 'tables', 'md_in_html']), 'html.parser')
    for paragraph in list(body.find_all('p')):
        image = paragraph.find('img')
        if image and len(paragraph.contents) == 1:
            figure = body.new_tag('figure', attrs={'class': 'diagram image-diagram'})
            paragraph.wrap(figure)
            paragraph.unwrap()
            caption = body.new_tag('figcaption')
            caption.string = image.get('alt', '技术图解')
            figure.append(caption)
    body.h1.decompose()
    registry = ANCHORS.setdefault(f'c{topic["n"]}', {})
    for heading in body.find_all(['h2', 'h3']):
        if heading.get_text() not in registry:
            last = max([int(value.rsplit('-s', 1)[1]) for value in registry.values()] or [0])
            registry[heading.get_text()] = f'c{topic["n"]}-s{last + 1}'
        heading['id'] = registry[heading.get_text()]
        heading['tabindex'] = '-1'
    for code in body.select('code.language-shell'):
        code['class'] = ['language-bash']
    for code in body.select('code.language-mermaid'):
        stats['diagrams'] += 1
        pre = code.parent
        diagram = body.new_tag('figure', attrs={'class': 'diagram', 'data-diagram': str(stats['diagrams'])})
        pre['class'] = ['mermaid']
        pre.string = code.get_text()
        pre.replace_with(diagram)
        diagram.append(pre)
        caption = body.new_tag('figcaption')
        caption.string = f'图 {stats["diagrams"]} · 对照上文阅读流程'
        diagram.append(caption)
    stats['images'] += len(body.select('figure.image-diagram'))
    stats['code_blocks'] += len(body.select('pre:not(.mermaid)'))
    stats['questions'] += len(body.select('details'))
    for details in body.select('details'):
        heading = details.find_previous_sibling('h3')
        if not heading:
            continue
        details['class'] = ['question']
        summary = details.summary
        summary.clear()
        summary.append(heading.extract())
        answer = body.new_tag('div', attrs={'class': 'answer'})
        for child in list(details.children):
            if child is not summary:
                answer.append(child.extract())
        details.append(answer)
    return body


def quick_section(topic, body):
    questions = body.select('details')[:(5 if topic['n'] == 7 else 4)]
    qa = ''
    for details in questions:
        clone = BeautifulSoup(str(details), 'html.parser')
        title = clone.summary.h3
        if title:
            title.name = 'span'
            title.attrs = {'class': 'question-title'}
        for element in clone.select('[id]'):
            del element['id']
        qa += str(clone)

    def paragraph_after(title):
        heading = next((h for h in body.find_all('h3') if h.get_text() == title), None)
        if not heading:
            return ''
        result = []
        for element in heading.next_siblings:
            if getattr(element, 'name', None) in ['h2', 'h3']:
                break
            if getattr(element, 'name', None) in ['p', 'ul', 'ol']:
                result.append(str(element))
        return ''.join(result)

    points = ''.join(f'<li>{html.escape(point)}</li>' for point in topic['quick'])
    prefix = f'c{topic["n"]}'
    quick = (f'<section class="quick" aria-label="要点速览"><h2 id="{prefix}-quick-core">先记住这几件事</h2>'
             f'<ul>{points}</ul><h2 id="{prefix}-quick-qa">{"五" if topic["n"] == 7 else "四"}个重点问题</h2>{qa}'
             f'<h2 id="{prefix}-quick-answer">核心要点</h2>{paragraph_after("一分钟要点回顾")}'
             f'<h2 id="{prefix}-quick-errors">常见误解与源码</h2>{paragraph_after("延伸问题、常见误解与速记")}</section>')
    return quick


def left_nav(topic):
    items = []
    for other in TOPICS:
        if other['n'] == topic['n']:
            items.append(
                f'<details class="chapter-nav current" data-chapter="c{topic["n"]}" open>'
                f'<summary><a href="./"><span>{topic["n"]:02d}</span>{ESC(other["title"])}</a></summary><div></div></details>')
        else:
            items.append(
                f'<a class="topic-nav-link" href="../{other["slug"]}/"><span>{other["n"]:02d}</span>{ESC(other["title"])}</a>')
    return (f'<nav id="left-nav" aria-label="技术专题">'
            f'<div class="reading"><span id="progress-text">阅读进度 0%</span><span id="current-label"></span></div>'
            f'<p class="nav-label">技术专题 / {len(TOPICS)}篇</p>'
            f'<a class="topic-nav-link topic-nav-index" href="../"><span>目录</span>全部专题</a>'
            + ''.join(items) + '</nav>')


def build_page(topic):
    text = insert_source(topic, topic_source(topic))
    if topic['n'] <= 11:
        text += ('\n\n## 官方资料与版本来源\n\n本文按上述版本阅读官方源码，函数窗口保留完整分支与边界，'
                 '声明窗口聚焦所讨论的字段或配置。版权见 [source-notices.txt](../source-notices.txt)，'
                 '下载记录见 [sources.json](../sources.json)。\n\n')
    for key in REFS.get(topic['n'], []):
        source = SOURCES[key]
        label = f'{META[key][1]} · {META[key][0]}' if key in META else (
            'PostgreSQL16 隔离级别' if key == 'pg' else 'Oracle19c 并发与一致性')
        text += f'- [{label}]({source["url"]})\n'
    for label, url in EXTRA_REFS.get(topic['n'], []):
        text += f'- [{label}]({url})\n'
    stats = {'chapters': 1, 'questions': 0, 'diagrams': 0, 'images': 0, 'code_blocks': 0}
    body = build_body(topic, text, stats)
    quick = quick_section(topic, body)
    title = topic['title']
    prefix = f'c{topic["n"]}'
    previous = TOPICS[topic['n'] - 2] if topic['n'] > 1 else None
    following = TOPICS[topic['n']] if topic['n'] < len(TOPICS) else None
    pager = '<nav class="topic-pager" aria-label="专题翻页">'
    pager += (f'<a href="../{previous["slug"]}/">← {ESC(previous["title"])}</a>' if previous else '<span></span>')
    pager += '<a href="../">全部专题</a>'
    pager += (f'<a href="../{following["slug"]}/">{ESC(following["title"])} →</a>' if following else '<span></span>')
    pager += '</nav>'
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">
<meta name="description" content="{ESC(topic['summary'])}">
<title>{ESC(title)} · 技术专题 | YiSiliang</title>
<script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script>
<script defer src="../vendor/prism.js" data-manual></script><script defer src="../vendor/prism-c.js"></script><script defer src="../vendor/prism-cpp.js"></script><script defer src="../vendor/prism-java.js"></script><script defer src="../vendor/prism-sql.js"></script><script defer src="../vendor/prism-bash.js"></script><script defer src="../vendor/prism-yaml.js"></script>
</head><body class="learning-reader" data-layout="learning-v2" data-reader="topics">
<a class="skip" href="#main">跳到正文</a>
<header class="topbar"><button id="menu" class="mobile" aria-label="打开专题导航" aria-expanded="false" aria-controls="left-nav">目录</button><div class="brand"><a class="library-home" href="../../">← 学习库</a>技术专题<span>源码原理 · 故障排查 · 架构实践</span></div><div class="tools"><button id="search-open" aria-label="打开全文搜索">搜索 <kbd>/</kbd></button><button id="mode" aria-pressed="false">要点速览</button><button id="print" type="button">打印</button><button id="theme" aria-label="切换主题">主题：系统</button></div></header>
<div class="progress-track" aria-hidden="true"><div id="progress-bar"></div></div><div id="drawer-backdrop" hidden></div>
<div class="layout">{left_nav(topic)}<main id="main" tabindex="-1">
<article class="chapter" id="{prefix}" data-title="{ESC(title)}"><div class="chapter-title"><p class="eyebrow">专题 {topic['n']:02d} / 完整阅读</p><h1>{ESC(title)}</h1></div><div class="study">{body}</div>{quick}</article>{pager}</main></div>
<dialog id="search-dialog" aria-labelledby="search-title"><div class="search-head"><h2 id="search-title">全文搜索</h2><button id="search-close" aria-label="关闭搜索">关闭</button></div><label for="search-input">搜索当前专题的关键词、源码方法或学习问题</label><input id="search-input" type="search" placeholder="例如：sizeCtl、事务回查、Direct buffer" autocomplete="off"><p id="search-status" role="status" aria-live="polite">输入关键词，搜索本篇完整正文与答案。</p><div id="search-results"></div></dialog><div id="toast" role="status" aria-live="polite"></div>
<footer>按章标注源码版本 · 教学案例与实测排查分别标注 · <a href="./article.md">下载 Markdown 正文</a> · <a href="../VERIFICATION.md">验证范围</a></footer></body></html>'''
    page = refresh(page, False)
    (ROOT / topic['slug']).mkdir(exist_ok=True)
    (ROOT / topic['slug'] / 'index.html').write_text(page)
    (ROOT / topic['slug'] / 'article.md').write_text(text.rstrip() + '\n')
    return stats


def build_index(stats):
    cards = []
    for topic in TOPICS:
        cards.append(f'''<article class="topic-card"><a href="./{topic["slug"]}/"><span class="num">{topic["n"]:02d}</span><h2>{ESC(topic["title"])}</h2><p>{ESC(topic["summary"])}</p><span class="more">完整阅读 ↗</span></a></article>''')
    route = ''.join(f'<li><time>{time}</time><a href="./{TOPICS[n - 1]["slug"]}/">{ESC(label)}</a></li>' for time, n, label in ROUTE)
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">
<meta name="description" content="技术专题：14 篇独立长文，覆盖 Java 并发、JVM、Spring、数据库、RocketMQ、Redis、分布式事务、稳定性、JIT 与 Nginx 限流。">
<title>技术专题 · 源码之下，系统之上 | YiSiliang</title>
<style>{ (TOOLS / 'reader/theme.css').read_text() }</style>
<script>{ (TOOLS / 'reader/theme.js').read_text() }</script>
<script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
a{{color:var(--accent);text-decoration:none}}.wrap{{max-width:1180px;margin:0 auto;padding:0 26px}}
header{{border-bottom:1px solid var(--border);background:var(--surface)}}.bar{{display:flex;align-items:center;justify-content:space-between;min-height:70px;gap:16px;flex-wrap:wrap}}
.brand{{font-weight:700}}.brand span{{font-size:11px;color:var(--muted);font-weight:400;margin-left:8px}}nav a{{margin-left:16px;font-size:14px}}
.hero{{padding:54px 0 30px;border-bottom:1px solid var(--border)}}.eyebrow{{font-size:11px;letter-spacing:.12em;color:var(--muted);font-weight:600;margin:0}}
h1{{font-size:36px;margin:14px 0 10px;letter-spacing:-.02em}}.hero p{{max-width:760px;color:var(--muted);margin:0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;padding:32px 0 12px}}
.topic-card{{border:1px solid var(--border);border-radius:10px;background:var(--surface);transition:.15s}}.topic-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.topic-card a{{display:block;padding:20px 22px 18px;color:var(--text)}}.num{{font:12px/1.4 ui-monospace,monospace;color:var(--muted)}}
.topic-card h2{{font-size:19px;margin:6px 0 8px;line-height:1.45}}.topic-card p{{font-size:13px;color:var(--muted);margin:0 0 14px;line-height:1.7}}
.more{{font-size:12px;color:var(--accent)}}.route{{padding:26px 0 60px}}.route h2{{font-size:22px;margin:0 0 14px}}
.route ol{{list-style:none;padding:0;display:grid;gap:8px}}.route li{{display:grid;grid-template-columns:110px 1fr;gap:14px;font-size:14px;border-bottom:1px solid var(--border);padding-bottom:8px}}
.route time{{color:var(--muted)}}footer{{border-top:1px solid var(--border);padding:24px 0;font-size:12px;color:var(--muted)}}
@media(max-width:640px){{h1{{font-size:28px}}.hero{{padding:34px 0 22px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><div class="wrap bar"><div class="brand"><a href="../">← 学习库</a><span>SOURCE NOTES / TECHNICAL DEEP DIVES</span></div><nav><a href="../">首页</a><a href="https://github.com/yisiliang/yisiliang.github.io" target="_blank" rel="noreferrer">GitHub</a><button id="theme" type="button" style="margin-left:16px;padding:4px 10px;border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text)">主题：系统</button></nav></div></header>
<main class="wrap"><section class="hero"><p class="eyebrow">TECHNICAL DEEP DIVES</p><h1>技术专题</h1><p>{len(TOPICS)} 篇独立长文，按问题读原理，再对照固定版本源码。每篇都有自己的目录与搜索，不再合并成一个总页。</p></section>
<section class="grid">{''.join(cards)}</section>
<section class="route" id="review-route"><h2>90分钟回顾路线</h2><p>按下面顺序复习，先回顾每篇的要点速览，再展开原理问答；RocketMQ 留 15 分钟。</p><ol>{route}</ol><p>扩展阅读：<a href="./jit-jmm-memory-barriers/">JIT即时编译、JMM与内存屏障</a>、<a href="./nginx-rate-limiting/">Nginx限流原理与工程实践</a>、<a href="./jvm-memory-structure-oom/">JVM内存结构与OOM排查实战</a>、<a href="./fastjson2-arm64-jit/">Fastjson2与ARM64 JIT编译缺陷排查</a>。</p></section></main>
<footer><div class="wrap">共 {stats['topics']} 篇 · {stats['questions']} 道三层问答 · {stats['figures']} 张图解 · 按篇标注源码版本 · <a href="../">源码学习库</a></footer>
<script>const names={{system:'系统',light:'浅色',dark:'深色'}};const button=document.getElementById('theme');const label=()=>{{button.textContent='主题：'+names[learningTheme.get()];}};label();button.addEventListener('click',()=>{{learningTheme.cycle();label();}});window.addEventListener('learning-theme-change',label);</script>
</body></html>'''
    (ROOT / 'index.html').write_text(page)


REDIRECTS = {
    'java-architect-interview': ('/topics/', True),
    'fastjson2-arm-jit': ('/topics/fastjson2-arm64-jit/', False),
    'nginx-rate-limiting': ('/topics/nginx-rate-limiting/', False),
    'jvm-memory-oom': ('/topics/jvm-memory-structure-oom/', False),
}


def write_redirects():
    """Keep retired article URLs working and map old #cN anchors to new pages."""
    slugs = json.dumps([topic['slug'] for topic in TOPICS], ensure_ascii=False)
    for name, (target, map_hash) in REDIRECTS.items():
        folder = ROOT.parent / name
        folder.mkdir(exist_ok=True)
        script = ''
        if map_hash:
            script = (
                '<script>(function(){var slugs=' + slugs + ';'
                'var m=location.hash.match(/^#c(\\d+)(?:-s\\d+)?$/);'
                "if(m){location.replace('/topics/'+slugs[Number(m[1])-1]+'/'+location.hash);return;}"
                "location.replace('/topics/'+location.hash);})();</script>"
            )
        else:
            script = f"<script>location.replace('{target}'+location.search);</script>"
        (folder / 'index.html').write_text(
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="0; url={target}">'
            f'<link rel="canonical" href="https://yisiliang.github.io{target}">'
            f'<title>页面已迁移 | YiSiliang</title></head><body>'
            f'<p>本页已迁移到 <a href="{target}">新地址</a>。</p>{script}</body></html>'
        )


def main():
    stats = {'topics': len(TOPICS), 'questions': 0, 'diagrams': 0, 'images': 0, 'code_blocks': 0}
    for topic in TOPICS:
        topic_stats = build_page(topic)
        for key in ('questions', 'diagrams', 'images', 'code_blocks'):
            stats[key] += topic_stats[key]
    stats['figures'] = stats['diagrams'] + stats['images']
    (ROOT / 'anchors.json').write_text(json.dumps(ANCHORS, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'content-stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    build_index(stats)
    write_redirects()
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    main()

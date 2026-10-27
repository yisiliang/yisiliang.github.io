#!/usr/bin/env python3
"""Build the guide from Markdown and byte-exact, AST-bounded upstream functions.

First build: --source /path/to/langgraph-at-pinned-commit
Later builds use the checked-in source evidence. --run-labs refreshes runtime output.
"""
import argparse
import ast
import hashlib
import html
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
import markdown

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHA = '41c9c22fdc83d68a2859d0c9a2b627c8615a792f'
SPECS = [
    ('last-value', 'channels/last_value.py', 'LastValue.update'),
    ('field-binop', 'graph/state.py', '_is_field_binop'),
    ('binop-update', 'channels/binop.py', 'BinaryOperatorAggregate.update'),
    ('compile', 'graph/state.py', 'StateGraph.compile'),
    ('attach-edge', 'graph/state.py', 'CompiledStateGraph.attach_edge'),
    ('tick', 'pregel/_loop.py', 'PregelLoop.tick'),
    ('apply-writes', 'pregel/_algo.py', 'apply_writes'),
    ('interrupt', 'types.py', 'interrupt'),
    ('retry', 'pregel/_retry.py', 'run_with_retry'),
]

def function(source, qualname):
    nodes = ast.parse(source).body
    for name in qualname.split('.'):
        matches = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name]
        # Overloads precede the implementation; select the final definition.
        node = matches[-1]
        nodes = node.body
    start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
    lines = source.splitlines(keepends=True)
    return start, node.end_lineno, ''.join(lines[start-1:node.end_lineno])


def extract(upstream):
    manifest = []
    version_source = (upstream / 'libs/langgraph/pyproject.toml').read_text()
    assert 'version = "1.2.16"' in version_source
    for eid, file, symbol in SPECS:
        path = 'libs/langgraph/langgraph/' + file
        source = (upstream / path).read_text()
        start, end, code = function(source, symbol)
        target = f'excerpts/{eid}.py.txt'
        (HERE / target).write_text(code)
        manifest.append(dict(id=eid, symbol=symbol, path=path, start=start, end=end,
            file=target, sha=SHA, sha256=hashlib.sha256(code.encode()).hexdigest(),
            url=f'https://github.com/langchain-ai/langgraph/blob/{SHA}/{path}#L{start}-L{end}'))
    (HERE / 'source-evidence.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'UPSTREAM-LICENSE.txt').write_text((upstream / 'LICENSE').read_text())


def diagrams():
    def svg(name, title, desc, nodes, edges, notes, height=360):
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc"><title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(desc)}</desc><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#527090"/></marker></defs><rect width="960" height="{height}" rx="14" fill="#f6f8fc"/><text x="28" y="38" font-size="23" font-weight="600" fill="#20354f" font-family="sans-serif">{html.escape(title)}</text>']
        for path, label, x, y in edges:
            parts.append(f'<path d="{path}" fill="none" stroke="#527090" stroke-width="2" marker-end="url(#arrow)"/>')
            if label:
                parts.append(f'<text x="{x}" y="{y}" fill="#526780" font-size="13" font-family="sans-serif">{html.escape(label)}</text>')
        for x, y, w, label, detail, color in nodes:
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="78" rx="10" fill="{color}" stroke="#b7c8dd"/><text x="{x+w/2}" y="{y+30}" text-anchor="middle" fill="#20354f" font-family="sans-serif" font-size="17" font-weight="600">{html.escape(label)}</text><text x="{x+w/2}" y="{y+57}" text-anchor="middle" fill="#526780" font-family="sans-serif" font-size="13">{html.escape(detail)}</text>')
        for i, note in enumerate(notes):
            parts.append(f'<text x="28" y="{height-48+i*23}" fill="#526780" font-family="sans-serif" font-size="14">{html.escape(note)}</text>')
        parts.append('</svg>')
        (HERE / 'diagrams' / name).write_text(''.join(parts))
    svg('01-layers.svg', '模型负责判断，图负责推进，业务服务负责提交', '业务应用分别调用模型、编排运行时与权威业务服务。',
        [(25,110,200,'应用入口','身份、输入、界面','#e7efff'), (280,110,180,'LangGraph','状态与控制流','#dff4ee'), (520,65,195,'模型 / LangChain','提取与工具协议','#e7efff'), (520,180,195,'业务服务','校验、幂等与事务','#fff0d9')],
        [('M225,149 H280','',0,0),('M460,149 H490 V104 H520','候选结果',473,85),('M460,149 H490 V219 H520','业务调用',465,253)],
        ['图决定何时执行；每个节点仍需遵守业务服务的权限和数据契约。'])
    svg('02-superstep.svg', '同一轮读取快照，轮末合并更新', 'A和B并行读取S0，Reducer合并两份增量得到S1，再触发后继节点。',
        [(25,120,145,'S0','本轮输入快照','#e7efff'), (230,65,170,'节点A','返回增量ΔA','#dff4ee'), (230,185,170,'节点B','返回增量ΔB','#dff4ee'), (470,120,190,'Channel.update','合并本轮写入','#fff0d9'), (735,120,195,'S1 → 下一轮','后继读取新状态','#e7efff')],
        [('M170,159 H200 V104 H230','',0,0),('M200,159 V224 H230','',0,0),('M400,104 H435 V159 H470','',0,0),('M400,224 H435 V159','',0,0),('M660,159 H735','',0,0)],
        ['节点B不能依赖本轮A尚未合并的更新；存在数据依赖就显式安排下一轮。'])
    svg('03-interrupt.svg', '审核恢复会重新进入节点', '第一次review执行到interrupt暂停，回答到达后从review开头重入，interrupt返回回答，再提交。',
        [(25,100,190,'review首次进入','interrupt抛出中断','#e7efff'), (265,100,190,'持久化待审状态','当前执行请求结束','#fff0d9'), (505,100,190,'审核请求到达','同thread + resume','#dff4ee'), (745,100,190,'review重新进入','interrupt返回回答','#e7efff')],
        [('M215,139 H265','',0,0),('M455,139 H505','',0,0),('M695,139 H745','',0,0)],
        ['业务写入安排在审核通过后的独立节点；中断前的代码可能再次执行。'])
    svg('04-idempotency.svg', '业务已提交，检查点可能尚未保存', '外部提交成功与checkpoint保存之间存在崩溃窗口；重试需要业务幂等键。',
        [(25,100,190,'节点发出请求','稳定业务幂等键','#e7efff'), (265,100,190,'业务事务提交','结果已生效','#dff4ee'), (505,100,190,'响应或进程丢失','执行方无法确认','#ffe5df'), (745,100,190,'同键重试 / 查询','返回原始业务回执','#fff0d9')],
        [('M215,139 H265','',0,0),('M455,139 H505','危险窗口',465,85),('M695,139 H745','',0,0)],
        ['Checkpoint保存图状态；业务唯一约束、幂等记录和结果查询处理外部提交窗口。'])
    svg('05-workflow.svg', '候选动作通过校验与审核后才允许写入', '抽取后规则校验，失败则拒绝，通过后等待人工审核，批准后才提交。',
        [(25,100,155,'extract','合成规则提取','#e7efff'), (225,100,155,'validate','确定性规则','#e7efff'), (430,100,155,'review','interrupt等待','#fff0d9'), (740,100,190,'submit','DEMO回执','#dff4ee'), (430,235,155,'reject','不执行业务写入','#ffe5df')],
        [('M180,139 H225','',0,0),('M380,139 H430','有效',385,125),('M585,139 H740','批准',635,125),('M302,178 V274 H430','无效',315,240),('M507,178 V235','拒绝',522,211)],
        ['示例使用固定规则与模拟提交；真实系统须在写节点校验权限、幂等与业务版本。'], 410)


def build():
    evidence = json.loads((HERE / 'source-evidence.json').read_text())
    by_id = {x['id']: x for x in evidence}
    examples = (HERE / 'examples/lab.py').read_text()
    result = json.loads((HERE / 'lab-results.json').read_text())
    def replace(match):
        kind, name = match.group(1), match.group(2)
        if kind == 'source':
            item = by_id[name]
            code = (HERE / item['file']).read_text()
            assert hashlib.sha256(code.encode()).hexdigest() == item['sha256']
            return f'源码：[{item["symbol"]} · L{item["start"]}—L{item["end"]}]({item["url"]})，固定提交`{SHA[:12]}`，完整函数。\n\n```python\n{code.rstrip()}\n```'
        if kind == 'example':
            _, _, code = function(examples, name)
            return f'示例来自[examples/lab.py](examples/lab.py)，依赖导入见该文件开头。\n\n```python\n{code.rstrip()}\n```'
        return f'```python\n{(HERE / name).read_text().rstrip()}\n```'
    sections, all_md = [], []
    for i, file in enumerate(sorted((HERE / 'chapters').glob('*.md')), 1):
        md = file.read_text()
        md = re.sub(r'\{\{(source|example|file):([^}]+)\}\}', replace, md)
        md = md.replace('{{results}}', '```json\n' + json.dumps(result, ensure_ascii=False, indent=2) + '\n```')
        all_md.append(md)
        fragment = markdown.markdown(md, extensions=['fenced_code', 'tables'])
        # h1 is the chapter title; h2 IDs support static sidebar links.
        count = [0]
        def heading(m):
            count[0] += 1
            return f'<h2 id="c{i:02d}-s{count[0]}">{m[1]}</h2>'
        fragment = re.sub(r'<h2>(.*?)</h2>', heading, fragment)
        fragment = re.sub(r'<p><img alt="([^"]*)" src="([^"]*)"\s*/></p>',
            lambda m: f'<figure class="image-diagram"><img alt="{m[1]}" src="{m[2]}" loading="lazy"><figcaption>{m[1]}</figcaption></figure>', fragment)
        sections.append(f'<section class="chapter" id="chapter-{i:02d}">{fragment}</section>')
    # Offline syntax coloring: highlight.js runs only at build time.
    plain = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="LangGraph核心机制、源码解析与工程实践：状态合并、Pregel执行、持久化、人工审核与幂等。"><title>LangGraph：核心机制、源码解析与工程实践</title><style>.image-diagram{margin:26px 0;padding:12px;border:1px solid var(--border);border-radius:8px;background:#f6f8fc}.image-diagram img{display:block;width:100%;height:auto}.image-diagram figcaption{font-size:12px;padding-top:8px;color:#526780!important}.hljs-comment,.hljs-quote{color:#718199}.hljs-keyword,.hljs-literal{color:#a347a5}.hljs-string{color:#247947}.hljs-number{color:#aa5726}[data-theme=dark] .hljs-keyword{color:#dca9ed}[data-theme=dark] .hljs-string{color:#9bcf9d}</style><script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script></head><body><header><p class="lead">从StateGraph与Channel到Pregel执行、Checkpoint、人工审核与业务幂等，沿固定源码与可运行实验理解Agent编排。</p><a href="langgraph.md">Markdown全文</a><a href="VERIFICATION.md">验证记录</a></header><main><p>固定基线：LangGraph1.2.16 · 提交' + SHA[:12] + '。资料核验与实验日期：2026年10月19日。先学状态与控制流，再读执行与恢复机制，最后运行合成受理案例。源码节选遵循MIT许可，见<a href="UPSTREAM-LICENSE.txt">上游许可</a>。</p>' + ''.join(sections) + '</main></body></html>'
    pattern = re.compile(r'<pre><code class="language-([^" ]+)">(.*?)</code></pre>', re.S)
    matches = list(pattern.finditer(plain))
    inputs = [dict(language=m[1] if m[1] in ('python', 'json') else 'bash', code=html.unescape(m[2])) for m in matches]
    highlighted = iter(json.loads(subprocess.check_output(['node', str(ROOT/'tools/highlight_source.cjs')], input=json.dumps(inputs).encode())))
    plain = pattern.sub(lambda m: f'<pre><code class="language-{m[1]}">{next(highlighted)}</code></pre>', plain)
    sys.path.insert(0, str(ROOT/'tools'))
    import style_readers
    online = style_readers.transform(plain, 'langgraph')
    (HERE/'index.html').write_text(online)
    (HERE/'langgraph.md').write_text('# LangGraph：核心机制、源码解析与工程实践\n\n基线：1.2.16，提交' + SHA + '；核验日期：2026年10月19日。\n\n' + '\n\n'.join(all_md))
    print(f'Built LangGraph: {len(sections)} chapters, {len(evidence)} full functions, 5 diagrams, 10 lab groups')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--run-labs', action='store_true')
    args = parser.parse_args()
    if args.source:
        extract(args.source)
    if args.run_labs:
        results = json.loads(subprocess.check_output([sys.executable, str(HERE/'examples/lab.py')]))
        results.update(json.loads(subprocess.check_output([sys.executable, str(HERE/'examples/sqlite_restart.py')])))
        results['verified_date'] = '2026-10-19'
        (HERE/'lab-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    diagrams()
    build()

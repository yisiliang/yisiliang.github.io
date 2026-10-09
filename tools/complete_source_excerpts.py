#!/usr/bin/env python3
"""Complete function boundaries against immutable upstream sources, then sync editions.

Uses bundled source archives first and caches SHA-addressed upstream files under
/tmp. Audit is the default; --apply updates HTML, Markdown, evidence and excerpts.
Run style_readers.py afterwards to refresh existing offline editions.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import textwrap
from urllib.request import urlopen
import zipfile

from repair_source_excerpts import PARSERS, METHODS, walk

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path('/tmp/learning-library-pinned-source')
URL = re.compile(r'https://github.com/([^/]+/[^/]+)/blob/([^/]+)/([^\s"<>)]*?)#L(\d+)-L(\d+)')
CODE = re.compile(r'<pre\b[^>]*>(?:(?!<code\b|</pre>).)*<code\b[^>]*>(.*?)</code>(?:(?!</pre>).)*</pre>', re.S)


def plain(value):
    return html.unescape(re.sub(r'<[^>]+>', '', value))


def equivalent(left, right):
    return textwrap.dedent(left).strip('\n') == textwrap.dedent(right).strip('\n')


def source(key):
    repo, sha, file = key
    target = CACHE / repo / sha / file
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(f'https://raw.githubusercontent.com/{repo}/{sha}/{file}', timeout=60) as response:
            target.write_bytes(response.read())
    data = target.read_bytes()
    lang = 'java' if file.endswith(('.java', '.java.template')) else 'cpp' if file.endswith(('.cc', '.cpp', '.hpp')) else 'c' if file.endswith(('.c', '.h')) else None
    return data.decode().splitlines(), PARSERS[lang].parse(data) if lang else None


def complete(lines, tree, start, end):
    if tree is None:
        return start, end
    nodes = list(walk(tree.root_node))
    functions = [n for n in nodes if n.type in METHODS and n.child_by_field_name('body') is not None]
    # Expand only the boundary's innermost function; field/enum/XML windows
    # remain focused on their declarations, rather than expanding whole classes.
    for point in (start, end):
        enclosing = [n for n in functions if n.start_point.row + 1 <= point <= n.end_point.row + 1]
        if enclosing:
            node = min(enclosing, key=lambda n: n.end_byte - n.start_byte)
            start = min(start, node.start_point.row + 1)
            end = max(end, node.end_point.row + 1)
    comments = [n for n in nodes if 'comment' in n.type]
    for node in comments:
        a, b = node.start_point.row + 1, node.end_point.row + 1
        if a <= start <= b:
            start = a
        if a <= end <= b:
            end = b
    # Include adjacent documentation belonging to the first declaration.
    preceding = start - 2
    while preceding >= 0 and not lines[preceding].strip():
        preceding -= 1
    leading = [n for n in comments if n.end_point.row == preceding]
    if leading:
        start = min(start, max(leading, key=lambda n: n.start_byte).start_point.row + 1)
        while start > 1 and lines[start - 2].lstrip().startswith('//'):
            start -= 1
    return start, end


def complete_bounds(lines, tree, start, end, file=''):
    if file.endswith('.ad'):
        # HotSpot architecture descriptions use nested %{ / %} bodies.
        declarations = [i for i in range(start) if lines[i].startswith('instruct ')]
        if declarations:
            start = declarations[-1] + 1
            end = next(i + 1 for i in range(end - 1, len(lines)) if lines[i].startswith('%}'))
        return start, end
    while True:
        new = complete(lines, tree, start, end)
        if new == (start, end):
            return new
        start, end = new


def replace_document(text, updates, markdown=False):
    pattern = re.compile(r'```(?:java|c|cpp)\n(.*?)\n```', re.S) if markdown else CODE
    replacements = []
    highlight_payload = []
    for match in pattern.finditer(text):
        links = list(URL.finditer(text[:match.start()]))
        if not links:
            continue
        link = links[-1]
        key = tuple(link.groups())
        change = updates.get(key)
        if not change:
            continue
        old, new, start, end = change
        code = match[1] if markdown else plain(match[1])
        if not equivalent(code, old):
            continue
        # Preserve each edition's original indentation and trailing newline.
        rendered = textwrap.dedent(new) if code.lstrip('\n').startswith(old.lstrip('\n').lstrip()) and not code.lstrip('\n').startswith(old.lstrip('\n')) else new
        extra_newlines = (len(code) - len(code.rstrip('\n'))) - (len(old) - len(old.rstrip('\n')))
        rendered += '\n' * max(0, extra_newlines)
        segment = text[link.start():match.end()]
        a, b = map(int, key[-2:])
        segment = segment.replace(f'#L{a}-L{b}', f'#L{start}-L{end}').replace(f'L{a}–L{b}', f'L{start}–L{end}').replace(f'L{a}—L{b}', f'L{start}—L{end}')
        relative_start = match.start(1) - link.start()
        # Recompute code offsets after the citation's line digits change.
        offset = len(segment) - len(text[link.start():match.end()])
        if markdown:
            markup = rendered
        else:
            language = 'java' if key[2].endswith(('.java', '.java.template')) else 'c' if key[2].endswith('.c') else 'cpp'
            markup = f'__SOURCE_COMPLETION_HIGHLIGHT_{len(highlight_payload)}__'
            highlight_payload.append(dict(language=language, code=rendered))
        segment = segment[:relative_start + offset] + markup + segment[match.end(1) - link.start() + offset:]
        # HTML line-number gutters live between citation and code.
        if not markdown:
            segment = re.sub(r'(<pre class="gutter"[^>]*>).*?(</pre>)', lambda m: m[1] + '\n'.join(map(str, range(start, end + 1))) + m[2], segment, flags=re.S)
        label_start = text.rfind('[', 0, link.start()) if markdown and text[:link.start()].endswith('](') else link.start()
        if label_start == link.start():
            caption = text.rfind('<div class="source-caption">', 0, link.start())
            if caption >= 0 and '</div>' not in text[caption:link.start()]:
                label_start = caption
        prefix = text[label_start:link.start()].replace(f'L{a}–L{b}', f'L{start}–L{end}').replace(f'L{a}—L{b}', f'L{start}—L{end}')
        replacements.append((label_start, match.end(), prefix + segment))
    for start, end, value in reversed(replacements):
        text = text[:start] + value + text[end:]
    if highlight_payload:
        highlighted = json.loads(subprocess.run(['node', str(ROOT/'tools/highlight_source.cjs')], input=json.dumps(highlight_payload), text=True, capture_output=True, check=True).stdout)
        for i, markup in enumerate(highlighted):
            text = text.replace(f'__SOURCE_COMPLETION_HIGHLIGHT_{i}__', markup)
    return text, len(replacements)


def update_evidence(folder, updates):
    # Existing generators must retain the completed ranges on regeneration.
    for path in folder.glob('*.json'):
        data = json.loads(path.read_text())
        changed = False
        def visit(value):
            nonlocal changed
            if isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                for key, (old, new, start, end) in updates.items():
                    repo, sha, file, a, b = key
                    if value.get('line') == int(a) and value.get('end_line') == int(b) and value.get('url') == f'https://raw.githubusercontent.com/{repo}/{sha}/{file}':
                        value.update(line=start, end_line=end, excerpt=new+'\n')
                        changed = True
                        break  # sha256 here identifies the complete upstream file.
                    if value.get('start') == int(a) and value.get('end') == int(b) and value.get('sha', sha) == sha and (value.get('path') == file or value.get('file') == file or value.get('url') == f'https://github.com/{repo}/blob/{sha}/{file}#L{a}-L{b}' or (folder.name == 'nginx-rate-limiting' and file == 'src/http/modules/ngx_http_limit_req_module.c')):
                        value.update(start=start, end=end)
                        if 'url' in value:
                            value['url'] = f'https://github.com/{repo}/blob/{sha}/{file}#L{start}-L{end}'
                        if 'text' in value:
                            value['text'] = new
                        local = value.get('excerpt') or (value.get('file') if str(value.get('file', '')).startswith('excerpts/') else None)
                        content = new + ('\n' if local or value.get('sha256') == hashlib.sha256((old+'\n').encode()).hexdigest() else '')
                        if local:
                            (folder/local).write_text(content)
                        if 'sha256' in value:
                            value['sha256'] = hashlib.sha256(content.encode()).hexdigest()
                        changed = True
                        break
                for item in value.values():
                    if isinstance(item, (dict, list)):
                        visit(item)
        visit(data)
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    catalog = json.loads((ROOT/'tools/homepage/catalog.json').read_text())
    folders = [ROOT/'docs'/book['path'] for group in catalog for book in group['books']]
    keys = set()
    for folder in folders:
        keys.update(tuple(m.groups()[:3]) for m in URL.finditer((folder/'index.html').read_text()))
    CACHE.mkdir(parents=True, exist_ok=True)
    # Seed cache from the three already bundled, immutable source archives.
    for folder in folders:
        for archive in folder.glob('*source.zip'):
            with zipfile.ZipFile(archive) as z:
                for repo, sha, file in keys:
                    candidates = [n for n in z.namelist() if n == file or n.endswith('/' + file)]
                    for name in candidates:
                        data = z.read(name)
                        # Different version prefixes are selected by exact old windows.
                        citations = [m for m in URL.finditer((folder/'index.html').read_text()) if tuple(m.groups()[:3]) == (repo, sha, file)]
                        if citations and all(equivalent('\n'.join(data.decode().splitlines()[int(m[4])-1:int(m[5])]), plain(CODE.search((folder/'index.html').read_text(), m.end())[1])) for m in citations):
                            target = CACHE/repo/sha/file
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(data)
                            break
    with ThreadPoolExecutor(max_workers=8) as pool:
        sources = dict(zip(sorted(keys), pool.map(source, sorted(keys))))
    report = []
    for folder in folders:
        text = (folder/'index.html').read_text()
        documents = [text]
        archives = {}
        for archive in folder.glob('*offline*.zip'):
            with zipfile.ZipFile(archive) as z:
                archives[archive] = [(i, z.read(i.filename)) for i in z.infolist()]
            documents.extend(data.decode() for i, data in archives[archive] if i.filename.endswith('.html'))
        documents.extend(path.read_text() for path in folder.glob('offline*.html'))
        updates = {}
        audited = 0
        markdown_sources = {}
        handbook = folder/'handbook.md'
        if handbook.exists():
            markdown = handbook.read_text()
            for block in re.finditer(r'```(?:java|c|cpp)\n(.*?)\n```', markdown, re.S):
                links = list(URL.finditer(markdown[:block.start()]))
                if links:
                    markdown_sources.setdefault(tuple(links[-1].groups()), []).append(block[1])
        for edition, document in enumerate(documents):
            for match in CODE.finditer(document):
                links = list(URL.finditer(document[:match.start()]))
                if not links:
                    continue
                link = links[-1]
                repo, sha, file, a, b = link.groups()
                lines, tree = sources[(repo, sha, file)]
                start, end = int(a), int(b)
                old = '\n'.join(lines[start-1:end])
                if not equivalent(plain(match[1]), old):
                    continue  # Teaching examples are not upstream source excerpts.
                if edition == 0:
                    audited += 1
                    if not args.apply and handbook.exists():
                        assert any(equivalent(old, block) for block in markdown_sources.get(tuple(link.groups()), [])), (folder.name, file, start, end, 'Markdown/source mismatch')
                na, nb = complete_bounds(lines, tree, start, end, file)
                if (na, nb) != (start, end):
                    new = '\n'.join(lines[na-1:nb])
                    updates[tuple(link.groups())] = old, new, na, nb
                    if edition == 0:
                        report.append(dict(book=folder.name, file=file, old=[start,end], new=[na,nb]))
        print(folder.name, 'audited', audited, 'changed', len(updates), flush=True)
        if args.apply and updates:
            for path in [folder/'index.html', *folder.glob('offline*.html'), *folder.glob('*.md')]:
                original = path.read_text()
                rendered, count = replace_document(original, updates, path.suffix == '.md')
                if rendered != original:
                    path.write_text(rendered)
            update_evidence(folder, updates)
            for archive, entries in archives.items():
                with zipfile.ZipFile(archive, 'w') as z:
                    for info, data in entries:
                        if info.filename.endswith('.html'):
                            data = replace_document(data.decode(), updates)[0].encode()
                        z.writestr(info, data)
    if args.apply and report:
        path = ROOT/'tools/source-completion-report.json'
        existing = json.loads(path.read_text()) if path.exists() else []
        path.write_text(json.dumps(existing + report, ensure_ascii=False, indent=2)+'\n')
    print('Total source blocks needing completion:', len(report))


if __name__ == '__main__':
    main()

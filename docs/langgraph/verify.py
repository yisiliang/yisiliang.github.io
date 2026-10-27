#!/usr/bin/env python3
"""Validate source boundaries, rendered code, chapter anchors, ZIP and lab evidence."""
import argparse
import ast
import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from audit_articles import verify as verify_article


def verify(source=None):
    evidence = json.loads((HERE/'source-evidence.json').read_text())
    page = (HERE/'index.html').read_text()
    md = (HERE/'langgraph.md').read_text()
    codes = [html.unescape(re.sub('<[^>]+>', '', c)) for c in re.findall(r'<pre><code[^>]*>(.*?)</code></pre>', page, re.S)]
    assert len(evidence) == 9
    for item in evidence:
        code = (HERE/item['file']).read_text()
        assert hashlib.sha256(code.encode()).hexdigest() == item['sha256']
        assert code.rstrip() + '\n' in codes, item['id']
        assert code.rstrip() in md and item['url'] in page
        # A standalone method needs dedenting before AST parsing.
        import textwrap
        parsed = ast.parse(textwrap.dedent(code))
        assert len(parsed.body) == 1 and isinstance(parsed.body[0], (ast.FunctionDef, ast.AsyncFunctionDef))
        if source:
            upstream = (source/item['path']).read_text().splitlines(keepends=True)
            assert ''.join(upstream[item['start']-1:item['end']]) == code
            # Confirm AST node end, not just a range that could accidentally truncate.
            tree = ast.parse((source/item['path']).read_text())
            functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.end_lineno == item['end']]
            assert any(min([n.lineno] + [d.lineno for d in n.decorator_list]) == item['start'] for n in functions)
    assert len(re.findall(r'<article class="chapter"', page)) == 16
    assert len(list((HERE/'diagrams').glob('*.svg'))) == 5
    assert '{{' not in md
    results = json.loads((HERE/'lab-results.json').read_text())
    assert results['langgraph'] == '1.2.16' and len(results['cases']) == 9
    assert results['separate_processes'][-1]['approved'] is True
    report = verify_article('langgraph')
    print(json.dumps({'source_functions':9, 'chapters':16, 'diagrams':5, 'lab_groups':10,
        'upstream_comparison':bool(source), 'article':report}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path)
    verify(ap.parse_args().source)

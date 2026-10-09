"""Verify JIT source windows against the pinned upstream commit and generated text."""
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
COMMIT = '943a5ea328fd2fc8eed0aed4ec9b1957d41f8144'
sources = json.loads((ROOT / 'sources.json').read_text())
page = BeautifulSoup((ROOT / 'index.html').read_text(), 'html.parser')
article = page.select_one('#c11 .study')
handbook = (ROOT / 'handbook.md').read_text()
cache, checks = {}, []
for key, source in sources.items():
    if not key.startswith('jit'):
        continue
    url = source['url']
    assert f'/{COMMIT}/' in url, (key, 'unpinned source')
    if url not in cache:
        cache[url] = urlopen(url, timeout=30).read()
    data = cache[url]
    assert hashlib.sha256(data).hexdigest() == source['sha256'], (key, 'file digest')
    excerpt = ''.join(data.decode().splitlines(keepends=True)[source['line'] - 1:source['end_line']])
    assert excerpt == source['excerpt'], (key, 'source window')
    assert excerpt.rstrip('\n') in handbook, (key, 'Markdown window')
    assert any(code.get_text().rstrip('\n') == excerpt.rstrip('\n')
               for code in article.select('pre code')), (key, 'HTML window')
    checks.append({'key': key, 'line': source['line'], 'end_line': source['end_line'],
                   'sha256': source['sha256'], 'status': 'PASS'})
assert len(checks) == 7, 'JIT source count'
report = {'commit': COMMIT, 'checks': checks, 'scope': 'Pinned source bytes and generated windows; not runtime machine-code verification.'}
(ROOT / 'jit-source-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('PASS: 7 pinned JIT source windows match upstream, Markdown and HTML')

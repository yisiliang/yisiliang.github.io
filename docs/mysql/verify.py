#!/usr/bin/env python3
"""Static verification. Optional argument: MySQL source checkout for exact excerpt proof."""
from pathlib import Path
import re,json,hashlib,sys,zipfile
r=Path(__file__).resolve().parent;p=(r/'index.html').read_text();md=(r/'handbook.md').read_text();meta=json.loads((r/'metadata.json').read_text());manifest=json.loads((r/'source-manifest.json').read_text())
assert len(re.findall(r'<section id="chapter-\d+"',p))==meta['chapters']==27
assert len(list((r/'diagrams').glob('*.svg')))==meta['diagrams']==27
assert len(manifest)==meta['excerpts']==30
assert p.count('cloud.umami.is/script.js')==1
assert p.count('data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"')==1
assert '/Users/' not in p and '/tmp/' not in p
ids=re.findall(r'\bid="([^"]+)"',p);assert len(ids)==len(set(ids)), 'duplicate DOM IDs'
for target in re.findall(r'(?:href="#|aria-labelledby="|url\(#)([^"\)]+)',p):assert target in ids,target
for link in re.findall(r'href="([^"]+)"',p):
 if not link.startswith(('https:','http:','#','../')):assert (r/link).exists(),link
for entry in manifest:
 text=(r/entry['excerpt']).read_text();assert hashlib.sha256(text.encode()).hexdigest()==entry['sha256']
 assert text.count('/*')==text.count('*/'),entry['excerpt']
 if len(sys.argv)>1:
  lines=(Path(sys.argv[1])/entry['file']).read_text().splitlines();expected='\n'.join(lines[entry['start']-1:entry['end']])+'\n';assert text==expected,entry['excerpt']
 assert entry['url'] in p and entry['url'] in md
with zipfile.ZipFile(r/'mysql-offline.zip') as z:
 assert z.testzip() is None
 q=z.read('index.html').decode();assert 'umami' not in q.lower();assert not re.search(r'<script[^>]+src=',q)
 assert len(re.findall(r'<section id="chapter-\d+"',q)) == meta['chapters']
 assert len(re.findall(r'<pre\b',q)) == meta['excerpts']
print(json.dumps({'chapters':27,'diagrams':27,'excerpts':30,'unique_dom_ids':len(ids),'exact_source_checked':len(sys.argv)>1,'offline_integrity':'PASS'},ensure_ascii=False))

#!/usr/bin/env python3
"""Verify frozen excerpts/assets; optional argv[1] is the matching NGINX checkout."""
from pathlib import Path
from html.parser import HTMLParser
import re,json,hashlib,sys,xml.etree.ElementTree as ET,zipfile
root=Path(__file__).resolve().parent
meta=json.loads((root/'metadata.json').read_text())
evidence=json.loads((root/'source-evidence.json').read_text())
md=(root/'handbook.md').read_text();code=re.findall(r'```c\n(.*?)\n```',md,re.S)
assert len(code)==len(evidence)==meta['excerpts']==24
assert len(re.findall(r'^# \d\d · ',md,re.M))==meta['chapters']==24
for text,e in zip(code,evidence):
 assert hashlib.sha256(text.encode()).hexdigest()==e['sha256'],e
 if len(sys.argv)>1:
  f=Path(sys.argv[1])/e['file'];lines=f.read_text().splitlines()
  assert text=='\n'.join(lines[e['start']-1:e['end']]),e
class Check(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.anchors=[];self.local=[];self.markers=[];self.figures=0;self.sections=0;self.pre=0;self.scripts=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  if tag=='figure':self.figures+=1
  if tag=='section' and a.get('class')=='chapter':self.sections+=1
  if tag=='pre':self.pre+=1
  if tag=='a':
   h=a.get('href','')
   if h.startswith('#'):self.anchors.append(h[1:])
   elif h.startswith('./'):self.local.append(h[2:])
  if tag=='script' and 'src' in a:self.scripts.append(a['src'])
  if 'marker-end' in a:self.markers.append(a['marker-end'][5:-1])
for name in (['index.html','offline-index.html'] if (root/'offline-index.html').exists() else ['index.html']):
 c=Check();c.feed((root/name).read_text())
 assert len(c.ids)==len(set(c.ids)),f'duplicate ids: {name}'
 assert all(a in c.ids for a in c.anchors)
 assert all(m in c.ids for m in c.markers)
 assert c.sections==c.figures==c.pre==24
 assert all((root/a).exists() for a in c.local),c.local
 if name=='offline-index.html' or 'data-website-id=' not in (root/name).read_text():assert not c.scripts
 else:assert c.scripts==['https://cloud.umami.is/script.js']
for path in sorted((root/'diagrams').glob('*.svg')):ET.parse(path)
assert len(list((root/'diagrams').glob('*.svg')))==meta['diagrams']==24
if (root/'nginx-offline.zip').exists():
 with zipfile.ZipFile(root/'nginx-offline.zip') as z:
  assert z.testzip() is None
  names=z.namelist();assert 'nginx-source-notes/index.html' in names
  content=z.read('nginx-source-notes/index.html').decode()
  offline=Check();offline.feed(content)
  assert all('nginx-source-notes/'+x in names for x in offline.local),offline.local
  assert 'cloud.umami.is' not in content and 'data-website-id' not in content
  for name in ['nginx-license.txt','source-notices.txt','handbook.md','experiments.md','lab-backend.py','lab-nginx.conf','VERIFICATION.md']:
   assert 'nginx-source-notes/'+name in names,name
print('PASS: 24 chapters / 24 diagrams / 24 original excerpts; anchors, IDs, SVG, resources, ZIP and tracker isolation')
if len(sys.argv)>1:print('PASS: all 24 excerpts exactly match supplied source checkout')

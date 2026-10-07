"""Build self-contained reading / teaching archives; never include target outputs."""
from pathlib import Path
import re,zipfile,json
ROOT=Path(__file__).resolve().parent
tracker='<script defer src="https://cloud.umami.is/script.js" data-website-id="8c64c0bf-97e7-4af5-a5bf-f090c52fc4d3"></script>'
page=(ROOT/'index.html').read_text()
assert page.count(tracker)==1
page=page.replace(tracker,'').replace('href="../"','href="#"').replace('href="./springboot-offline.zip"','href="./阅读说明.txt"')
assert 'cloud.umami.is' not in page
examples=[p for p in (ROOT/'examples').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT).parts]
with zipfile.ZipFile(ROOT/'springboot-examples.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in examples:z.write(p,p.relative_to(ROOT))
 z.write(ROOT/'apache-license.txt','apache-license.txt')
with zipfile.ZipFile(ROOT/'springboot-offline.zip','w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('index.html',page)
 for name in ['handbook.md','metadata.json','source-manifest.json','source-notices.txt','apache-license.txt','framework-license.txt','VERIFICATION.md','experiment-results.json','validation-results.json','chapters.json','springboot-examples.zip']:
  z.write(ROOT/name,name)
 for p in examples:z.write(p,p.relative_to(ROOT))
 z.writestr('阅读说明.txt','解压后打开index.html。正文、SVG图解、搜索和主题自包含，无统计脚本；点击源码外链才联网。Maven实验首次执行需要联网下载依赖。\n')
# Downloads in the offline page must stay local and available; links to its own ZIP
# are replaced with this offline readme rather than nesting the archive recursively.
with zipfile.ZipFile(ROOT/'springboot-offline.zip') as z:
 assert 'cloud.umami.is' not in z.read('index.html').decode()
 assert all('target/' not in n for n in z.namelist())
print(json.dumps({'offline_bytes':(ROOT/'springboot-offline.zip').stat().st_size,'examples_bytes':(ROOT/'springboot-examples.zip').stat().st_size}))

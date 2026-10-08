#!/usr/bin/env python3
"""Build a deterministic, self-contained, tracker-free teaching package."""
from pathlib import Path
import zipfile
import re
ROOT=Path(__file__).resolve().parent
page=(ROOT/'index.html').read_text()
page=re.sub(r'<script[^>]+src="https://cloud\.umami\.is/script\.js"[^>]*></script>', '', page)
page=page.replace('<a href="./transformer-offline.zip" download>下载离线阅读包 ↓</a>','')
page=page.replace('href="../"','href="https://yisiliang.github.io/"')
assert 'umami' not in page and '<script defer src="./attention.js">' in page
with zipfile.ZipFile(ROOT/'transformer-offline.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['index.html','style.css','attention.js','verify.py']:
        data=page if name=='index.html' else (ROOT/name).read_text()
        info=zipfile.ZipInfo(name,date_time=(2026,10,8,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,data)
print('Built transformer-offline.zip: HTML, CSS, interactive calculator, numeric verifier')

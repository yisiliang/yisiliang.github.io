#!/usr/bin/env python3
"""Package the CAP/BASE article with local CSS and no analytics."""
from pathlib import Path
import re
import zipfile
ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'docs/distributed'
page = (folder / 'index.html').read_text()
page = re.sub(r'<script[^>]+src="https://cloud\.umami\.is/script\.js"[^>]*></script>', '', page)
page = page.replace('<a href="./cap-base-offline.zip" download>下载离线阅读包 ↓</a>', '')
page = page.replace('href="../"', 'href="https://yisiliang.github.io/"')
for target in ('nacos', 'rocketmq', 'redis'):
    page = page.replace(f'href="../{target}/"', f'href="https://yisiliang.github.io/{target}/"')
with zipfile.ZipFile(folder / 'cap-base-offline.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for name, content in (('index.html', page), ('style.css', (folder / 'style.css').read_text())):
        entry = zipfile.ZipInfo(name, date_time=(2026, 10, 8, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(entry, content)
print('Built CAP/BASE offline archive')

#!/usr/bin/env python3
"""Add shared discovery metadata to every public content page.

The block is idempotent and is inserted after the page's own <head> content, so
reader generators can rebuild bodies without losing descriptions or social cards.
Also regenerates sitemap.xml, robots.txt, favicon and the default share image.
"""
from pathlib import Path
import html, json, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
SITE = 'https://yisiliang.github.io'
TOPICS = json.loads((DOCS / 'topics/topics.json').read_text())
CATALOG = json.loads((ROOT / 'tools/homepage/catalog.json').read_text())
SITE_NAME = '源码之下，系统之上'
OG_IMAGE = f'{SITE}/assets/og-default.png'

DESCRIPTIONS = {
    'jvm': '深入理解Java虚拟机：76章图解HotSpot JDK8的内存结构、垃圾回收、类加载与执行引擎，附XStream实例与CMS附录。',
}

BLOCK_START = '<!-- social-meta:start -->'
BLOCK_END = '<!-- social-meta:end -->'


def clean(text):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', text))).strip()


def page_info():
    pages = []
    pages.append({'file': DOCS / 'index.html', 'url': '/', 'type': 'website'})
    for group in CATALOG:
        for book in group['books']:
            if group.get('layout') == 'topics':
                continue
            pages.append({'file': DOCS / book['path'] / 'index.html',
                          'url': f'/{book["path"]}/', 'type': 'article'})
    pages.append({'file': DOCS / 'topics/index.html', 'url': '/topics/', 'type': 'website',
                  'description': '技术专题：14 篇独立长文，覆盖 Java 并发、JVM、Spring、数据库、RocketMQ、Redis、分布式事务、稳定性、JIT 与 Nginx 限流。'})
    for topic in TOPICS:
        pages.append({'file': DOCS / 'topics' / topic['slug'] / 'index.html',
                      'url': f'/topics/{topic["slug"]}/', 'type': 'article',
                      'description': topic['summary']})
    return pages


def metadata_block(title, description, url, og_type):
    tags = [
        f'<link rel="canonical" href="{SITE}{url}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        '<meta property="og:locale" content="zh_CN">',
        f'<meta property="og:title" content="{html.escape(title, quote=True)}">',
        f'<meta property="og:description" content="{html.escape(description, quote=True)}">',
        f'<meta property="og:url" content="{SITE}{url}">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{html.escape(title, quote=True)}">',
        f'<meta name="twitter:description" content="{html.escape(description, quote=True)}">',
        f'<meta name="twitter:image" content="{OG_IMAGE}">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        '<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
    ]
    return BLOCK_START + ''.join(tags) + BLOCK_END


def inject(info):
    path = info['file']
    raw = path.read_text()
    head, sep, rest = raw.partition('</head>')
    if not sep:
        raise ValueError(f'no head: {path}')
    title_match = re.search(r'<title>(.*?)</title>', head, re.S)
    if not title_match:
        raise ValueError(f'no title: {path}')
    title = clean(title_match.group(1))
    desc_tags = re.findall(r'<meta\b[^>]*name="description"[^>]*>', head, flags=re.I)
    description = ''
    for tag in desc_tags:
        value = re.search(r'content="([^"]*)"', tag, flags=re.I)
        if value:
            description = clean(value.group(1))
            break
    if not description:
        description = info.get('description') or DESCRIPTIONS.get(path.parent.name)
    if not description:
        raise ValueError(f'no description: {path}')
    head = re.sub(r'<meta\b[^>]*name="description"[^>]*>\s*', '', head, flags=re.I)
    head = head.replace('<title>', f'<meta name="description" content="{html.escape(description, quote=True)}">\n<title>', 1)
    head = re.sub(re.escape(BLOCK_START) + r'.*?' + re.escape(BLOCK_END), '', head, flags=re.S)
    # Drop previously hand-written duplicate discovery tags, keeping the page body intact.
    head = re.sub(r'<link\b[^>]*rel="canonical"[^>]*>', '', head)
    head = re.sub(r'<meta\b[^>]*property="og:[^"]*"[^>]*>', '', head)
    head = re.sub(r'<meta\b[^>]*name="twitter:[^"]*"[^>]*>', '', head)
    head = re.sub(r'<link\b[^>]*rel="(?:icon|apple-touch-icon)"[^>]*>', '', head)
    block = metadata_block(title, description, info['url'], info.get('type', 'article'))
    head = head.rstrip() + '\n' + block + '\n'
    path.write_text(head + sep + rest)
    return title, description


def git_date(path):
    try:
        return subprocess.check_output(['git', 'log', '-1', '--format=%cs', '--', str(path)],
                                       cwd=ROOT, text=True).strip() or '2026-10-27'
    except Exception:
        return '2026-10-27'


def write_sitemap(pages):
    entries = []
    for info in pages:
        entries.append(f'  <url><loc>{SITE}{info["url"]}</loc>'
                       f'<lastmod>{git_date(info["file"])}</lastmod></url>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + '\n'.join(entries) + '\n</urlset>\n')
    (DOCS / 'sitemap.xml').write_text(xml)
    (DOCS / 'robots.txt').write_text(
        'User-agent: *\nAllow: /\n\nSitemap: ' + SITE + '/sitemap.xml\n')


FAVICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#131820"/>
<path d="M25 18 12 32l13 14" fill="none" stroke="#8ab7ff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M39 18l13 14-13 14" fill="none" stroke="#8ab7ff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="32" cy="32" r="4.5" fill="#75ccb9"/>
</svg>
'''


def draw_icon(size, path):
    from PIL import Image, ImageDraw
    scale = 4
    canvas = Image.new('RGBA', (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    radius = int(size * scale * 0.22)
    draw.rounded_rectangle([0, 0, size * scale - 1, size * scale - 1], radius=radius, fill='#131820')
    w = int(size * scale * 0.075)
    accent = '#8ab7ff'
    left = [(int(size * scale * .38), int(size * scale * .30)), (int(size * scale * .20), int(size * scale * .50)),
            (int(size * scale * .38), int(size * scale * .70))]
    right = [(int(size * scale * .62), int(size * scale * .30)), (int(size * scale * .80), int(size * scale * .50)),
             (int(size * scale * .62), int(size * scale * .70))]
    draw.line(left, fill=accent, width=w, joint='curve')
    draw.line(right, fill=accent, width=w, joint='curve')
    r = int(size * scale * .055)
    cx = cy = int(size * scale * .5)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#75ccb9')
    canvas.resize((size, size), Image.LANCZOS).save(path)


def draw_og(path):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    image = Image.new('RGB', (W, H), '#0f1722')
    draw = ImageDraw.Draw(image)
    for y in range(H):
        shade = int(15 + 10 * y / H)
        draw.line([(0, y), (W, y)], fill=(shade, shade + 5, shade + 12))
    draw.rectangle([0, 0, 8, H], fill='#75ccb9')
    bold = '/System/Library/Fonts/Hiragino Sans GB.ttc'
    font_title = ImageFont.truetype(bold, 78, index=1)
    font_sub = ImageFont.truetype(bold, 30, index=0)
    font_small = ImageFont.truetype(bold, 22, index=0)
    draw.text((92, 150), '源码之下，', font=font_title, fill='#eef4fb')
    draw.text((92, 248), '系统之上。', font=font_title, fill='#8ab7ff')
    draw.text((96, 374), '从源码出发，理解系统。', font=font_sub, fill='#b9c6d6')
    draw.text((96, 430), 'JDK · JVM · Spring · MySQL · Redis · RocketMQ · Nginx · AI · 技术专题', font=font_small, fill='#7f90a5')
    draw.text((96, 540), 'YiSiliang  ·  yisiliang.github.io', font=font_small, fill='#75ccb9')
    image.save(path, 'PNG')


def write_assets():
    (DOCS / 'favicon.svg').write_text(FAVICON_SVG)
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print('Pillow unavailable: skipped PNG favicon and share image')
        return
    (DOCS / 'assets').mkdir(exist_ok=True)
    draw_icon(32, DOCS / 'favicon-32.png')
    draw_icon(180, DOCS / 'apple-touch-icon.png')
    draw_og(DOCS / 'assets/og-default.png')


def main():
    pages = page_info()
    for info in pages:
        title, description = inject(info)
        print(f'{info["url"]:<38} {title}')
    write_sitemap(pages)
    write_assets()
    print(f'{len(pages)} pages, sitemap.xml, robots.txt, favicon and share image written')


if __name__ == '__main__':
    main()

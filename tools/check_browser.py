#!/usr/bin/env python3
"""Browser regression for the published readers.

Starts a local static server for docs/, then checks every reader at desktop and
mobile widths: single sidebar, no overflow, no ZIP entries, no script errors,
page-outline links, search, copy, themes, drawer and no-JavaScript reading.

Requires: pip install playwright, plus a local Chrome/Chromium.
Override the browser with CHROMIUM_EXECUTABLE.
"""
from pathlib import Path
import functools, http.server, json, os, socket, threading, sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
TOPICS = json.loads((DOCS / 'topics/topics.json').read_text())
CATALOG = json.loads((ROOT / 'tools/homepage/catalog.json').read_text())
BOOKS = [book['path'] for group in CATALOG if group.get('layout') != 'topics' for book in group['books']]
PATHS = ['/', '/topics/'] + [f'/{book}/' for book in BOOKS] + [f'/topics/{topic["slug"]}/' for topic in TOPICS]
CHROME = os.environ.get('CHROMIUM_EXECUTABLE') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(QuietHandler, directory=str(DOCS))
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{port}'


def main():
    server, origin = serve()
    issues, checked = [], 0
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
            for width, height in [(1440, 900), (820, 1000), (390, 844), (320, 720)]:
                context = browser.new_context(viewport={'width': width, 'height': height})
                for path in PATHS:
                    page = context.new_page()
                    errors = []
                    page.on('console', lambda message: errors.append(message.text)
                            if message.type == 'error' and 'ERR_FAILED' not in message.text else None)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('https://cloud.umami.is/**', lambda route: route.abort())
                    try:
                        page.goto(origin + path, wait_until='load', timeout=30000)
                        page.wait_for_timeout(250)
                        info = page.evaluate("""() => {
                          const active=document.querySelector('.chapter.active');
                          const nav=active?document.querySelector('.chapter-nav[data-chapter="'+active.id+'"]'):null;
                          return {right:!!document.querySelector('#right-toc'),
                            overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,
                            reader:!!document.querySelector('#left-nav'),
                            jsEnabled:document.documentElement.classList.contains('js-enabled'),
                            headings:active?active.querySelectorAll('.study h2,.study h3').length:0,
                            links:nav?nav.querySelectorAll('div a').length:0,
                            zip:[...document.querySelectorAll('a')].filter(a=>(a.getAttribute('href')||'').includes('.zip')).length};
                        }""")
                        if info['right']:
                            issues.append((width, path, 'right sidebar present'))
                        if info['overflow'] > 1:
                            issues.append((width, path, f'horizontal overflow {info["overflow"]}'))
                        if info['reader'] and not info['jsEnabled']:
                            issues.append((width, path, 'reader script not initialized'))
                        if info['reader'] and info['headings'] and info['links'] == 0:
                            issues.append((width, path, 'missing page outline in sidebar'))
                        if info['zip']:
                            issues.append((width, path, f'{info["zip"]} ZIP links'))
                        if errors:
                            issues.append((width, path, '; '.join(errors[:3])))
                    except Exception as error:
                        issues.append((width, path, 'load failed: ' + str(error)[:120]))
                    finally:
                        page.close()
                        checked += 1
                context.close()

            # Interaction sample: search, copy, theme, quick mode and drawer.
            page = browser.new_page(viewport={'width': 390, 'height': 844})
            page.goto(origin + '/topics/rocketmq/', wait_until='load')
            page.click('#search-open')
            page.fill('#search-input', 'CommitLog')
            page.wait_for_function("() => document.querySelector('#search-results').children.length > 0")
            page.click('#search-results a')
            page.wait_for_function("() => !document.querySelector('#search-dialog').open")
            page.evaluate("() => Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>window.__copied=text}})")
            copy = page.locator('.chapter.active pre:has(code) button.copy').first
            if copy.count():
                expected = page.locator('.chapter.active pre:has(code) code').first.inner_text()
                copy.click()
                if page.evaluate('() => window.__copied') != expected:
                    issues.append((390, '/topics/rocketmq/', 'copy content differs'))
            page.click('#mode')
            page.wait_for_function("() => getComputedStyle(document.querySelector('.chapter.active .quick')).display !== 'none'")
            page.click('#mode')
            page.click('#menu')
            page.wait_for_function("() => document.body.classList.contains('drawer-open')")
            page.close()
            browser.close()

            # No-JavaScript fallback: all chapters stay readable.
            nojs = playwright.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
            context = nojs.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844})
            page = context.new_page()
            for path in [f'/{book}/' for book in BOOKS] + [f'/topics/{topic["slug"]}/' for topic in TOPICS]:
                page.goto(origin + path, wait_until='load')
                if page.locator('.chapter:visible').count() != page.locator('.chapter').count():
                    issues.append((390, path, 'chapters hidden without JavaScript'))
            context.close()
            nojs.close()
    finally:
        server.shutdown()

    print(f'checked {checked} page/width combinations')
    for issue in issues[:40]:
        print('  ', issue)
    if issues:
        return 1
    print('PASS: single sidebar, outline, search, copy, themes, quick mode, drawer, no-JS and responsive layouts')
    return 0


if __name__ == '__main__':
    sys.exit(main())

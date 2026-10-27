#!/usr/bin/env python3
"""Pre-render Mermaid diagrams inside every standalone topic page.

Mermaid 10.9.3 is loaded once from tools/vendor; readers never download or run it.
The script is idempotent: pages whose diagrams are already rendered are skipped.
"""
from pathlib import Path
import json, os, re, sys

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT.parent.parent / 'tools'
MERMAID = TOOLS / 'vendor' / 'mermaid.min.js'
CHROME = os.environ.get('CHROMIUM_EXECUTABLE') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TOPICS = json.loads((ROOT / 'topics.json').read_text())


def main():
    report = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME, headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        page.set_content('<!doctype html><html><body></body></html>')
        page.add_script_tag(path=str(MERMAID))
        page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',themeVariables:{primaryColor:'#e8eef8',primaryTextColor:'#182338',primaryBorderColor:'#7890af',lineColor:'#72849a',secondaryColor:'#edf2f7',tertiaryColor:'#f4f6f9',fontFamily:'sans-serif'},flowchart:{htmlLabels:false,useMaxWidth:true}})")
        for topic in TOPICS:
            path = ROOT / topic['slug'] / 'index.html'
            soup = BeautifulSoup(path.read_text(), 'html.parser')
            pending = soup.select('.diagram[data-diagram] > pre.mermaid')
            if not pending:
                continue
            for figure in soup.select('.diagram[data-diagram]'):
                source = figure.select_one('pre.mermaid')
                if not source:
                    continue
                diagram_id = f'jai-diagram-{figure["data-diagram"]}'
                raw = source.get_text()
                svg = page.evaluate('''async ({id,raw}) => {const r=await mermaid.render(id,raw);return r.svg;}''',
                                    {'id': diagram_id, 'raw': raw})
                parsed = BeautifulSoup(svg, 'html.parser')
                idmap = {el['id']: diagram_id + '-' + el['id'] for el in parsed.select('[id]')}
                for el in parsed.select('[id]'):
                    el['id'] = idmap[el['id']]
                serialized = str(parsed)
                pattern = re.compile('#(' + '|'.join(re.escape(old) for old in sorted(idmap, key=len, reverse=True)) + r')(?=$|[^\w-])')
                serialized = pattern.sub(lambda match: '#' + idmap[match[1]], serialized)
                parsed = BeautifulSoup(serialized, 'html.parser')
                for el in parsed.select('[aria-labelledby],[aria-describedby]'):
                    for attr in ['aria-labelledby', 'aria-describedby']:
                        if el.has_attr(attr):
                            el[attr] = ' '.join(idmap.get(x, x) for x in el[attr].split())
                parsed.svg['role'] = 'img'
                parsed.svg['aria-label'] = figure.figcaption.get_text() if figure.figcaption else topic['title']
                source.replace_with(parsed)
                details = soup.new_tag('details')
                summary = soup.new_tag('summary')
                summary.string = '查看 Mermaid 图表源码'
                details.append(summary)
                pre = soup.new_tag('pre')
                code = soup.new_tag('code')
                code.string = raw
                pre.append(code)
                details.append(pre)
                figure.append(details)
                report.append({'topic': topic['slug'], 'id': diagram_id, 'rendered': True,
                               'type': raw.splitlines()[0]})
            path.write_text(str(soup))
            print(f'{topic["slug"]}: rendered {len([x for x in report if x["topic"] == topic["slug"]])} diagrams')
        browser.close()
    (ROOT / 'diagram-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('total', len(report))


if __name__ == '__main__':
    main()

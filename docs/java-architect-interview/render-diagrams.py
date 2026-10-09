"""本地构建时用 Mermaid 10.9.3 预渲染；读者无需执行 Mermaid 或访问 CDN。"""
from pathlib import Path
import json,os,re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
soup=BeautifulSoup((ROOT/'index.html').read_text(),'html.parser');report=[]
with sync_playwright() as p:
 executable=os.environ.get('CHROMIUM_EXECUTABLE')
 if not executable and Path('/usr/bin/chromium').exists():executable='/usr/bin/chromium'
 if not executable and Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists():executable='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
 browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox']);page=browser.new_page()
 page.route('https://**/*', lambda route: route.abort())
 page.goto('http://127.0.0.1:8000/java-architect-interview/')
 page.add_script_tag(url='http://127.0.0.1:8000/java-architect-interview/vendor/mermaid.min.js')
 page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',themeVariables:{primaryColor:'#e8eef8',primaryTextColor:'#182338',primaryBorderColor:'#7890af',lineColor:'#72849a',secondaryColor:'#edf2f7',tertiaryColor:'#f4f6f9',fontFamily:'sans-serif'}, flowchart:{htmlLabels:false,useMaxWidth:true}})")
 for fig in soup.select('.diagram'):
  source=fig.select_one('pre.mermaid');diagram_id='jai-diagram-'+fig['data-diagram'];raw=source.get_text()
  svg=page.evaluate('''async ({id,raw}) => {const r=await mermaid.render(id,raw);return r.svg;}''',{'id':diagram_id,'raw':raw})
  parsed=BeautifulSoup(svg,'html.parser')
  # Mermaid 的 sequence/state 图存在通用 marker ID；合并单页时给每个 ID 命名空间。
  idmap={el['id']:diagram_id+'-'+el['id'] for el in parsed.select('[id]')}
  for el in parsed.select('[id]'):el['id']=idmap[el['id']]
  serialized=str(parsed)
  # Single-pass mapping avoids rewriting a longer marker ID again when its
  # root SVG ID is a prefix (which would leave a nonexistent arrow reference).
  pattern=re.compile('#('+'|'.join(re.escape(old) for old in sorted(idmap,key=len,reverse=True))+r')(?=$|[^\w-])')
  serialized=pattern.sub(lambda match:'#'+idmap[match[1]],serialized)
  parsed=BeautifulSoup(serialized,'html.parser')
  for el in parsed.select('[aria-labelledby],[aria-describedby]'):
   for attr in ['aria-labelledby','aria-describedby']:
    if el.has_attr(attr):el[attr]=' '.join(idmap.get(x,x) for x in el[attr].split())
  parsed.svg['role']='img';parsed.svg['aria-label']=fig.figcaption.get_text()
  source.replace_with(parsed)
  details=soup.new_tag('details');summary=soup.new_tag('summary');summary.string='查看 Mermaid 图表源码';details.append(summary)
  pre=soup.new_tag('pre');code=soup.new_tag('code');code.string=raw;pre.append(code);details.append(pre);fig.append(details)
  report.append({'id':diagram_id,'rendered':True,'type':raw.splitlines()[0]})
 browser.close()
(ROOT/'index.html').write_text(str(soup));(ROOT/'diagram-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('Rendered',len(report),'diagrams')

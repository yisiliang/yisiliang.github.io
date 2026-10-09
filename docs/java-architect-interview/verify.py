"""验收：pip install beautifulsoup4 playwright；先从 docs 目录启动静态服务器。"""
from pathlib import Path
import json,re,hashlib,urllib.request,sys,os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent;URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000/java-architect-interview/'
report={'static':{},'browser':{},'limits':['生产故障案例为模拟讲解，原有章节未运行生产故障实验；JIT本地教学实验见JIT-VERIFICATION.md。','不将所有外部参考文档链接的可达性作为永久保证；Redis 文档站 403 后改用官方 redis-doc 仓库核对。']}
soup=BeautifulSoup((ROOT/'index.html').read_text(),'html.parser');ids=[x['id'] for x in soup.select('[id]')]
diagram_count=json.loads((ROOT/'content-stats.json').read_text())['diagrams']
assert len(ids)==len(set(ids)),'duplicate IDs'
for a in soup.select('a[href^="#"]'):assert a['href'][1:] in ids,a['href']
for el in soup.select('[src],[href]'):
 value=el.get('src') or el.get('href')
 if value.startswith('./'):assert (ROOT/value[2:].split('#')[0].split('?')[0]).exists(),value
assert len(soup.select('article.chapter'))==11
assert len(soup.select('.study details'))==66+diagram_count
assert len(soup.select('.study details:not(.diagram details)'))==66
assert len(soup.select('.diagram svg'))==diagram_count
for svg in soup.select('.diagram svg'):
 svg_ids={node['id'] for node in svg.select('[id]')}|{svg['id']}
 for reference in re.findall(r'url\(#([^)]+)\)',str(svg)):
  assert reference in svg_ids,reference
for art in soup.select('article.chapter'):
 assert len(art.select('.study h3'))>=9
 qas=art.select('.study details:not(.diagram details)');assert len(qas)==6
 for d in qas:
  assert len(d.select('.answer p'))==3
  assert len(d.get_text())>180
 assert '模拟生产案例' in art.get_text()
 assert len(art.select('.quick details')) in [3,4,5]
 assert not re.search(r'尚未完善|占位符',art.get_text())
 assert '面试' not in art.get_text()
sources=json.loads((ROOT/'sources.json').read_text())
storage=json.loads((ROOT/'storage-source-verification.json').read_text())
for record in storage['records']:
 s=sources[record['key']]
 assert s['sha256']==record['sha256'] and s['line']==record['line'] and s['end_line']==record['end_line']
 assert any(code.get_text().rstrip()==s['excerpt'].rstrip() for code in soup.select('#c7 .study pre code')),record['key']
report['static']={'chapters':11,'three_layer_questions':66,'diagrams':diagram_count,'ids':len(ids),'all_internal_anchors':'pass','all_local_resources':'pass','storage_source_excerpts':len(storage['records']),'storage_excerpts_match_html':'pass','learning_wording':'pass'}
with sync_playwright() as p:
 executable=os.environ.get('CHROMIUM_EXECUTABLE')
 if not executable and Path('/usr/bin/chromium').exists():executable='/usr/bin/chromium'
 if not executable and Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists():executable='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
 browser=p.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox'])
 context=browser.new_context(reduced_motion='reduce',viewport={'width':1440,'height':1000},permissions=['clipboard-read','clipboard-write'])
 # 所有远程请求中断：证明 Umami 不可用不影响阅读。
 context.route('https://**/*',lambda route:route.abort())
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 resp=page.goto(URL);assert resp.status==200
 page.wait_for_function("document.documentElement.classList.contains('js-enabled')")
 assert page.locator('.chapter.active').get_attribute('id')=='c1'
 assert page.locator('.chapter:visible').count()==1
 assert page.locator('#right-toc').is_visible()
 assert page.locator('.token.keyword').count()>0
 assert page.locator('.diagram svg:visible').count()==1
 screenshot_dir=ROOT.parents[1]/'output/playwright';screenshot_dir.mkdir(parents=True,exist_ok=True)
 page.screenshot(path=str(screenshot_dir/'desktop.png'),full_page=False)
 for n in range(1,12):
  page.goto(URL+'#c'+str(n));page.wait_for_function(f"document.querySelector('.chapter.active').id==='c{n}'")
  assert page.locator('#toc a').count()>10
  qa=page.locator(f'#c{n} .study details:not(.diagram details)').first
  assert not qa.evaluate('(el)=>el.open');qa.locator('summary').click();assert qa.evaluate('(el)=>el.open')
  assert qa.locator('p').count()==3
  page.locator('#mode').click();assert page.locator(f'#c{n} .quick').is_visible()
  assert not page.locator(f'#c{n} .study').is_visible()
  assert page.locator('.route').is_visible()
  page.locator('#mode').click();assert page.locator(f'#c{n} .study').is_visible()
 # 搜索完整正文与默认折叠的答案，并能跳到匹配章节。
 page.locator('#search-open').click();page.locator('#search-input').fill('rollback-only')
 page.wait_for_function("document.querySelector('#search-results').children.length>0")
 page.locator('#search-results .search-result').first.click();assert not page.locator('#search-dialog').is_visible()
 page.wait_for_function("document.querySelector('.chapter.active').id==='c5'")
 page.keyboard.press('/');page.locator('#search-input').fill('MemBarVolatile')
 page.wait_for_function("document.querySelector('#search-results').children.length>0 && document.querySelector('#search-results').textContent.includes('MemBarVolatile')")
 page.locator('#search-results .search-result').first.click()
 page.wait_for_function("document.querySelector('.chapter.active').id==='c11'")
 page.keyboard.press('/');page.locator('#search-input').fill('<script>')
 page.wait_for_timeout(180);assert page.locator('#search-results script').count()==0
 page.locator('#search-input').fill('不可能存在的技术关键词012345');page.wait_for_timeout(180)
 assert '没有找到' in page.locator('#search-status').inner_text();page.keyboard.press('Escape');assert not page.locator('#search-dialog').is_visible()
 # 拷贝内容必须与源码一致。
 page.goto(URL+'#c1');button=page.locator('#c1 .study .copy').first
 text=button.locator('..').locator('code').inner_text()
 # 检查页面写入内容，避免覆盖维护者的系统剪贴板。
 page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>window.__readerCopied=text}})")
 button.click();assert page.evaluate('window.__readerCopied')==text
 # 深浅和系统偏好持久化。
 for pref in ['light','dark','system']:
  page.locator('#theme').click();assert page.locator('html').get_attribute('data-preference')==pref
 page.emulate_media(color_scheme='dark');page.wait_for_function("document.documentElement.dataset.theme==='dark'")
 page.locator('#theme').click();page.reload();assert page.locator('html').get_attribute('data-theme')=='light'
 # hash 深层定位；文章底部进度接近 100。
 target=soup.select_one('#c7 .study h3')['id'];page.goto(URL+'#'+target)
 page.wait_for_function("document.querySelector('.chapter.active').id==='c7'")
 page.wait_for_timeout(250);assert page.locator('#'+target).is_visible()
 page.evaluate("document.querySelector('#c7').scrollIntoView({block:'end',behavior:'instant'})");page.wait_for_timeout(100)
 assert int(re.search(r'\d+',page.locator('#progress-text').inner_text()).group())>=95
 # 放大后的SVG必须保留原图样式；仅确认弹窗存在会漏掉黑色节点。
 for figure in soup.select('.diagram'):
  chapter=figure.find_parent('article')['id'];identifier=figure['data-diagram']
  page.goto(URL+'#'+chapter);page.wait_for_function("id=>document.querySelector('.chapter.active').id===id",arg=chapter)
  original=page.locator(f'figure[data-diagram="{identifier}"]')
  colors=original.locator('svg rect').evaluate_all("nodes=>nodes.map(el=>({fill:getComputedStyle(el).fill,stroke:getComputedStyle(el).stroke}))")
  original.locator('button.expand').click()
  assert page.locator('#diagram-dialog').is_visible()
  assert page.locator('#diagram-content svg').count()==1
  assert page.locator('#diagram-content svg').evaluate("svg=>{const ids=new Set([svg.id,...[...svg.querySelectorAll('[id]')].map(el=>el.id)]);return [...svg.querySelectorAll('[marker-end],[marker-start]')].every(el=>['marker-end','marker-start'].every(attr=>{const value=el.getAttribute(attr);const match=value?.match(/url\\(#([^)]+)\\)/);return !match||ids.has(match[1])}))}")
  assert page.locator('#diagram-content svg rect').evaluate_all("nodes=>nodes.map(el=>({fill:getComputedStyle(el).fill,stroke:getComputedStyle(el).stroke}))")==colors,identifier
  assert page.evaluate("(()=>{const ids=[...document.querySelectorAll('[id]')].map(el=>el.id);return ids.length===new Set(ids).size})()")
  page.locator('#zoom-in').click();assert page.locator('#diagram-content svg').evaluate("el=>el.style.width")=='125%'
  page.locator('#diagram-close').click()
 # 320/390/820 手机和平板无整页横向溢出；代码/表格/图允许自己的水平滚动。
 for width in [320,390,820]:
  page.set_viewport_size({'width':width,'height':844});page.goto(URL+'#c11');page.wait_for_timeout(200)
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'overflow {width}'
  if width<760:
   page.locator('#menu').click();assert page.locator('#left-nav').is_visible()
   page.locator('#left-nav a[href="#c11"]').click()
   page.wait_for_function("document.querySelector('.chapter.active').id==='c11'")
   assert not page.locator('#left-nav').is_visible()
   if width==390:page.screenshot(path=str(screenshot_dir/'mobile.png'),full_page=False)
 # 禁用 JS：所有十章和预渲染图存在，问答原生可展开。
 nojs=browser.new_context(java_script_enabled=False,viewport={'width':1280,'height':900})
 nojs.route('https://**/*',lambda route:route.abort());np=nojs.new_page();np.goto(URL)
 assert np.locator('.chapter:visible').count()==11
 assert np.locator('.diagram svg').count()==diagram_count
 np.locator('#c1 .study details:not(.diagram details)').first.locator('summary').click()
 assert np.locator('#c1 .study details:not(.diagram details)').first.get_attribute('open') is not None
 assert not errors,errors
 report['browser']={'desktop':'1440×1000 pass','responsive':'320/390/820 px pass','search':'full content / no result / escaped input pass','mode':'all 11 chapters pass','theme':'system/light/dark and persistence pass','copy':'copy handler matches source pass','qa':'all 11 chapters pass','hash':'deep link pass','reading_progress':'pass','diagram_viewer':f'{diagram_count} SVGs retain node colors, valid arrows, unique IDs and zoom controls','offline_core':'all external requests blocked pass','javascript_disabled':f'11 chapters + {diagram_count} SVG pass','page_errors':errors}
 browser.close()
(ROOT/'validation-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))

async page => {
  const origin='http://127.0.0.1:8765/';
  const names=['jdk-source','jvm','springboot','mysql','redis','rocketmq','nginx','distributed','nacos','transformer','java-architect-interview'];
  const oldAnchors={
    'jdk-source':'chapter-14','jvm':'appendix-xstream','springboot':'chapter-18','mysql':'chapter-12',
    'redis':'chapter-12','rocketmq':'chapter-15','nginx':'chapter-15','distributed':'cap-paper',
    'nacos':'baseline','transformer':'calculate','java-architect-interview':'c7-s9'
  };
  const words={'jdk-source':'ThreadLocal','jvm':'CMS','springboot':'SpringApplication','mysql':'ReadView','redis':'sentinel','rocketmq':'CommitLog','nginx':'ngx_http','distributed':'分区','nacos':'MD5','transformer':'softmax','java-architect-interview':'rollback-only'};
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  const results=[];
  for(const name of names){
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(origin+name+'/#'+oldAnchors[name]);
    await page.waitForFunction(()=>document.querySelectorAll('.chapter.active').length===1);
    const target=page.locator('[id="'+oldAnchors[name]+'"]');
    if(await target.count()!==1)throw Error(name+' old anchor missing');
    const matchChapter=await target.evaluate(el=>el.closest('.chapter')?.id);
    if(await page.locator('.chapter.active').getAttribute('id')!==matchChapter)throw Error(name+' old anchor opened wrong chapter');
    await page.locator('#search-open').click();await page.locator('#search-input').fill(words[name]);
    await page.waitForFunction(()=>document.querySelector('#search-results').children.length>0);
    await page.locator('#search-results a').first().click();
    await page.waitForFunction(()=>!document.querySelector('#search-dialog').open);
    await page.locator('#search-open').click();await page.locator('#search-input').fill('无法存在的关键词0123456789');
    await page.waitForFunction(()=>document.querySelector('#search-status').textContent.includes('没有找到'));
    await page.locator('#search-input').fill('<script>');
    await page.waitForTimeout(130);
    if(await page.locator('#search-results script').count())throw Error(name+' unsafe search rendering');
    await page.keyboard.press('Escape');
    // Exercise actual copy handlers without changing the user's system clipboard.
    const codeChapter=await page.evaluate(()=>[...document.querySelectorAll('.chapter')].find(c=>c.querySelector('pre code'))?.id);
    if(codeChapter){
      await page.evaluate(id=>location.hash=id,codeChapter);
      await page.waitForFunction(id=>document.querySelector('.chapter.active').id===id,codeChapter);
      await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>window.__readerCopied=text}}));
      const pre=page.locator('.chapter.active pre:has(code)').first();const expected=await pre.locator('code').innerText();
      await pre.locator('button.copy').click();
      if(await page.evaluate(()=>window.__readerCopied)!==expected)throw Error(name+' copy differs from code');
    }
    const diagramChapter=await page.evaluate(()=>[...document.querySelectorAll('.chapter')].find(c=>c.querySelector('figure svg,figure img'))?.id);
    if(diagramChapter&&await page.locator('#diagram-dialog').count()){
      await page.evaluate(id=>location.hash=id,diagramChapter);await page.waitForFunction(id=>document.querySelector('.chapter.active').id===id,diagramChapter);
      await page.locator('.chapter.active figure button.expand').first().click();
      if(!await page.locator('#diagram-dialog').isVisible()||await page.locator('#diagram-content svg,#diagram-content img').count()!==1)throw Error(name+' zoom');
      await page.locator('#zoom-in').click();if(await page.locator('#diagram-content').evaluate(el=>el.firstElementChild.style.width)!=='125%')throw Error(name+' diagram scaling');await page.locator('#zoom-reset').click();
      await page.locator('#diagram-close').click();
    }
    await page.evaluate(()=>{localStorage.setItem('learning-reader-theme','system');});await page.reload();
    for(const preference of ['light','dark','system']){
      await page.locator('#theme').click();if(await page.locator('html').getAttribute('data-preference')!==preference)throw Error(name+' theme '+preference);
    }
    if(name==='transformer'){
      await page.evaluate(()=>location.hash='calculate');await page.waitForFunction(()=>document.querySelector('.chapter.active')?.querySelector('#q0'));
      await page.locator('#q0').fill('2');await page.locator('#q1').fill('1');const before=await page.locator('#lab-result').innerText();
      await page.locator('#causal').check();const after=await page.locator('#lab-result').innerText();
      if(before===after||!after.includes('1.000000, 0.000000, 0.000000'))throw Error('attention calculator');
    }
    if(name==='java-architect-interview'){
      await page.evaluate(()=>location.hash='c7');await page.waitForFunction(()=>document.querySelector('.chapter.active').id==='c7');
      await page.locator('#mode').click();if(!await page.locator('#c7 .quick').isVisible())throw Error('quick mode');
      await page.locator('#mode').click();if(!await page.locator('#c7 .study').isVisible())throw Error('complete mode');
    }
    const original=await page.locator('.chapter.active').getAttribute('id');
    for(const width of [320,390,768,1024,1440]){
      await page.setViewportSize({width,height:900});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error(name+' overflow '+width);
    }
    await page.setViewportSize({width:390,height:844});await page.locator('#menu').click();
    if(!await page.locator('#left-nav').isVisible())throw Error(name+' drawer');
    await page.locator('#left-nav .chapter-nav summary a').first().click();await page.waitForFunction(()=>!document.body.classList.contains('drawer-open'));
    await page.setViewportSize({width:1440,height:1000});
    await page.evaluate(id=>location.hash=id,original);await page.waitForFunction(id=>document.querySelector('.chapter.active').id===id,original);
    await page.evaluate(()=>document.querySelector('.chapter.active').scrollIntoView({block:'end',behavior:'instant'}));
    await page.waitForTimeout(100);
    if(Number((await page.locator('#progress-text').innerText()).match(/\d+/)[0])<95)throw Error(name+' progress');
    results.push({name,oldAnchor:'pass',search:'pass',copy:'pass',diagram:diagramChapter?'pass':'no SVG',theme:'pass',responsive:'pass',drawer:'pass',progress:'pass'});
  }
  if(errors.length)throw Error(errors.join(';'));
  const nojs=await page.context().browser().newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
  const nojsPage=await nojs.newPage();
  for(const name of names){
    await nojsPage.goto(origin+name+'/');
    const count=await nojsPage.locator('.chapter').count();if(await nojsPage.locator('.chapter:visible').count()!==count)throw Error(name+' no JS chapters');
  }
  await nojs.close();
  return {pages:results,noJavaScript:'all chapters remain readable',pageErrors:errors};
}

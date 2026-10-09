(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const chapters = [...document.querySelectorAll('.chapter')];
  const root = document.documentElement;
  const dialog = $('#search-dialog');
  let active = chapters[0], mode = 'study', sections = [], ticking = false;
  let lastSearch = '', searchTimer, toastTimer;
  const highlighted = new WeakSet();
  const escape = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const searchIndex = [];
  // 从已存在的完整 HTML 建索引，包含默认折叠的答案，不加载远程内容。
  chapters.forEach(article => {
    let heading = article.querySelector('.chapter-title h1,.chapter-title h2'), text = [];
    const flush = () => {
      if (!text.length || !heading) return;
      searchIndex.push({id:heading.id || article.id, chapter:article.id, title:heading.textContent,
        chapterTitle:article.dataset.title, text:text.join(' ').replace(/\s+/g,' ').trim()}); text=[];
    };
    const study=article.querySelector('.study');
    let sectionNumber=0;
    study.querySelectorAll('h2,h3').forEach(h=>{if(!h.id)h.id=article.id+'-section-'+(++sectionNumber);});
    study.querySelectorAll('h2,h3,p,li,pre:not(.gutter),td,.source-caption,.source-head,.source-bar').forEach(node=>{
      if (/^H[23]$/.test(node.tagName)) {flush(); heading=node;}
      else text.push(node.textContent);
    });flush();
    article.querySelectorAll('pre:not(.mermaid):not(.gutter)').forEach(pre => {
      const code = pre.querySelector('code'); if (!code) return;
      const container=pre.closest('.source-card,.source,.source-block,.source-box');
      const previous=container?.querySelector('button.copy-source,button.copy,button[data-copy]') || pre.querySelector('button.copy');
      if(previous)previous.remove();
      const label=document.createElement('span'); label.className='code-lang';
      label.textContent=(code.className.match(/language-([\w-]+)/)||[])[1] || 'text';
      const button=document.createElement('button');button.className='copy';button.type='button';button.textContent='复制';
      button.setAttribute('aria-label','复制 '+label.textContent+' 代码');
      button.addEventListener('click', async () => {
        try {
          if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(code.textContent);
          else {
            const area=document.createElement('textarea');area.value=code.textContent;area.style.position='fixed';area.style.opacity='0';
            document.body.append(area);area.select();const ok=document.execCommand('copy');area.remove();button.focus();if(!ok)throw Error('copy');
          }
          button.textContent='已复制';toast('代码已复制');setTimeout(()=>button.textContent='复制',1800);
        } catch (_) {toast('自动复制失败，请选中代码手动复制');}
      });pre.prepend(label);pre.append(button);
    });
  });
  const preface=$('.reader-preface');if(preface)searchIndex.push({id:'reader-preface',chapter:chapters[0].id,title:'版本、来源与学习路线',chapterTitle:'阅读说明',text:preface.textContent});
  if(preface)preface.id='reader-preface';
  $('#print')?.addEventListener('click',()=>window.print());
  function toast(message) {clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').classList.add('visible');toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),2400);}
  function highlight(article) {if(window.Prism && !highlighted.has(article)){Prism.highlightAllUnder(article);highlighted.add(article);}}
  function visibleHeadings() {return [...active.querySelector(mode==='quick'?'.quick':'.study').querySelectorAll('h2,h3')];}
  function makeToc() {
    sections=visibleHeadings();$('#toc').replaceChildren();
    sections.forEach(h=>{const a=document.createElement('a');a.href='#'+h.id;a.textContent=h.textContent;a.className=h.tagName==='H3'?'depth3':'';$('#toc').append(a);});
    $('#current-label').textContent=active.dataset.title;
  }
  function setMode(next) {
    mode=next;root.classList.toggle('quick-mode',mode==='quick');
    if(!$('#mode'))return;
    $('#mode').setAttribute('aria-pressed',String(mode==='quick'));$('#mode').textContent=mode==='quick'?'完整学习':'要点速览';
    chapters.forEach(c=>{c.querySelector('.eyebrow').textContent='专题 '+c.id.slice(1).padStart(2,'0')+' / '+(mode==='quick'?'要点速览':'完整阅读');});
    makeToc();
  }
  function closeDrawer(focus=false) {document.body.classList.remove('drawer-open');$('#drawer-backdrop').hidden=true;$('#menu').setAttribute('aria-expanded','false');if(focus)$('#menu').focus();}
  function selectChapter(article) {
    active=article;
    chapters.forEach(c=>c.classList.toggle('active',c===active));
    document.querySelectorAll('.chapter-nav').forEach(n=>{const current=n.dataset.chapter===active.id;n.classList.toggle('current',current);if(current)n.open=true;});
    highlight(active);makeToc();
  }
  function scrollToTarget(target) {
    const margin=window.innerWidth<=760?115:90;
    window.scrollTo({top:Math.max(0,target.getBoundingClientRect().top+window.scrollY-margin),behavior:'instant'});
  }
  function navigate(hash, scroll=true) {
    let id;try{id=decodeURIComponent((hash||'').replace(/^#/,''));}catch(_){id='';}
    if(id==='review-route' && $('#review-route')) {root.classList.add('show-route');if(scroll)scrollToTarget($('#review-route'));closeDrawer();return;}
    root.classList.remove('show-route');
    const targetNode=document.getElementById(id);const article=targetNode?.closest('.chapter') || chapters[0];
    if(!article)return;
    active=article;
    if(id.includes('-quick-') && mode!=='quick')setMode('quick');
    else if(id.includes('-s') && mode!=='study')setMode('study');
    selectChapter(article);closeDrawer();
    let target=document.getElementById(id) || active;
    if(target.closest('.study') && mode==='quick')target=active;
    if(scroll) {
      if(target.tagName==='DETAILS')target.open=true;
      // 搜索可跳入默认折叠的问答，完整参考答案立即可见。
      const next=target.nextElementSibling;if(next?.tagName==='DETAILS')next.open=true;
      for(let p=target.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
      scrollToTarget(target);if(target.hasAttribute('tabindex'))target.focus({preventScroll:true});updateReading();
    }
    updateReading(false);
  }
  function updateReading(trackChapter=true) {
    ticking=false;if(!active)return;
    const margin=window.innerWidth<=760?115:90;
    let currentChapter=chapters[0];
    for(const chapter of chapters){if(chapter.getBoundingClientRect().top<=margin+30)currentChapter=chapter;else break;}
    const first=chapters[0].getBoundingClientRect(),last=chapters[chapters.length-1].getBoundingClientRect();
    const box={top:first.top,bottom:last.bottom,height:last.bottom-first.top};
    const length=Math.max(1,box.height-(innerHeight-margin));
    let progress=Math.min(100,Math.max(0,Math.round((margin-box.top)/length*100)));
    if(box.bottom<=innerHeight+3 && box.bottom>margin)progress=100;
    if(progress===100)currentChapter=chapters[chapters.length-1];
    if(trackChapter && currentChapter!==active)selectChapter(currentChapter);
    if(root.classList.contains('show-route'))progress=0;
    $('#progress-bar').style.width=progress+'%';$('#progress-text').textContent='阅读进度 '+progress+'%';
    let current=sections[0];for(const h of sections){if(h.getBoundingClientRect().top<=margin+30)current=h;else break;}
    document.querySelectorAll('#toc a,.chapter-nav div a').forEach(a=>a.classList.toggle('current',!!current && a.hash==='#'+current.id));
  }
  window.addEventListener('scroll',()=>{if(!ticking){requestAnimationFrame(updateReading);ticking=true;}},{passive:true});
  window.addEventListener('resize',()=>{if(innerWidth>760)closeDrawer();updateReading();});
  window.addEventListener('hashchange',()=>navigate(location.hash));
  document.addEventListener('click',e=>{const a=e.target.closest('a[href^="#"]');if(!a)return;if(a.closest('#search-results'))return;
    if(a.hash===location.hash){e.preventDefault();navigate(a.hash);}else if(a.hash==='#main'){closeDrawer();}
  });
  $('#mode')?.addEventListener('click',()=>{const chapter=active.id;setMode(mode==='study'?'quick':'study');
    const hash=mode==='quick'?'#'+chapter+'-quick-core':'#'+chapter;history.replaceState(null,'',hash);navigate(hash);
  });
  const themeNames={system:'系统',light:'浅色',dark:'深色'};
  function themeLabel(){const name=themeNames[window.learningTheme?.get()||'system'];$('#theme').textContent='主题：'+name;$('#theme').setAttribute('aria-label','当前主题 '+name+'，点击切换');}
  window.addEventListener('learning-theme-change',themeLabel);
  themeLabel();$('#theme').addEventListener('click',()=>{window.learningTheme?.cycle();themeLabel();});
  $('#menu').addEventListener('click',()=>{const open=!document.body.classList.contains('drawer-open');document.body.classList.toggle('drawer-open',open);$('#drawer-backdrop').hidden=!open;$('#menu').setAttribute('aria-expanded',String(open));if(open)$('#left-nav a').focus();});
  $('#drawer-backdrop').addEventListener('click',()=>closeDrawer(true));
  const openSearch=()=>{closeDrawer();if(!dialog.open)dialog.showModal();$('#search-input').focus();};
  $('#search-open').addEventListener('click',openSearch);$('#search-close').addEventListener('click',()=>dialog.close());
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape'){if(dialog.open){e.preventDefault();dialog.close();}else if(document.body.classList.contains('drawer-open'))closeDrawer(true);}
    if(e.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)&&!e.target.isContentEditable){e.preventDefault();openSearch();}
    if(e.key==='Tab'&&document.body.classList.contains('drawer-open')){
      const links=[...$('#left-nav').querySelectorAll('a,summary')].filter(x=>x.getClientRects().length);const first=links[0],last=links[links.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
    }
  });
  function renderSearch() {
    const q=$('#search-input').value.trim();lastSearch=q;$('#search-results').replaceChildren();
    if(!q){$('#search-status').textContent='输入关键词，搜索完整正文与原理问答。';return;}
    const words=q.toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const hits=searchIndex.map(entry=>{const title=(entry.chapterTitle+' '+entry.title).toLocaleLowerCase();const all=(title+' '+entry.text).toLocaleLowerCase();return {entry,score:words.every(w=>all.includes(w))?words.reduce((n,w)=>n+(title.includes(w)?5:1),0):0};}).filter(x=>x.score).sort((a,b)=>b.score-a.score);
    $('#search-status').textContent=hits.length?'找到 '+hits.length+' 处匹配'+(hits.length>80?'，显示前 80 处':''):'没有找到匹配内容，请尝试缩短关键词或使用源码方法名。';
    const mark=s=>{let safe=escape(s);const pattern=words.map(w=>escape(w).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).sort((a,b)=>b.length-a.length).join('|');return safe.replace(new RegExp(pattern,'gi'),v=>'<mark>'+v+'</mark>');};
    hits.slice(0,80).forEach(({entry})=>{
      const a=document.createElement('a');a.className='search-result';a.href='#'+entry.id;
      const offset=entry.text.toLocaleLowerCase().indexOf(words[0]);const start=Math.max(0,offset-55);const excerpt=(start?'…':'')+entry.text.slice(start,start+190)+'…';
      a.innerHTML='<small>'+escape(entry.chapterTitle)+'</small><strong>'+mark(entry.title)+'</strong><p>'+mark(excerpt)+'</p>';
      a.addEventListener('click',e=>{e.preventDefault();dialog.close();setMode('study');if(location.hash===a.hash)navigate(a.hash);else location.hash=a.hash;});$('#search-results').append(a);
    });
  }
  $('#search-input').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(renderSearch,100);});
  const viewer=$('#diagram-dialog');
  if(viewer){
    let zoom=1;
    const scale=next=>{zoom=Math.max(.5,Math.min(4,next));const graphic=$('#diagram-content').firstElementChild;if(graphic)graphic.style.width=(zoom*100)+'%';};
    $('#zoom-in')?.addEventListener('click',()=>scale(zoom*1.25));
    $('#zoom-out')?.addEventListener('click',()=>scale(zoom/1.25));
    $('#zoom-reset')?.addEventListener('click',()=>scale(1));
    $('#diagram-close').addEventListener('click',()=>viewer.close());
    document.querySelectorAll('figure:has(svg),.diagram:has(svg),figure:has(img),.diagram:has(img)').forEach(figure=>{
      let button=figure.querySelector('button.expand,button.zoom');
      if(!button){button=document.createElement('button');button.type='button';button.className='expand';button.textContent='放大图解';figure.prepend(button);}
      button.addEventListener('click',()=>{
        const canvas=$('#diagram-content');canvas.classList.add('diagram');
        canvas.style.margin='0';canvas.style.padding='0';canvas.style.border='0';
        canvas.replaceChildren(figure.querySelector('svg,img').cloneNode(true));
        const ids=new Map([...canvas.querySelectorAll('[id]')].map(el=>[el.id,'zoom-'+el.id]));
        const keys=[...ids.keys()].sort((a,b)=>b.length-a.length).map(id=>id.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
        const pattern=keys.length?new RegExp('#('+keys.join('|')+')(?=$|[^\\w-])','g'):null;
        const references=value=>pattern?value.replace(pattern,(_,id)=>'#'+ids.get(id)):value;
        canvas.querySelectorAll('[id]').forEach(el=>{el.id=ids.get(el.id);});
        // Mermaid scopes CSS selectors to the root SVG ID; keep those selectors
        // and marker/use references aligned with the renamed clone IDs.
        canvas.querySelectorAll('style').forEach(el=>{el.textContent=references(el.textContent);});
        canvas.querySelectorAll('*').forEach(el=>{
          for(const attr of ['style','fill','stroke','marker-end','marker-start','marker-mid','clip-path','mask','filter','href','xlink:href']){
            const value=el.getAttribute(attr);if(value)el.setAttribute(attr,references(value));
          }
          for(const attr of ['aria-labelledby','aria-describedby']){
            const value=el.getAttribute(attr);if(value)el.setAttribute(attr,value.split(/\s+/).map(id=>ids.get(id)||id).join(' '));
          }
        });scale(1);viewer.showModal();
      });
    });
  }
  root.classList.add('js-enabled');navigate(location.hash,false);
  // Inline offline controls may run before the reference's deferred Prism files.
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>highlight(active),{once:true});
  else highlight(active);
  if(location.hash)requestAnimationFrame(()=>navigate(location.hash));
})();

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
    let heading = article.querySelector('h1'), text = [];
    const flush = () => {
      if (!text.length) return;
      searchIndex.push({id:heading.id || article.id, chapter:article.id, title:heading.textContent,
        chapterTitle:article.dataset.title, text:text.join(' ').replace(/\s+/g,' ').trim()}); text=[];
    };
    [...article.querySelector('.study').children].forEach(node => {
      if (/^H[23]$/.test(node.tagName)) {flush(); heading=node;}
      else if(node.matches('details.question')){flush();heading=node.querySelector('h3');text.push(node.querySelector('.answer').textContent);flush();}
      else text.push(node.textContent);
    }); flush();
    article.querySelectorAll('pre:not(.mermaid)').forEach(pre => {
      const code = pre.querySelector('code'); if (!code) return;
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
    $('#mode').setAttribute('aria-pressed',String(mode==='quick'));$('#mode').textContent=mode==='quick'?'完整学习':'面试速查';
    chapters.forEach(c=>{c.querySelector('.eyebrow').textContent='专题 '+c.id.slice(1).padStart(2,'0')+' / '+(mode==='quick'?'面试速查':'完整阅读');});
    makeToc();
  }
  function closeDrawer(focus=false) {document.body.classList.remove('drawer-open');$('#drawer-backdrop').hidden=true;$('#menu').setAttribute('aria-expanded','false');if(focus)$('#menu').focus();}
  function navigate(hash, scroll=true) {
    const id=decodeURIComponent((hash||'').replace(/^#/,''));
    if(id==='review-route') {root.classList.add('show-route');if(scroll)$('#review-route').scrollIntoView({block:'start'});closeDrawer();return;}
    root.classList.remove('show-route');
    const match=id.match(/^c(10|[1-9])(?:-|$)/);const article=match?$('#c'+match[1]):chapters[0];
    if(!article)return;
    active=article;
    if(id.includes('-quick-') && mode!=='quick')setMode('quick');
    else if(id.includes('-s') && mode!=='study')setMode('study');
    chapters.forEach(c=>c.classList.toggle('active',c===active));
    document.querySelectorAll('.chapter-nav').forEach(n=>{const current=n.dataset.chapter===active.id;n.classList.toggle('current',current);if(current)n.open=true;});
    highlight(active);makeToc();closeDrawer();
    let target=document.getElementById(id) || active;
    if(target.closest('.study') && mode==='quick')target=active;
    if(scroll) {
      // 搜索可跳入默认折叠的问答，完整参考答案立即可见。
      const next=target.nextElementSibling;if(next?.tagName==='DETAILS')next.open=true;
      for(let p=target.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
      requestAnimationFrame(()=>{target.scrollIntoView({block:'start'});if(target.hasAttribute('tabindex'))target.focus({preventScroll:true});updateReading();});
    }
    updateReading();
  }
  function updateReading() {
    ticking=false;if(!active)return;
    const margin=window.innerWidth<=760?115:90;const box=active.getBoundingClientRect();
    const length=Math.max(1,box.height-(innerHeight-margin));
    let progress=Math.min(100,Math.max(0,Math.round((margin-box.top)/length*100)));
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
  $('#mode').addEventListener('click',()=>{const chapter=active.id;setMode(mode==='study'?'quick':'study');
    const hash=mode==='quick'?'#'+chapter+'-quick-core':'#'+chapter;history.replaceState(null,'',hash);navigate(hash);
  });
  const themeNames={system:'系统',light:'浅色',dark:'深色'};
  function themeLabel(){const name=themeNames[window.interviewTheme?.get()||'system'];$('#theme').textContent='主题：'+name;$('#theme').setAttribute('aria-label','当前主题 '+name+'，点击切换');}
  themeLabel();$('#theme').addEventListener('click',()=>{window.interviewTheme?.cycle();themeLabel();});
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
    if(!q){$('#search-status').textContent='输入关键词，搜索十个专题的完整正文与答案。';return;}
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
  root.classList.add('js-enabled');navigate(location.hash,false);
  if(location.hash)requestAnimationFrame(()=>navigate(location.hash));
})();

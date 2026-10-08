/* Shared appearance and mobile navigation; existing search/diagram handlers stay. */
(()=>{
 const body=document.body, theme=document.getElementById('theme'), menu=document.getElementById('menu');
 try{body.classList.toggle('reader-light',localStorage.getItem('source-library-theme')==='light')}catch(e){}
 function label(){if(theme)theme.textContent=body.classList.contains('reader-light')?'深色阅读':'浅色阅读'}
 label();
 if(theme)theme.onclick=()=>{body.classList.toggle('reader-light');label();try{localStorage.setItem('source-library-theme',body.classList.contains('reader-light')?'light':'dark')}catch(e){}};
 if(menu){body.classList.add('reader-collapsed');menu.setAttribute('aria-expanded','false');menu.textContent='展开目录';menu.onclick=()=>{body.classList.toggle('reader-collapsed');const open=!body.classList.contains('reader-collapsed');menu.setAttribute('aria-expanded',String(open));menu.textContent=open?'收起目录':'展开目录'};}
 document.querySelectorAll('nav a').forEach(a=>a.addEventListener('click',()=>{if(innerWidth<=700&&menu){body.classList.add('reader-collapsed');menu.setAttribute('aria-expanded','false');menu.textContent='展开目录'}}));
})();

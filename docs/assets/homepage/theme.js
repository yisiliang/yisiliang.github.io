(() => {
  let preference = 'system';
  try { preference = localStorage.getItem('learning-reader-theme') || localStorage.getItem('jai-theme') || localStorage.getItem('source-library-theme') || 'system'; } catch (_) {}
  if (!['system', 'light', 'dark'].includes(preference)) preference = 'system';
  const query = matchMedia('(prefers-color-scheme: dark)');
  const apply = () => {
    document.documentElement.dataset.theme = preference === 'system' ? (query.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.preference = preference;
    window.dispatchEvent(new Event('learning-theme-change'));
  };
  apply(); query.addEventListener('change', apply);
  window.addEventListener('storage',event=>{if(event.key==='learning-reader-theme'){preference=['system','light','dark'].includes(event.newValue)?event.newValue:'system';apply();}});
  window.learningTheme = {
    get: () => preference,
    cycle: () => {
      preference = {system:'light', light:'dark', dark:'system'}[preference];
      try { localStorage.setItem('learning-reader-theme', preference); } catch (_) {}
      apply(); return preference;
    }
  };
})();

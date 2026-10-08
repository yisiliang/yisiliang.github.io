(() => {
  let preference = 'system';
  try { preference = localStorage.getItem('jai-theme') || 'system'; } catch (_) {}
  if (!['system', 'light', 'dark'].includes(preference)) preference = 'system';
  const query = matchMedia('(prefers-color-scheme: dark)');
  const apply = () => {
    document.documentElement.dataset.theme = preference === 'system' ? (query.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.preference = preference;
  };
  apply(); query.addEventListener('change', apply);
  window.interviewTheme = {
    get: () => preference,
    cycle: () => {
      preference = {system:'light', light:'dark', dark:'system'}[preference];
      try { localStorage.setItem('jai-theme', preference); } catch (_) {}
      apply(); return preference;
    }
  };
})();

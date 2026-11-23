(function () {
  const TAGS = {cet4: '四级', cet6: '六级', ielts: '雅思', toefl: '托福', gre: 'GRE', zk: '中考'};
  const LISTS = ['cet4', 'cet6', 'ielts', 'toefl', 'gre', 'zk'];
  const KIND = {root: '词根', prefix: '前缀', suffix: '后缀'};
  const LANG = {Latin: '拉丁语', Greek: '希腊语', 'Latin and Greek': '拉丁语 / 希腊语'};
  const main = document.getElementById('main');
  const cache = new Map();
  const state = {scope: 'core', kind: 'all', lang: 'all', shown: 80, routeKey: ''};

  function asset(path) {
    return new URL(path, document.baseURI).href;
  }
  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, function (ch) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch];
    });
  }
  function route() {
    const params = new URLSearchParams(location.search);
    return {
      m: params.get('m') || '',
      w: params.get('w') || '',
      list: params.get('list') || '',
      about: params.get('about') === '1',
      q: params.get('q') || '',
    };
  }
  function go(params) {
    const usp = new URLSearchParams();
    Object.keys(params).forEach(function (key) {
      if (params[key]) usp.set(key, params[key]);
    });
    const search = usp.toString();
    history.pushState(null, '', search ? '?' + search : location.pathname);
    render();
    window.scrollTo(0, 0);
  }
  async function load(path) {
    if (cache.has(path)) return cache.get(path);
    const response = await fetch(asset(path));
    if (!response.ok) throw new Error(path);
    const data = await response.json();
    cache.set(path, data);
    return data;
  }
  function paintTheme() {
    const mode = localStorage.getItem('roots-theme') || 'system';
    document.documentElement.dataset.theme = mode === 'system' ? '' : mode;
    const names = {system: '系统', light: '浅色', dark: '深色'};
    const button = document.getElementById('theme');
    button.textContent = names[mode];
    button.setAttribute('aria-label', '当前主题' + names[mode] + '，点击切换');
  }
  function scopeOk(item) {
    if (state.scope === 'all') return true;
    if (state.scope === 'core') return item.core;
    if (state.scope === 'medical') return item.med === 'y';
    return item.med !== 'y';
  }
  function morphMatch(item, query) {
    if (!query) return true;
    const folded = query.toLowerCase();
    return [item.forms, item.en, item.zh, item.origin, item.id].some(function (value) {
      return String(value || '').toLowerCase().includes(folded) || String(value || '').includes(query);
    });
  }
  function tagText(tags) {
    return (tags || []).map(function (tag) { return TAGS[tag] || tag; }).join(' ');
  }
  function wordBlock(word, link) {
    const parts = word.parts || [];
    const usable = parts.some(function (part) { return part.t && part.t !== 'other'; });
    const head = usable
        ? '<h3 class="seg">' + parts.map(function (part) {
          return '<span class="' + esc(part.t || 'other') + '">' + esc(part.s) + '</span>';
        }).join('') + '</h3><p class="bits">' + parts.filter(function (part) { return part.zh; }).map(function (part) {
          return '<span class="' + esc(part.t) + '">' + esc(part.zh) + '</span>';
        }).join('<span class="sep">·</span>') + '</p>'
      : '<h3>' + esc(word.w) + '</h3>';
    const chinese = word.zh ? '<p class="zh">' + esc(word.zh) + '</p>' : '<p class="zh missing">这份词典里没有中文释义</p>';
    const meta = ['<p class="meta">'];
    if (word.ipa) meta.push('/' + esc(word.ipa) + '/');
    if (word.pos && word.pos.length) meta.push(' · ' + esc(word.pos.join('/')));
    if (word.tags && word.tags.length) meta.push(' · ' + esc(tagText(word.tags)));
    meta.push('</p>');
    const literal = word.literalZh ? '<p class="lit">字面：' + esc(word.literalZh) + '</p>' : '';
    const partial = word.partial ? '<p class="meta">灰色字母这份资料没有拆开。</p>' : '';
    const body = head + chinese + meta.join('') + literal + partial;
    if (!link) return '<article class="word">' + body + '</article>';
    return '<a class="word" href="?w=' + encodeURIComponent(word.w) + '">' + body + '</a>';
  }
  function knownLine(word) {
    if (!word.known || !word.known.length) return '';
    return '<p class="meta">' + word.known.map(function (item) {
      return '<a href="?m=' + encodeURIComponent(item.id) + '">' + esc(item.forms) + ' ' + esc(item.zh) + '</a>';
    }).join(' · ') + '</p>';
  }
  function filters() {
    const scopes = [['core', '核心'], ['general', '常用'], ['all', '全部'], ['medical', '医学']];
    const kinds = [['all', '词根和词缀'], ['root', '词根'], ['prefix', '前缀'], ['suffix', '后缀']];
    const langs = [['all', '拉丁和希腊'], ['Latin', '拉丁语'], ['Greek', '希腊语']];
    function chips(name, options, current) {
      return options.map(function (option) {
        return '<button type="button" class="chip' + (current === option[0] ? ' on' : '') + '" data-filter="' + name + '" data-value="' + option[0] + '">' + option[1] + '</button>';
      }).join('');
    }
    return '<div class="filters" role="group" aria-label="筛选">' + chips('scope', scopes, state.scope) + chips('kind', kinds, state.kind) + chips('lang', langs, state.lang) + '</div>';
  }
  function card(item) {
    const pills = '<span class="pill">' + KIND[item.kind] + '</span><span class="pill">' + (LANG[item.lang] || esc(item.lang)) + '</span>' + (item.core ? '<span class="pill">核心</span>' : '') + (item.med === 'y' ? '<span class="pill">医学</span>' : '');
    return '<a class="card" href="?m=' + encodeURIComponent(item.id) + '"><div class="kicker">' + pills + '</div><h2 class="form">' + esc(item.forms) + '</h2><p class="zh">' + esc(item.zh) + '</p><p class="en">' + esc(item.en) + '</p><p class="meta">' + item.n + ' 个例词</p></a>';
  }
  function setTab(name) {
    document.querySelectorAll('.tabs a').forEach(function (link) {
      link.classList.toggle('on', link.dataset.tab === name);
    });
  }
  function syncQuery(query) {
    const input = document.getElementById('q');
    if (document.activeElement !== input && input.value !== query) input.value = query;
  }

  async function showHome(current) {
    setTab('roots');
    const data = state.catalog;
    const query = current.q.trim();
    let items = data.morphemes.filter(scopeOk).filter(function (item) {
      if (state.kind !== 'all' && item.kind !== state.kind) return false;
      if (state.lang !== 'all' && item.lang !== state.lang && item.lang !== 'Latin and Greek') return false;
      return morphMatch(item, query);
    });
    items.sort(function (a, b) { return (b.n - a.n) || a.forms.localeCompare(b.forms); });
    const stats = data.stats;
    let wordHtml = '';
    if (query) {
      const index = await load('data/words-index.json');
      const folded = query.toLowerCase();
      const hits = index.filter(function (word) {
        return word.w.toLowerCase().includes(folded) || (word.z || '').includes(query);
      }).slice(0, 30);
      if (hits.length) {
        wordHtml = '<h2 class="sub">单词</h2>' + hits.map(function (word) {
          return '<a class="row" href="?w=' + encodeURIComponent(word.w) + '"><b>' + esc(word.w) + '</b><span>' + esc(word.z || '暂无中文') + '</span><small>' + (word.m || []).length + ' 个词根</small></a>';
        }).join('');
      }
    }
    const visible = items.slice(0, state.shown);
    const more = items.length > visible.length ? '<button type="button" class="more" id="more">再显示 ' + Math.min(80, items.length - visible.length) + ' 个</button>' : '';
    main.innerHTML = '<p class="lead">先看一个词根，再认一串单词。</p><p class="sub">这里有 ' + stats.roots + ' 个词根、' + (stats.prefixes + stats.suffixes) + ' 个词缀，例词后面是中文。默认只列出最常用的 ' + stats.core + ' 个。</p>' + filters() + '<p class="count">' + items.length + ' 条</p><div class="grid">' + (visible.map(card).join('') || '<p class="empty">没有匹配的词根。</p>') + '</div>' + more + wordHtml;
    const moreButton = document.getElementById('more');
    if (moreButton) moreButton.onclick = function () { state.shown += 80; showHome(current); };
  }

  async function showMorph(id) {
    setTab('roots');
    let detail;
    try {
      detail = await load('data/m/' + encodeURIComponent(id) + '.json');
    } catch (error) {
      main.innerHTML = '<p class="empty">没有这个词根。<a href="./">回到列表</a></p>';
      return;
    }
    const story = detail.story ? '<div class="story"><p>' + esc(detail.story.zh) + '</p><p class="meta">词源小记的译文。原文出处：<a href="' + esc(detail.story.source) + '" rel="noreferrer">' + esc(detail.story.source) + '</a></p><p class="en">' + esc(detail.story.en) + '</p></div>' : '';
    const words = (detail.words || []).map(function (word) { return wordBlock(word, true); }).join('') || '<p class="empty">这个条目没有例词。</p>';
    main.innerHTML = '<p><a class="back" href="./">← 词根列表</a></p><article class="panel"><div class="kicker"><span class="pill">' + KIND[detail.kind] + '</span><span class="pill">' + (LANG[detail.lang] || esc(detail.lang)) + '</span></div><h1 class="form">' + esc(detail.forms) + '</h1><p class="zh">' + esc(detail.zh) + '</p><p class="en">' + esc(detail.en) + '</p><p class="origin">' + esc(detail.origin) + '</p><p class="meta">中文是这条英文释义的译文，不是另写的定义。</p>' + story + '</article><h2 class="sub">例词 · ' + detail.words.length + '</h2>' + words;
  }

  async function showWord(spelling) {
    setTab('roots');
    const index = await load('data/words-index.json');
    const hit = index.find(function (word) { return word.w.toLowerCase() === spelling.toLowerCase(); });
    if (!hit || !hit.m || !hit.m.length) {
      main.innerHTML = '<p class="empty">词根表里没有这个例词。<a href="./">回到列表</a></p>';
      return;
    }
    const detail = await load('data/m/' + encodeURIComponent(hit.m[0]) + '.json');
    const word = (detail.words || []).find(function (item) { return item.w.toLowerCase() === spelling.toLowerCase(); });
    if (!word) {
      main.innerHTML = '<p class="empty">没有找到这个单词。</p>';
      return;
    }
    main.innerHTML = '<p><a class="back" href="./">← 词根列表</a></p><article class="word">' + wordBlock(word, false).replace(/^<article class="word">|<\/article>$/g, '') + knownLine(word) + '<button type="button" class="speak" id="speak">朗读</button></article>';
    document.getElementById('speak').onclick = function () {
      if (!window.speechSynthesis) return;
      const utter = new SpeechSynthesisUtterance(word.w);
      utter.lang = 'en-US';
      utter.rate = 0.86;
      speechSynthesis.cancel();
      speechSynthesis.speak(utter);
    };
  }

  async function showList(tag, query) {
    setTab('lists');
    const chosen = LISTS.indexOf(tag) >= 0 ? tag : 'cet4';
    const data = await load('data/lists/' + chosen + '.json');
    const folded = query.toLowerCase();
    const rows = data.words.filter(function (word) {
      if (!query) return true;
      return word.w.toLowerCase().includes(folded) || (word.z || '').includes(query);
    });
    const visible = rows.slice(0, state.shown);
    const chips = LISTS.map(function (item) {
      const href = query ? '?list=' + item + '&q=' + encodeURIComponent(query) : '?list=' + item;
      return '<a class="chip' + (item === chosen ? ' on' : '') + '" href="' + href + '">' + TAGS[item] + '</a>';
    }).join('');
    const body = visible.map(function (word) {
      const label = '<b>' + esc(word.w) + '</b><span>' + esc(word.z || '暂无中文') + '</span><small>' + esc(tagText(word.t)) + (word.p ? ' · /' + esc(word.p) + '/' : '') + '</small>';
      if (word.m && word.m.length) return '<a class="row" href="?w=' + encodeURIComponent(word.w) + '">' + label + '</a>';
      return '<div class="row plain">' + label + '</div>';
    }).join('');
    const more = rows.length > visible.length ? '<button type="button" class="more" id="more">再显示 ' + Math.min(120, rows.length - visible.length) + ' 个</button>' : '';
    main.innerHTML = '<p class="lead">' + esc(data.label) + '</p><p class="sub">' + esc(data.code) + ' · ' + data.count + ' 词，其中 ' + data.withZh + ' 个有中文，' + data.linked + ' 个能连到词根。点进有词根的词，可以看拆分。</p><div class="filters">' + chips + '</div><p class="count">当前 ' + rows.length + ' 条</p>' + body + more;
    const moreButton = document.getElementById('more');
    if (moreButton) moreButton.onclick = function () { state.shown += 120; showList(chosen, query); };
  }

  function showAbout(stats) {
    setTab('about');
    const lists = LISTS.map(function (tag) {
      const item = stats.lists[tag];
      return '<li>' + TAGS[tag] + '：' + item.count + ' 词，有中文 ' + item.withZh + '，连到词根 ' + item.linked + '</li>';
    }).join('');
    const missing = stats.missing.length
      ? '<p>例词里有 <strong>' + stats.memberWithoutZh + '</strong> 个在 ECDICT 里没有中文：' + esc(stats.missing.join('、')) + '。</p>'
      : '<p>例词全部对上了中文。</p>';
    main.innerHTML = '<article class="panel"><h1 class="form">这份页面从哪来</h1><p>浏览顺序参考 <a href="https://wordiyo.com">Wordiyo</a>：词根列表，点进去看意义、来源和同根词。Wordiyo 的仓库是 MIT，版权属于 Wordiyo（2026）。它的词库不在仓库里，网站条款也不允许抓取，所以这里没有用它的词条，也没有抄它的程序。</p><p>词根、词缀、例词、拆分和词源小记改编自 <a href="https://github.com/jupsh/anki-word-roots">anki-word-roots</a>（提交 ' + esc(stats.ankiCommit.slice(0, 7)) + '），许可是 <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>。上游来自维基百科《List of Greek and Latin roots in English》和医学词根表，贡献者同样以 CC BY-SA 4.0 授权。</p><p>词根和词缀旁边的中文，是那条英文释义的译文，存在构建用的对照表里。译文跟着 CC BY-SA 4.0 一起授权，不另编定义。</p><p>单词的中文、音标和考试标签来自 <a href="https://github.com/skywind3000/ECDICT">ECDICT</a>（提交 ' + esc(stats.ecdictCommit.slice(0, 7)) + '，MIT，版权 Linwei，2025）。对不上的词就空着，不补一句。</p><h2>覆盖</h2><ul><li>词根 ' + stats.roots + '，前缀 ' + stats.prefixes + '，后缀 ' + stats.suffixes + '</li><li>拉丁语 ' + stats.latin + '，希腊语 ' + stats.greek + '，两者都有 ' + stats.latinAndGreek + '</li><li>例词 ' + stats.memberWords + '，有中文 ' + stats.memberWithZh + '，没有中文 ' + stats.memberWithoutZh + '</li><li>带完整拆分的 decode 词 ' + stats.decodeWords + '，词源小记 ' + stats.stories + '</li></ul>' + missing + '<h2>考试词表</h2><ul>' + lists + '</ul><p>词表里的中文也只来自 ECDICT。能连到词根的，才有构词拆分。</p><p><a href="NOTICE.txt">完整许可与出处</a></p></article>';
  }

  async function render() {
    const current = route();
    if (location.search !== state.routeKey) {
      state.routeKey = location.search;
      state.shown = 80;
    }
    syncQuery(current.q);
    try {
      state.catalog = state.catalog || await load('data/catalog.json');
      if (current.about) showAbout(state.catalog.stats);
      else if (current.list) await showList(current.list, current.q.trim());
      else if (current.m) await showMorph(current.m);
      else if (current.w) await showWord(current.w);
      else await showHome(current);
    } catch (error) {
      main.innerHTML = '<p class="empty">词条没有载入。' + esc(error.message) + '</p>';
    }
  }

  document.getElementById('theme').addEventListener('click', function () {
    const order = ['system', 'dark', 'light'];
    const mode = localStorage.getItem('roots-theme') || 'system';
    localStorage.setItem('roots-theme', order[(order.indexOf(mode) + 1) % order.length]);
    paintTheme();
  });
  document.getElementById('search').addEventListener('submit', function (event) {
    event.preventDefault();
    const value = document.getElementById('q').value.trim();
    const current = route();
    if (current.list) go({list: current.list, q: value});
    else go({q: value});
  });
  document.body.addEventListener('click', function (event) {
    const button = event.target.closest('[data-filter]');
    if (button) {
      state[button.dataset.filter] = button.dataset.value;
      state.shown = 80;
      showHome(route());
      return;
    }
    const link = event.target.closest('a');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href || href === './' || href.startsWith('?')) {
      event.preventDefault();
      history.pushState(null, '', href && href !== './' ? href : location.pathname);
      render();
      window.scrollTo(0, 0);
    }
  });
  window.addEventListener('popstate', render);
  paintTheme();
  render();
})();

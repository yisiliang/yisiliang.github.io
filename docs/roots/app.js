(function () {
  const TAGS = {cet4: '四级', cet6: '六级', ielts: '雅思', toefl: '托福', gre: 'GRE', zk: '中考'};
  const LISTS = ['cet4', 'cet6', 'ielts', 'toefl', 'gre', 'zk'];
  const KIND = {root: '词根', prefix: '前缀', suffix: '后缀'};
  const LANG = {Latin: '拉丁语', Greek: '希腊语', 'Latin and Greek': '拉丁语 / 希腊语'};
  const BOOK_KEY = 'roots-book';
  const main = document.getElementById('main');
  const cache = new Map();
  const state = {scope: 'core', kind: 'all', lang: 'all', shown: 80, routeKey: ''};
  const tap = {word: '', n: 0, at: 0, timer: 0};
  const DOUBLE_TAP_MS = 300;

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
      book: params.get('book') === '1',
      review: params.get('review') === '1',
      plan: params.get('plan') === '1',
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
  function loadBook() {
    try {
      const data = JSON.parse(localStorage.getItem(BOOK_KEY) || '[]');
      return Array.isArray(data) ? data.filter(function (item) { return item && item.w; }) : [];
    } catch (error) {
      return [];
    }
  }
  function bookHas(word) {
    const key = String(word || '').toLowerCase();
    return loadBook().some(function (item) { return item.w.toLowerCase() === key; });
  }
  function paintBookCount() {
    const count = document.getElementById('book-count');
    if (!count) return;
    const n = loadBook().length;
    count.textContent = n ? String(n) : '';
    count.hidden = !n;
  }
  function saveBook(items) {
    localStorage.setItem(BOOK_KEY, JSON.stringify(items));
    paintBookCount();
  }
  let toastTimer = 0;
  let currentUtterance = null;
  function englishVoice(voices) {
    let best = null;
    let bestScore = 0;
    (voices || []).forEach(function (voice) {
      const lang = String(voice.lang || '').toLowerCase().replace('_', '-');
      if (lang.indexOf('en') !== 0) return;
      let score = 1;
      if (lang === 'en-us') score += 4;
      else if (lang === 'en-gb') score += 3;
      if (voice.localService) score += 2;
      if (/samantha|alex|daniel|karen|moira|serena|google us english/.test(String(voice.name || '').toLowerCase())) score += 1;
      if (score > bestScore) {
        bestScore = score;
        best = voice;
      }
    });
    return best;
  }
  function speakText(text, button) {
    const synth = window.speechSynthesis;
    if (!synth || typeof SpeechSynthesisUtterance !== 'function') {
      toast('这台浏览器不能朗读');
      if (button) button.dataset.speech = 'unsupported';
      return;
    }
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'en-US';
    utter.rate = 0.9;
    utter.volume = 1;
    const voice = englishVoice(synth.getVoices());
    if (voice) utter.voice = voice;
    // Safari drops the utterance if nothing keeps a reference after the click returns.
    currentUtterance = utter;
    if (button) {
      button.dataset.speech = 'requested';
      utter.onstart = function () {
        button.dataset.speech = 'started';
        button.textContent = '朗读中';
      };
      utter.onend = function () {
        if (currentUtterance === utter) currentUtterance = null;
        button.dataset.speech = 'ended';
        button.textContent = '朗读';
      };
    }
    utter.onerror = function (event) {
      const code = event && event.error ? event.error : '';
      if (code === 'canceled' || code === 'interrupted') return;
      if (button) {
        button.dataset.speech = 'error:' + code;
        button.textContent = '朗读';
      }
      toast('没有读出来');
    };
    const start = function () {
      synth.resume();
      synth.speak(currentUtterance);
      if (synth.paused) synth.resume();
    };
    // cancel() in the same turn as speak() silently drops the new utterance on Chrome and iOS.
    if (synth.speaking || synth.pending) {
      synth.cancel();
      setTimeout(function () {
        if (currentUtterance !== utter) return;
        synth.resume();
        synth.speak(utter);
        if (synth.paused) synth.resume();
      }, 60);
    } else {
      start();
    }
  }
  function toast(message) {
    const node = document.getElementById('toast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { node.classList.remove('show'); }, 1600);
  }
  function wordData(word, zh, ipa, root) {
    return ' data-word="' + esc(word) + '" data-zh="' + esc(zh || '') + '" data-ipa="' + esc(ipa || '') + '" data-root="' + esc(root || '') + '"';
  }
  function star(word) {
    return bookHas(word) ? '<span class="star">已收入</span>' : '';
  }
  function clearTap() {
    clearTimeout(tap.timer);
    tap.timer = 0;
    tap.n = 0;
    tap.word = '';
  }
  let confirmAction = null;
  function openConfirm(text, yes, no, action) {
    document.getElementById('confirm-text').textContent = text;
    document.getElementById('confirm-yes').textContent = yes;
    document.getElementById('confirm-no').textContent = no;
    confirmAction = action;
    document.getElementById('confirm').hidden = false;
  }
  function handleBookTap(el) {
    const word = el.dataset.word;
    const now = Date.now();
    if (tap.word !== 'book:' + word || now - tap.at > DOUBLE_TAP_MS) tap.n = 0;
    tap.word = 'book:' + word;
    tap.n += 1;
    tap.at = now;
    clearTimeout(tap.timer);
    if (tap.n >= 2) {
      tap.n = 0;
      openConfirm('把 ' + word + ' 移出生词本？', '移除', '保留', function () {
        const items = loadBook().filter(function (item) { return item.w.toLowerCase() !== word.toLowerCase(); });
        saveBook(items);
        const kept = Number(localStorage.getItem(REVIEW_KEY) || 0);
        if (kept >= items.length) localStorage.setItem(REVIEW_KEY, String(Math.max(0, items.length - 1)));
        toast('已移出：' + word);
        showBook();
      });
    }
  }
  async function addSpecial(el) {
    const word = el.dataset.word;
    const items = loadBook();
    if (items.some(function (item) { return item.w.toLowerCase() === word.toLowerCase(); })) {
      el.classList.add('saved');
      toast(word + ' 已经在生词本里');
      return;
    }
    const entry = {w: word, z: el.dataset.zh || '', p: el.dataset.ipa || '', m: el.dataset.root || '', at: Date.now()};
    if (entry.m && !entry.p) {
      try {
        const detail = await load('data/m/' + encodeURIComponent(entry.m) + '.json');
        const found = (detail.words || []).find(function (item) { return item.w.toLowerCase() === word.toLowerCase(); });
        if (found) {
          if (!entry.z) entry.z = found.zh || '';
          if (!entry.p) entry.p = found.ipa || '';
        }
      } catch (error) { /* keep the gloss already on the card */ }
    }
    items.unshift(entry);
    saveBook(items);
    el.classList.add('saved');
    if (!el.querySelector('.star')) el.insertAdjacentHTML('beforeend', '<span class="star">已收入</span>');
    toast('已加入生词本：' + word);
  }
  function handleWordClick(event, el) {
    const word = el.dataset.word;
    const href = el.getAttribute('href') || '';
    const now = Date.now();
    if (tap.word !== word || now - tap.at > DOUBLE_TAP_MS) tap.n = 0;
    tap.word = word;
    tap.n += 1;
    tap.at = now;
    clearTimeout(tap.timer);
    tap.timer = 0;
    event.preventDefault();
    event.stopPropagation();
    if (el.dataset.planIndex) rememberPlan(Number(el.dataset.planIndex));
    if (tap.n >= 2) {
      tap.n = 0;
      addSpecial(el);
      return;
    }
    if (href.charAt(0) === '?') {
      const target = href;
      const watched = word;
      tap.timer = setTimeout(function () {
        if (tap.word !== watched) return;
        tap.n = 0;
        history.pushState(null, '', target);
        render();
        window.scrollTo(0, 0);
      }, DOUBLE_TAP_MS);
    }
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
    const root = word.known && word.known[0] ? word.known[0].id : '';
    const saved = bookHas(word.w) ? ' saved' : '';
    if (!link) return '<article class="word' + saved + '">' + body + '</article>';
    return '<a class="word' + saved + '" href="?w=' + encodeURIComponent(word.w) + '"' + wordData(word.w, word.zh, word.ipa, root) + '>' + body + star(word.w) + '</a>';
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
        wordHtml = '<h2 class="sub">单词</h2><p class="count">连点两次，收入生词本。</p>' + hits.map(function (word) {
          const root = word.m && word.m[0] ? word.m[0] : '';
          return '<a class="row' + (bookHas(word.w) ? ' saved' : '') + '" href="?w=' + encodeURIComponent(word.w) + '"' + wordData(word.w, word.z, '', root) + '><b>' + esc(word.w) + '</b><span>' + esc(word.z || '暂无中文') + '</span><small>' + (word.m || []).length + ' 个词根</small>' + star(word.w) + '</a>';
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
    main.innerHTML = '<p><a class="back" href="./">← 词根列表</a></p><article class="panel"><div class="kicker"><span class="pill">' + KIND[detail.kind] + '</span><span class="pill">' + (LANG[detail.lang] || esc(detail.lang)) + '</span></div><h1 class="form">' + esc(detail.forms) + '</h1><p class="zh">' + esc(detail.zh) + '</p><p class="en">' + esc(detail.en) + '</p><p class="origin">' + esc(detail.origin) + '</p><p class="meta">中文是这条英文释义的译文，不是另写的定义。连点两次例词，收入生词本。</p>' + story + '</article><h2 class="sub">例词 · ' + detail.words.length + '</h2>' + words;
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
    main.innerHTML = '<p><a class="back" href="./">← 词根列表</a></p><article class="word">' + wordBlock(word, false).replace(/^<article class="word">|<\/article>$/g, '') + knownLine(word) + '<button type="button" class="speak" id="speak" data-speak="' + esc(word.w) + '">朗读</button></article>';
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
      const root = word.m && word.m[0] ? word.m[0] : '';
      const saved = bookHas(word.w) ? ' saved' : '';
      const label = '<b>' + esc(word.w) + '</b><span>' + esc(word.z || '暂无中文') + '</span><small>' + esc(tagText(word.t)) + (word.p ? ' · /' + esc(word.p) + '/' : '') + '</small>' + star(word.w);
      const attrs = wordData(word.w, word.z, word.p, root);
      if (root) return '<a class="row' + saved + '" href="?w=' + encodeURIComponent(word.w) + '"' + attrs + '>' + label + '</a>';
      return '<div class="row plain' + saved + '"' + attrs + '>' + label + '</div>';
    }).join('');
    const more = rows.length > visible.length ? '<button type="button" class="more" id="more">再显示 ' + Math.min(120, rows.length - visible.length) + ' 个</button>' : '';
    main.innerHTML = '<p class="lead">' + esc(data.label) + '</p><p class="sub">' + esc(data.code) + ' · ' + data.count + ' 词，其中 ' + data.withZh + ' 个有中文，' + data.linked + ' 个能连到词根。点进有词根的词，可以看拆分。连点两次，收入生词本。</p><div class="filters">' + chips + '</div><p class="count">当前 ' + rows.length + ' 条</p>' + body + more;
    const moreButton = document.getElementById('more');
    if (moreButton) moreButton.onclick = function () { state.shown += 120; showList(chosen, query); };
  }

  const PLAN_KEY = 'roots-plan';
  const REVIEW_KEY = 'roots-review';
  const PLAN_LEVELS = [
    {tag: 'cet4', name: '四级'},
    {tag: 'cet6', name: '六级'},
    {tag: 'ielts', name: '雅思'},
    {tag: 'toefl', name: '托福'},
    {tag: 'gre', name: 'GRE'}
  ];
  const BATCH_CHOICES = [100, 500, 1000, 2000];
  let curriculum = null;
  function loadPlan() {
    try {
      const data = JSON.parse(localStorage.getItem(PLAN_KEY) || '{}');
      const batchSize = BATCH_CHOICES.indexOf(data.batchSize) >= 0 ? data.batchSize : 1000;
      const position = Number.isInteger(data.position) ? data.position : -1;
      return {position: position, batchSize: batchSize};
    } catch (error) {
      return {position: -1, batchSize: 1000};
    }
  }
  function savePlan(plan) {
    localStorage.setItem(PLAN_KEY, JSON.stringify({position: plan.position, batchSize: plan.batchSize}));
  }
  function rememberPlan(index) {
    const plan = loadPlan();
    if (index <= plan.position) return;
    const currentBatch = plan.position < 0 ? 0 : Math.floor(plan.position / plan.batchSize);
    const indexBatch = Math.floor(index / plan.batchSize);
    if (indexBatch > currentBatch + 1) return;
    plan.position = index;
    savePlan(plan);
    paintPlanProgress();
    document.querySelectorAll('.row.here').forEach(function (row) { row.classList.remove('here'); });
    const here = document.getElementById('plan-word-' + index);
    if (here) here.classList.add('here');
  }
  async function getCurriculum() {
    if (curriculum) return curriculum;
    const seen = new Set();
    const words = [];
    const levels = [];
    for (let i = 0; i < PLAN_LEVELS.length; i += 1) {
      const level = PLAN_LEVELS[i];
      const data = await load('data/lists/' + level.tag + '.json');
      const start = words.length;
      (data.words || []).forEach(function (word) {
        const key = String(word.w || '').toLowerCase();
        if (!key || seen.has(key)) return;
        seen.add(key);
        words.push({
          w: word.w,
          z: word.z || '',
          p: word.p || '',
          m: word.m && word.m[0] ? word.m[0] : '',
          level: level.tag,
          levelName: level.name
        });
      });
      levels.push({tag: level.tag, name: level.name, start: start, end: words.length});
    }
    curriculum = {words: words, levels: levels};
    return curriculum;
  }
  function teardownPlan() {
    if (state.planObserver) state.planObserver.disconnect();
    if (state.planScroll) window.removeEventListener('scroll', state.planScroll);
    state.planObserver = null;
    state.planScroll = null;
  }
  function paintPlanProgress() {
    if (!curriculum || !document.getElementById('plan-read')) return;
    const plan = loadPlan();
    const total = curriculum.words.length;
    const read = plan.position < 0 ? 0 : Math.min(total, plan.position + 1);
    document.getElementById('plan-read').textContent = read + ' / ' + total;
    const overall = document.getElementById('plan-overall');
    if (overall) overall.style.width = (total ? 100 * read / total : 0) + '%';
    curriculum.levels.forEach(function (level) {
      const row = document.getElementById('lvl-' + level.tag);
      if (!row) return;
      const size = level.end - level.start;
      const done = plan.position < level.start ? 0 : Math.min(size, plan.position + 1 - level.start);
      row.querySelector('b').textContent = done + ' / ' + size;
      row.querySelector('.barline span').style.width = (size ? 100 * done / size : 0) + '%';
    });
    const banner = document.getElementById('plan-banner');
    if (!banner) return;
    const size = plan.batchSize;
    const finishedChunk = plan.position >= 0 && (plan.position + 1) % size === 0;
    banner.hidden = !finishedChunk;
    if (!finishedChunk) return;
    const doneAll = plan.position + 1 >= total;
    const n = (plan.position + 1) / size;
    banner.querySelector('p').textContent = doneAll
      ? '词表读完了。生词本可以再过一遍。'
      : '第 ' + n + ' 段读完了。可以马上读下一段，也可以先复习生词本。';
    const next = document.getElementById('plan-next');
    if (next) next.hidden = doneAll;
  }
  async function showPlan() {
    setTab('plan');
    teardownPlan();
    main.innerHTML = '<p class="loading">正在按四级、六级、雅思的顺序排词…</p>';
    const seq = state.renderSeq;
    const book = await getCurriculum();
    if (seq !== state.renderSeq) return;
    const plan = loadPlan();
    const total = book.words.length;
    if (plan.position >= total) plan.position = total - 1;
    const size = plan.batchSize;
    const resumeAt = plan.position < 0 ? 0 : plan.position;
    const view = state.planView == null ? Math.floor(resumeAt / size) : state.planView;
    const batchCount = Math.max(1, Math.ceil(total / size));
    const safeView = Math.max(0, Math.min(batchCount - 1, view));
    const start = safeView * size;
    const slice = book.words.slice(start, Math.min(total, start + size));
    const day = Math.floor(resumeAt / size) + 1;
    const levels = book.levels.map(function (level) {
      const count = level.end - level.start;
      return '<div class="level" id="lvl-' + level.tag + '"><div>' + level.name + ' <b>0 / ' + count + '</b></div><div class="barline"><span></span></div></div>';
    }).join('');
    const sizes = BATCH_CHOICES.map(function (choice) {
      return '<button type="button" class="chip' + (choice === size ? ' on' : '') + '" data-batch="' + choice + '">每段 ' + choice + '</button>';
    }).join('');
    const options = [];
    for (let batch = 0; batch < batchCount; batch += 1) {
      const from = batch * size + 1;
      const to = Math.min(total, (batch + 1) * size);
      options.push('<option value="' + batch + '"' + (batch === safeView ? ' selected' : '') + '>第 ' + (batch + 1) + ' 段 · ' + from + '–' + to + '</option>');
    }
    let lastLevel = '';
    const rows = slice.map(function (word, offset) {
      const index = start + offset;
      const root = word.m || '';
      const saved = bookHas(word.w) ? ' saved' : '';
      const here = index === resumeAt ? ' here' : '';
      const levelMark = word.level !== lastLevel ? '<span class="pill">' + esc(word.levelName) + '</span>' : '';
      lastLevel = word.level;
      const label = '<b>' + esc(word.w) + '</b><span>' + esc(word.z || '暂无中文') + '</span><small>' + levelMark + (word.p ? ' /' + esc(word.p) + '/' : '') + '</small>' + star(word.w);
      const attrs = wordData(word.w, word.z, word.p, root) + ' data-plan-index="' + index + '"';
      if (root) return '<a class="row' + saved + here + '" id="plan-word-' + index + '" href="?w=' + encodeURIComponent(word.w) + '"' + attrs + '>' + label + '</a>';
      return '<div class="row plain' + saved + here + '" id="plan-word-' + index + '"' + attrs + '>' + label + '</div>';
    }).join('');
    const resumeWord = book.words[resumeAt];
    main.innerHTML = '<p class="lead">第 ' + (safeView + 1) + ' 段</p><p class="sub">第 ' + day + ' 天只是进度标签。一段读完可以马上读下一段。停在半路，下次从最后一个词接着读。连点两次不认识的词，收入生词本。进度只存在这台浏览器里。</p>'
      + '<button type="button" class="plan-continue" id="plan-continue">从「' + esc(resumeWord.w) + '」继续<small>第 ' + (resumeAt + 1) + ' 个词 · 已读 <span id="plan-read">0 / ' + total + '</span></small></button>'
      + '<div id="plan-banner" class="plan-banner" hidden><p></p><div class="book-actions"><button type="button" id="plan-next">继续下一段</button><button type="button" id="plan-review">复习生词本</button></div></div>'
      + '<div class="levels">' + levels + '<div class="level">总进度<div class="barline"><span id="plan-overall"></span></div></div></div>'
      + '<div class="filters" aria-label="每段词数">' + sizes + '</div>'
      + '<label class="count" for="plan-jump">查看某一段</label><select id="plan-jump" class="plan-jump">' + options.join('') + '</select>'
      + rows;
    paintPlanProgress();
    document.getElementById('plan-continue').onclick = function () {
      state.planView = null;
      state.planScrollTo = loadPlan().position < 0 ? 0 : loadPlan().position;
      showPlan();
    };
    document.getElementById('plan-next').onclick = function () {
      const next = Math.min(total - 1, loadPlan().position + 1);
      state.planView = Math.floor(next / loadPlan().batchSize);
      state.planScrollTo = next;
      state.planArm = true;
      showPlan();
    };
    document.getElementById('plan-review').onclick = function () { go({book: '1', review: '1'}); };
    document.getElementById('plan-jump').onchange = function (event) {
      state.planView = Number(event.target.value);
      state.planScrollTo = state.planView * loadPlan().batchSize;
      showPlan();
    };
    const scrollTo = state.planScrollTo;
    state.planScrollTo = null;
    if (scrollTo != null) {
      const target = document.getElementById('plan-word-' + scrollTo);
      if (target) target.scrollIntoView({block: 'start'});
    }
    let armed = false;
    state.planScroll = function () { armed = true; };
    window.addEventListener('scroll', state.planScroll, {passive: true});
    state.planObserver = new IntersectionObserver(function (entries) {
      if (!armed && !state.planArm) return;
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        rememberPlan(Number(entry.target.dataset.planIndex));
      });
    }, {root: null, rootMargin: '0px 0px -72% 0px', threshold: 0.6});
    main.querySelectorAll('[data-plan-index]').forEach(function (row) { state.planObserver.observe(row); });
    state.planArm = false;
  }

  function reviewIndex(length) {
    const raw = Number(localStorage.getItem(REVIEW_KEY) || 0);
    if (!length) return 0;
    return Math.max(0, Math.min(length - 1, raw || 0));
  }
  function bookAttrs(item) {
    return ' data-book-word="1"' + wordData(item.w, item.z, item.p, item.m || '');
  }
  function showBook() {
    setTab('book');
    const items = loadBook();
    const current = route();
    if (current.review) {
      if (!items.length) {
        main.innerHTML = '<p class="lead">复习生词</p><p class="empty">生词本是空的。<a href="?book=1">回到列表</a></p>';
        return;
      }
      const index = reviewIndex(items.length);
      localStorage.setItem(REVIEW_KEY, String(index));
      const item = items[index];
      const root = item.m ? '<a href="?m=' + encodeURIComponent(item.m) + '">看词根</a>' : '没有对应词根';
      main.innerHTML = '<p class="lead">复习生词</p><p class="sub">' + (index + 1) + ' / ' + items.length + ' · 连点两次这个词可以移出。名单还在这台浏览器里。</p>'
        + '<article class="word review saved"' + bookAttrs(item) + '><h2 class="form">' + esc(item.w) + '</h2><p class="zh">' + esc(item.z || '暂无中文') + '</p><p class="meta">' + (item.p ? '/' + esc(item.p) + '/ · ' : '') + root + '</p><button type="button" class="speak" data-speak="' + esc(item.w) + '">朗读</button></article>'
        + '<div class="book-actions"><button type="button" id="rev-prev">上一个</button><button type="button" id="rev-next">下一个</button></div>'
        + '<p><a class="back" href="?book=1">回到生词列表</a></p>';
      document.getElementById('rev-prev').onclick = function () {
        localStorage.setItem(REVIEW_KEY, String(Math.max(0, index - 1)));
        showBook();
      };
      document.getElementById('rev-next').onclick = function () {
        localStorage.setItem(REVIEW_KEY, String(Math.min(items.length - 1, index + 1)));
        showBook();
      };
      return;
    }
    const cards = items.map(function (item) {
      const root = item.m ? '<a href="?m=' + encodeURIComponent(item.m) + '">词根</a>' : '没有对应词根';
      const open = item.m ? ' · <a href="?w=' + encodeURIComponent(item.w) + '">单词页</a>' : '';
      return '<article class="word saved"' + bookAttrs(item) + '><h3>' + esc(item.w) + '</h3><p class="zh">' + esc(item.z || '暂无中文') + '</p><p class="meta">' + (item.p ? '/' + esc(item.p) + '/ · ' : '') + root + open + '</p></article>';
    }).join('');
    const tools = items.length ? '<div class="book-actions"><a class="more" href="?book=1&review=1">复习这些词</a><button type="button" class="more" id="copy-book">复制为文本</button><button type="button" class="more" id="clear-book">清空生词本</button></div>' : '';
    main.innerHTML = '<p class="lead">生词本 · ' + items.length + '</p><p class="sub">连点两次不认识的词，会记在这里，换级别也不会丢。连点两次下面的词，再确认，才会移出。这份名单只存在这台浏览器里。</p>' + tools + (cards || '<p class="empty">还没有生词。在计划、词根例词、搜索结果或考试词表里，对一个单词连点两次。</p>');
    const copy = document.getElementById('copy-book');
    if (copy) copy.onclick = function () {
      const text = items.map(function (item) {
        return [item.w, item.z || '', item.p ? '/' + item.p + '/' : ''].filter(Boolean).join('\t');
      }).join('\n');
      const done = function () { toast('已复制 ' + items.length + ' 个词'); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { toast('复制没有成功'); });
      } else toast('这台浏览器不能复制');
    };
    const clear = document.getElementById('clear-book');
    if (clear) clear.onclick = function () {
      openConfirm('清空生词本？里面的 ' + items.length + ' 个词都会删掉。', '移除全部', '保留', function () {
        saveBook([]);
        toast('生词本已清空');
        showBook();
      });
    };
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
    state.renderSeq = (state.renderSeq || 0) + 1;
    teardownPlan();
    const current = route();
    if (location.search !== state.routeKey) {
      state.routeKey = location.search;
      state.shown = 80;
      if (!current.plan) state.planView = null;
    }
    syncQuery(current.q);
    try {
      state.catalog = state.catalog || await load('data/catalog.json');
      if (current.about) showAbout(state.catalog.stats);
      else if (current.plan) await showPlan();
      else if (current.book) showBook();
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
    const batchBtn = event.target.closest('[data-batch]');
    if (batchBtn) {
      event.preventDefault();
      clearTap();
      const plan = loadPlan();
      plan.batchSize = Number(batchBtn.dataset.batch);
      savePlan(plan);
      state.planView = null;
      showPlan();
      return;
    }
    const button = event.target.closest('[data-filter]');
    if (button) {
      clearTap();
      state[button.dataset.filter] = button.dataset.value;
      state.shown = 80;
      showHome(route());
      return;
    }
    const speakBtn = event.target.closest('[data-speak]');
    if (speakBtn) {
      event.preventDefault();
      clearTap();
      speakText(speakBtn.dataset.speak, speakBtn);
      return;
    }
    if (event.target.closest('button')) return;
    const directLink = event.target.closest('a');
    if (directLink && !directLink.hasAttribute('data-word')) {
      clearTap();
      const href = directLink.getAttribute('href') || '';
      if (href === './' || href.charAt(0) === '?') {
        event.preventDefault();
        history.pushState(null, '', href === './' ? location.pathname : href);
        render();
        window.scrollTo(0, 0);
      }
      return;
    }
    const bookEl = event.target.closest('[data-book-word]');
    if (bookEl && !event.target.closest('a')) {
      handleBookTap(bookEl);
      return;
    }
    const wordEl = event.target.closest('[data-word]');
    if (wordEl && main.contains(wordEl)) {
      handleWordClick(event, wordEl);
      return;
    }
    clearTap();
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
  window.addEventListener('popstate', function () { clearTap(); render(); });
  if (window.speechSynthesis) {
    speechSynthesis.getVoices();
    speechSynthesis.onvoiceschanged = function () { speechSynthesis.getVoices(); };
  }
  document.getElementById('confirm-no').onclick = function () {
    document.getElementById('confirm').hidden = true;
    confirmAction = null;
  };
  document.getElementById('confirm-yes').onclick = function () {
    document.getElementById('confirm').hidden = true;
    const action = confirmAction;
    confirmAction = null;
    if (action) action();
  };
  document.getElementById('confirm').addEventListener('click', function (event) {
    if (event.target.id === 'confirm') document.getElementById('confirm-no').click();
  });
  paintTheme();
  paintBookCount();
  render();
})();

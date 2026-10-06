/* Independent current-date reader. Stale, missing or failed production is PENDING. */
(() => {
  'use strict';
  const root = document.querySelector('[data-daily-headlines]');
  if (!root) return;
  const grid = root.querySelector('.dh-grid');
  const state = root.querySelector('.dh-state');
  const dateLabel = root.querySelector('[data-dh-date]');
  const action = root.querySelector('.dh-action');
  const dateInShanghai = () => new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(new Date());
  const pending = () => {
    grid.replaceChildren(); grid.hidden = true; state.hidden = false;
    state.replaceChildren(document.createTextNode('今日情报更新待完成'));
    const en = document.createElement('span'); en.textContent = 'Daily Intelligence Update Pending'; state.append(en);
    dateLabel.textContent = dateInShanghai(); action.href = '/intelligence/daily-headlines/';
  };
  const element = (tag, cls, value) => {
    const node = document.createElement(tag); node.className = cls; node.textContent = value; return node;
  };
  let request = 0;
  async function refresh() {
    const token = ++request; pending();
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch('/data/daily-headlines/latest.json', {cache:'no-store',signal:controller.signal});
      if (!response.ok) throw new Error('Unavailable');
      const data = await response.json();
      if (token !== request) return;
      if (data.schema_version !== 1 || data.date !== dateInShanghai() || !Array.isArray(data.headlines)) throw new Error('Stale or malformed');
      if (!['PUBLISHED','NO_MATERIAL_CHANGE'].includes(data.status)) throw new Error('Incomplete');
      if (data.status === 'NO_MATERIAL_CHANGE') {
        if (data.headlines.length) throw new Error('Invalid empty state');
        state.replaceChildren(document.createTextNode('今日暂无重大情报变化'),element('span','','No Material Intelligence Change'));
      } else {
        if (!data.headlines.length || data.headlines.length > 5) throw new Error('Invalid count');
        for (const h of data.headlines.slice(0,3)) {
          if (h.date !== data.date || !h.headline_cn || !h.summary || !h.category || !['CONFIRMED','PARTIAL','DEVELOPING'].includes(h.confidence)) throw new Error('Invalid headline');
          const card = element('article','dh-card','');
          const meta = element('div','dh-meta','');
          meta.append(element('span','dh-category',h.category));
          if (h.time) meta.append(element('span','',h.time+' CST'));
          card.append(meta,element('h3','',h.headline_cn),element('p','',h.summary));
          if (h.confidence !== 'CONFIRMED') card.append(element('p','dh-note',h.confidence === 'PARTIAL' ? '部分核实 · 媒体报道口径' : '事件发展中'));
          grid.append(card);
        }
        grid.hidden = false; state.hidden = true;
      }
      action.href = '/intelligence/daily-headlines/'+data.date+'.html';
    } catch (_) { if(token === request) pending(); }
    finally {clearTimeout(timer);}
  }
  refresh();
  // Open tabs must change to PENDING at Shanghai midnight even without a reload.
  setInterval(refresh,60000);
  document.addEventListener('visibilitychange',() => {if(!document.hidden) refresh();});
})();

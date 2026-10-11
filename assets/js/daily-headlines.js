/* Current Shanghai date only. A failed review is distinct from pending/no change. */
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
  const element = (tag, cls, value, lang) => {
    const node = document.createElement(tag); node.className = cls; node.textContent = value;
    if (lang) node.lang = lang;
    return node;
  };
  const label = (target, en, cn) => target.replaceChildren(
    element('span', '', en, 'en'), element('span', '', cn, 'zh-CN'));
  const pending = () => {
    grid.replaceChildren(); grid.hidden = true; state.hidden = false;
    label(state, 'Daily Intelligence Update Pending', '今日情报更新待完成');
    dateLabel.textContent = dateInShanghai();
    action.href = '/intelligence/daily-headlines/#archive';
    label(action, 'View Archive', '查看历史归档');
  };
  let request = 0;
  async function refresh() {
    const token = ++request; pending();
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 10000);
    const read = async path => {
      try {
        const response = await fetch(path, {cache:'no-store',signal:controller.signal});
        return response.ok ? await response.json() : null;
      } catch (_) { return null; }
    };
    try {
      const [data, outcome] = await Promise.all([
        read('/data/daily-headlines/latest.json'), read('/data/daily-headlines/status.json')
      ]);
      if (token !== request) return;
      const today = dateInShanghai();
      // An accepted same-day publication takes precedence over an earlier failed attempt.
      let published = false;
      if (data?.schema_version === 1 && data.date === today && Array.isArray(data.headlines)) {
        if (data.status === 'NO_MATERIAL_CHANGE' && data.headlines.length === 0) {
          label(state, 'No Material Intelligence Change', '今日暂无重大情报变化'); published = true;
        } else if (data.status === 'PUBLISHED' && data.headlines.length > 0 && data.headlines.length <= 5 &&
          data.headlines.every(h => h && h.date === data.date && h.headline_cn && h.summary && h.category &&
            ['CONFIRMED','PARTIAL','DEVELOPING'].includes(h.confidence))) {
          const cards = document.createDocumentFragment();
          for (const h of data.headlines.slice(0,3)) {
            const card = element('article','dh-card','');
            const meta = element('div','dh-meta','');
            meta.append(element('span','dh-category',h.category));
            if (h.time) meta.append(element('span','',h.time+' CST'));
            card.append(meta,element('h3','',h.headline_cn),element('p','',h.summary));
            if (h.confidence !== 'CONFIRMED') card.append(element('p','dh-note',h.confidence === 'PARTIAL' ? '部分核实 · 媒体报道口径' : '事件发展中'));
            cards.append(card);
          }
          grid.replaceChildren(cards); grid.hidden = false; state.hidden = true; published = true;
        }
      }
      if (published) {
        action.href = '/intelligence/daily-headlines/'+data.date+'.html';
        label(action, 'View All Daily Headlines', '查看全部今日头条');
      } else if (outcome?.schema_version === 1 && outcome.date === today && outcome.status === 'NO_VERIFIED_UPDATE') {
        state.replaceChildren(document.createTextNode('No Verified Update｜今日暂无符合发布标准的更新'),
          element('span','dh-explanation','审核未通过不代表当天没有重大新闻。','zh-CN'));
      }
    } finally {clearTimeout(timer);}
  }
  refresh();
  setInterval(refresh,60000);
  document.addEventListener('visibilitychange',() => {if(!document.hidden) refresh();});
})();

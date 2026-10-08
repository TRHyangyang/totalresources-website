/* intelligence.html is the single source maintained by publish_weekly_outlook.py.
   Read only its latest card; archive entries are never copied to the homepage. */
(() => {
    'use strict';
    const section = document.querySelector('[data-weekly-outlook]');
    if (!section) return;
    const card = section.querySelector('.home-weekly-card');
    const status = section.querySelector('.home-weekly-status');
    const sourceURL = new URL('intelligence.html', document.baseURI);
    let loading = false;
    async function refresh() {
        if (loading) return;
        loading = true;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(sourceURL, {cache: 'no-store', signal: controller.signal});
            if (!response.ok) throw new Error('Weekly Outlook index unavailable');
            const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
            const latest = doc.querySelector('#weekly-outlook .latest-card');
            const date = latest?.querySelector('.latest-date')?.textContent.trim();
            const title = latest?.querySelector('h3')?.textContent.trim();
            const period = latest?.querySelector('p')?.textContent.trim();
            const link = latest?.querySelector('a[href]');
            const url = link && new URL(link.getAttribute('href'), sourceURL);
            if (!/^\d{4}-\d{2}-\d{2}$/.test(date || '') || !title || !period ||
                !url || url.origin !== sourceURL.origin || url.pathname !== '/weekly-outlook/' + date + '.html') {
                throw new Error('Weekly Outlook latest card incomplete');
            }
            const time = card.querySelector('time');
            time.dateTime = date;
            time.textContent = date;
            card.querySelector('h3').textContent = title;
            card.querySelector('.home-weekly-content p').textContent = period;
            card.querySelector('.home-weekly-read').href = url.pathname;
            card.hidden = false;
            status.hidden = true;
        } catch (_) {
            card.hidden = true;
            status.textContent = '请进入 Intelligence 查看最新一期每周展望。';
            status.hidden = false;
        } finally {
            clearTimeout(timeout);
            loading = false;
        }
    }
    refresh();
    setInterval(() => { if (!document.hidden) refresh(); }, 300000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();

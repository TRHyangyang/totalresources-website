/* The existing publication workflow updates this source card daily.
   Keep this selector scoped: Intelligence also contains Weekly Outlook cards. */
(async function () {
    'use strict';
    const section = document.querySelector('.global-pulse');
    if (!section) return;
    const card = section.querySelector('.pulse-card');
    const status = section.querySelector('.pulse-status');
    status.hidden = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
        const response = await fetch('intelligence.html', {
            cache: 'no-store', signal: controller.signal
        });
        if (!response.ok) throw new Error('Intelligence unavailable');
        const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
        const latest = doc.querySelector('#research-archive .latest-card');
        const date = latest?.querySelector('time[datetime]')?.getAttribute('datetime');
        const title = latest?.querySelector('h3')?.textContent.trim();
        const summary = latest?.querySelector('p')?.textContent.trim();
        const href = latest?.querySelector('a[href]')?.getAttribute('href');
        if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date) || !title || !summary || !href) {
            throw new Error('Incomplete latest publication');
        }
        const url = new URL(href, response.url || location.href);
        if (url.origin !== location.origin || url.pathname !== `/intelligence/${date}.html`) {
            throw new Error('Invalid publication link');
        }
        const time = card.querySelector('time');
        time.dateTime = date;
        // Use the publication date as written, without timezone conversion.
        time.textContent = date.slice(0, 4) + '\n' + date.slice(5);
        card.querySelector('h3').textContent = title;
        card.querySelector('.pulse-summary').textContent = summary;
        card.querySelector('.pulse-read').href = url.pathname;
        card.hidden = false;
        status.hidden = true;
    } catch (error) {
        status.textContent = '暂时无法加载最新一期，请通过「进入 Intelligence →」查看。';
    } finally {
        clearTimeout(timeout);
    }
}());

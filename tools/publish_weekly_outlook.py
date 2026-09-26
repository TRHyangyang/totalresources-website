#!/usr/bin/env python3
"""Publish one explicitly supplied, archived Weekly FINAL; never discover sources."""
import argparse
from datetime import date
import html
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from publish_global_pulse import render_markdown

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- WEEKLY OUTLOOK START -->'
END = '<!-- WEEKLY OUTLOOK END -->'


def publish(source):
    source = source.resolve(strict=True)
    text = source.read_text(encoding='utf-8')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z', text, re.S)
    if not match:
        raise ValueError('YAML front matter required')
    meta = {}
    for line in match[1].splitlines():
        item = re.match(r'^(date|status|publication_status|title|subtitle):\s*(.*?)\s*$', line)
        if item:
            meta[item[1]] = item[2].strip('\'"')
    if meta.get('status', meta.get('publication_status')) != 'FINAL':
        raise ValueError('Explicit FINAL status required')
    day = meta.get('date', '')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('ISO publication date required')
    date.fromisoformat(day)
    expected = ('02 Global Intelligence（全球情报）', 'Weekly Outlook（每周展望）', day[:4], day[5:7])
    if source.parts[-5:-1] != expected:
        raise ValueError('Source must be archived under 02 Global Intelligence（全球情报）/Weekly Outlook（每周展望）/YYYY/MM/')
    if not meta.get('title') or not match[2].strip():
        raise ValueError('Title and body required')
    relative = 'weekly-outlook/' + day + '.html'
    output = ROOT / relative
    if output.exists():
        raise ValueError('Duplicate publication: article already exists')
    index_path = ROOT / 'intelligence.html'
    index = index_path.read_text(encoding='utf-8')
    dates = re.findall(r'<!-- weekly-publication:(\d{4}-\d{2}-\d{2}) -->', index)
    if dates and day <= max(dates):
        raise ValueError('Publication must be newer than the latest Weekly issue')
    title = html.escape(meta['title'])
    subtitle = html.escape(meta.get('subtitle', ''))
    canonical = 'https://totalresources.info/' + relative
    page = (ROOT / 'tools/weekly_outlook_article.html').read_text(encoding='utf-8')
    values = {'TITLE': title + ('｜' + subtitle if subtitle else ''), 'DESCRIPTION': title + ' ' + subtitle,
              'CANONICAL': canonical, 'DATE': day, 'ARTICLE': render_markdown(match[2])}
    # Single pass: source text containing template-like braces is literal content.
    page = re.sub(r'\{\{([A-Z]+)\}\}', lambda m: values[m[1]], page)
    entry = (f'<!-- weekly-publication:{day} --><li><time datetime="{day}">{day}</time>'
             f'<a href="{relative}">{title}｜{subtitle} →</a></li>')
    card = (f'<div class="latest-card"><div class="latest-date">{day}</div>'
            f'<h3>{title}</h3><p>{subtitle}</p><a href="{relative}">Read Weekly Outlook →</a></div>')
    if START in index:
        if index.count(START) != 1 or index.count(END) != 1:
            raise ValueError('Ambiguous Weekly section')
        old = index.split(START, 1)[1].split(END, 1)[0]
        archive = re.search(r'<ul>(.*?)</ul>', old, re.S)
        if not archive:
            raise ValueError('Weekly archive missing')
        entries = entry + archive[1]
    else:
        entries = entry
    section = (START + '\n<section class="latest-section" id="weekly-outlook"><div class="container">'
               '<div class="section-head"><div class="eyebrow">02 Weekly Outlook</div>'
               '<h2>每周展望</h2><p>下周风险日历与重要事件报告</p></div>' + card +
               '<div class="archive-list"><h3>Weekly Outlook Archive</h3><ul>' + entries +
               '</ul></div></div></section>\n' + END)
    if START in index:
        index = index.split(START, 1)[0] + section + index.split(END, 1)[1]
    else:
        anchor = '<!-- CONTENT / WECHAT -->'
        if index.count(anchor) != 1 or index.count('<strong>Weekly Outlook</strong>') != 1:
            raise ValueError('Expected website insertion points missing')
        index = index.replace(anchor, section + '\n\n' + anchor)
        index = index.replace('<strong>Weekly Outlook</strong>', '<strong><a href="#weekly-outlook">Weekly Outlook</a></strong>')
    sitemap_path = ROOT / 'sitemap.xml'
    sitemap = sitemap_path.read_text(encoding='utf-8')
    root = ET.fromstring(sitemap)
    if canonical in [n.text for n in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]:
        raise ValueError('Duplicate sitemap URL')
    if sitemap.count('</urlset>') != 1:
        raise ValueError('Invalid sitemap')
    sitemap = sitemap.replace('</urlset>', f'  <url><loc>{canonical}</loc></url>\n\n</urlset>')
    ET.fromstring(sitemap)
    # Finish rendering and validation before writing any publication files.
    output.parent.mkdir(exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        handle.write(page)
    index_path.write_text(index, encoding='utf-8')
    sitemap_path.write_text(sitemap, encoding='utf-8')
    return canonical


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        print(publish(args.source))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        print('Publication rejected: ' + str(error), file=sys.stderr)
        sys.exit(1)

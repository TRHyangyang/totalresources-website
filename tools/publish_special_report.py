#!/usr/bin/env python3
"""Prepare an isolated preview by default; publish only with a file-bound review receipt."""
import argparse
from datetime import date
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import markdown
import yaml

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- SPECIAL REPORTS START -->'
END = '<!-- SPECIAL REPORTS END -->'
ENTRY = '<!-- SPECIAL REPORTS ENTRIES -->'

class SafeHTML(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'iframe', 'object', 'embed', 'style', 'form'}:
            raise ValueError('Unsafe HTML element: ' + tag)
        for key, value in attrs:
            if key.startswith('on') or key in {'style', 'srcdoc'}:
                raise ValueError('Unsafe HTML attribute: ' + key)
            if key in {'href', 'src'} and value:
                from urllib.parse import urlsplit
                if urlsplit(value.strip()).scheme not in {'', 'https', 'http', 'mailto'} or value.strip().startswith('//'):
                    raise ValueError('Unsafe URL')

def scalar(value):
    if isinstance(value, list):
        return '、'.join(map(str, value))
    return str(value or '')

def load(source):
    raw = source.read_bytes()
    text = raw.decode('utf-8-sig')
    match = re.fullmatch(r'---\r?\n(.*?)\r?\n---\r?\n(.*)', text, re.S)
    meta, body = (yaml.safe_load(match[1]), match[2]) if match else ({}, text)
    if not isinstance(meta, dict):
        raise ValueError('Metadata must be a YAML mapping')
    heading = re.search(r'^#\s+(.+)', body, re.M)
    title = scalar(meta.get('title')) or (heading[1] if heading else '')
    if not title or not body.strip():
        raise ValueError('Title and body required')
    digest = hashlib.sha256(raw).hexdigest()
    issues = []
    if 'pending' in scalar(meta.get('status')).lower():
        issues.append('Resolve pending publication status in FINAL.md')
    if re.search(r'\[(?:iea|english\.stm|csis)\]', body):
        issues.append('Replace source placeholders with verified clickable links')
    if '发布前核验' in body:
        issues.append('Resolve the file’s pre-publication verification notes')
    if '表1' in body and not re.search(r'^\s*\|.*\|\s*$', body, re.M):
        issues.append('Supply Table 1 or explicitly document its absence for readers')
    return meta, body, title, digest, issues

def run(args):
    source = args.source.resolve(strict=True)
    meta, body, title, digest, issues = load(source)
    day = args.date or scalar(meta.get('publication_date') or meta.get('date'))
    date.fromisoformat(day)
    slug = args.slug or scalar(meta.get('slug'))
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Supply a stable lowercase URL slug using --slug or metadata')
    relative = 'special-reports/' + slug + '.html'
    canonical = 'https://totalresources.info/' + relative
    article = markdown.markdown(body, extensions=['extra', 'sane_lists'], output_format='html5')
    SafeHTML().feed(article)
    for ref in re.findall(r'\[\^([^\]]+)\]', body):
        if not re.search(r'^\[\^'+re.escape(ref)+r'\]:', body, re.M):
            raise ValueError('Undefined footnote: ' + ref)
    values = dict(TITLE=title, DESCRIPTION=scalar(meta.get('description')) or title, CANONICAL=canonical,
                  DATE=day, AUTHORS=scalar(meta.get('authors') or meta.get('author')), SOURCE=scalar(meta.get('source')),
                  ORIGINALDATE=scalar(meta.get('original_date')) or '—')
    if args.publish:
        if not args.approval:
            raise ValueError('Publication requires --approval receipt')
        receipt = json.loads(args.approval.read_text())
        for key in ('rights_cleared', 'image_rights_cleared_or_no_image', 'file_checks_completed', 'publish_approved'):
            if receipt.get(key) is not True:
                raise ValueError('Review not completed: ' + key)
        if receipt.get('source_sha256') != digest or receipt.get('publication_date') != day:
            raise ValueError('Review receipt does not match the exact source and publication date')
        if not receipt.get('reviewer') or not receipt.get('evidence'):
            raise ValueError('Reviewer and evidence required')
        if issues:
            raise ValueError('; '.join(issues))
        if not values['AUTHORS'] or not values['SOURCE']:
            raise ValueError('Author and source metadata required')
        if scalar(meta.get('status') or meta.get('publication_status')).upper() != 'FINAL':
            raise ValueError('Explicit FINAL status required for publication')
    page = (ROOT/'tools/special_report_article.html').read_text()
    escaped = {k:html.escape(v, quote=True) for k,v in values.items()}
    escaped['ARTICLE'] = article
    page = re.sub(r'\{\{([A-Z]+)\}\}', lambda m:escaped[m[1]], page)
    if not args.publish:
        if not args.preview_dir:
            raise ValueError('Supply --preview-dir outside the public repository')
        out = args.preview_dir.resolve()
        if out == ROOT or ROOT in out.parents:
            raise ValueError('Preview must remain outside the public repository')
        out.mkdir(parents=True, exist_ok=True)
        page = page.replace('发布日期 '+day, '网站发布日期 待定').replace('Publication Date<strong>'+day, 'Publication Date<strong>待定')
        page = page.replace('<head>', '<head>\n<meta name="robots" content="noindex,nofollow">').replace('<body>', '<body><p style="padding:16px;background:#fff4d8">待发布预览 · 未公开上线</p>')
        (out/(slug+'.html')).write_text(page)
        (out/'review.json').write_text(json.dumps(dict(title=title, source=str(source), source_sha256=digest, status='pending', publication_date=None, original_date=scalar(meta.get('original_date')), blockers=issues, required_reviews=['CSIS translation/republication rights', 'Image permission or no image', 'Source links and Table 1', 'Resource/reserve units, graphite 27 million short tons, time-sensitive project claims, author roles']),ensure_ascii=False,indent=2))
        print(out/(slug+'.html'))
        return
    target = ROOT/relative
    if target.exists():
        raise ValueError('Duplicate slug; existing articles cannot be overwritten')
    indexpath = ROOT/'intelligence.html'
    index = indexpath.read_text()
    if index.count(START)!=1 or index.count(END)!=1:
        raise ValueError('Special Reports section missing or ambiguous')
    prefix, section = index.split(START)
    section, suffix = section.split(END)
    entries = re.findall(r'<!-- special-report:(\d{4}-\d{2}-\d{2}):([a-z0-9-]+) --><li>.*?</li>', section, re.S)
    existing = re.findall(r'<!-- special-report:\d{4}-\d{2}-\d{2}:[a-z0-9-]+ --><li>.*?</li>', section, re.S)
    entry = f'<!-- special-report:{day}:{slug} --><li><time datetime="{day}">{day}</time><a href="{relative}">{escaped["TITLE"]} →</a></li>'
    ordered = sorted(existing+[entry], key=lambda x:re.search(r'special-report:([^:]+):',x)[1], reverse=True)
    archive = ''.join(ordered)
    latest = ordered[0]
    latest_slug = re.search(r'special-report:[^:]+:([^ ]+) ', latest)[1]
    if latest_slug == slug:
        card = f'<div class="latest-card"><div class="latest-date">{day}</div><h3>{escaped["TITLE"]}</h3><p>{escaped["SOURCE"]} · {escaped["AUTHORS"]}</p><a href="{relative}">Read Special Report →</a></div>'
        section = re.sub(r'<div class="latest-card">.*?</div>(?=\s*<div class="archive-list">)',lambda m:card,section,flags=re.S)
    section = re.sub(r'<ul>.*?</ul>',lambda m:'<ul>'+archive+'</ul>',section,flags=re.S)
    newindex = prefix+START+section+END+suffix
    landingpath = ROOT/'special-reports/index.html'
    landing = re.sub(r'<ul>.*?</ul>',lambda m:'<ul>'+archive.replace('href="special-reports/','href="')+'</ul>',landingpath.read_text(),flags=re.S)
    smpath = ROOT/'sitemap.xml'; sm=smpath.read_text()
    if canonical in sm:
        raise ValueError('Duplicate sitemap entry')
    sm = sm.replace('</urlset>',f'  <url><loc>{canonical}</loc></url>\n</urlset>')
    ET.fromstring(sm)
    # Validate and render all outputs before mutating any public files.
    target.write_text(page); indexpath.write_text(newindex); landingpath.write_text(landing); smpath.write_text(sm)
    print(canonical)

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--date');p.add_argument('--slug')
    p.add_argument('--preview-dir',type=Path);p.add_argument('--publish',action='store_true');p.add_argument('--approval',type=Path)
    try:
        run(p.parse_args())
    except (ValueError, OSError, KeyError, yaml.YAMLError, ET.ParseError) as e:
        p.exit(1, 'Publication rejected: '+str(e)+'\n')

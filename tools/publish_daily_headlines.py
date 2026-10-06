#!/usr/bin/env python3
"""Daily Headlines V1: local evidence only; preview by default; no collection or deployment.
Editorial decisions are an explicit input, never inferred from importance labels.
"""
import argparse, datetime as dt, difflib, hashlib, html, json, pathlib, re, shutil
import string, sys, tempfile, urllib.parse, urllib.request, urllib.error, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
ROOT = pathlib.Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Shanghai')
PRIORITIES = [
 ('ENERGY',r'oil|diesel|refiner|gasoline|lng|natural gas|crude|aramco|hormuz|fuel|energy stockpile',1),
 ('GEOPOLITICS',r'houthi|yemen|saudi|iran|tanker|shipping|sanction|red sea|bab.el.mand',2),
 ('MACRO',r'fed\b|\brates?\b|dollar|euro\b|fiscal|private.credit|\bbonds?\b|treasur|inflation|payroll|debt|financial',3),
 ('CHINA',r'china|chinese|beijing',4),
 ('CHEMICALS',r'\bpx\b|\bpta\b|benzene|ethylene|styrene|petrochemical',5),
 ('AI GOVERNANCE',r'\bai\b|openai|anthropic|artificial intelligence|super.intelligence',6)]
TOPICS=[('hormuz-flow',r'hormuz.*(?:traffic|flow)|oil drops as hormuz'),('saudi-pipeline',r'saudi.*pipeline'),
 ('aramco-osp',r'aramco.*(?:prices|inventor)'),('yemen-war',r'houthi|yemen.*counterattack|riyadh'),
 ('us-diesel-tax',r'diesel.*restrictions|gas.tax|pump pain'),('euro-fiscal',r'euro.*(?:fiscal|sink|dollar)|eurodrama'),
 ('private-credit-review',r'private.credit'),('ai-task-force',r'ai task force'),('openai-legal',r'legal risks.*openai')]
def digest(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def clean(value): return html.unescape(re.sub(r'<[^>]*>', '',value or '')).strip()
def urlnorm(url):
 u=urllib.parse.urlsplit(url); return urllib.parse.urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path.rstrip('/'),'', ''))
def stamp(value):
 x=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
 if x.tzinfo is None: raise ValueError('Timezone missing')
 return x.astimezone(TZ)
def eventid(item):
 text=item['headline'].lower()
 for name,pattern in TOPICS:
  if re.search(pattern,text):return 'dh-'+name
 slug=re.sub(r'[^a-z0-9]+','-',text).strip('-')
 return 'dh-'+slug[:100]
def classify(i):
 text=(i['headline']+' '+clean(i.get('summary'))).lower()
 if re.search(r'james bond|bond watches|prime day|documentary|best power banks|review:',text):return ('OTHER',7)
 # Chemical and AI subject keywords override upstream category errors.
 if re.search(PRIORITIES[4][1],text):return ('CHEMICALS',5)
 if re.search(PRIORITIES[5][1],text) and not re.search(r'fuel|oil|diesel|hormuz',text):return ('AI GOVERNANCE',6)
 for category,pattern,priority in PRIORITIES:
  if re.search(pattern,text):return(category,priority)
 return ('OTHER',7)
def insufficient(i):
 raw=i.get('summary','');s=clean(raw)
 if not s:return 'EMPTY_SUMMARY'
 if len(s)<65:return 'INSUFFICIENT_FACTS'
 if re.search(r'<[^>]*$',raw) or re.search(r'<(?:p|a|div|ul)\b[^>]*>\s*$',raw):return 'TRUNCATED_SUMMARY'
 if not re.search(r'[.!?。][”’"\']?$',s):return 'TRUNCATED_SUMMARY'
 if s.lower()==i['headline'].lower():return 'TITLE_ONLY'
 return None

def discover(scan_path,date,history_dir,rss):
 input_bytes=scan_path.read_bytes();scan=json.loads(input_bytes);input_hash=hashlib.sha256(input_bytes).hexdigest(); now=dt.datetime.now(TZ)
 if date!=now.date().isoformat():raise ValueError('Only the current Shanghai date is allowed')
 if scan.get('date')!=date:raise ValueError('Scan date mismatch')
 cutoff=stamp(scan['retrieval_time']);start=stamp(scan['window_start'])
 if cutoff.date().isoformat()!=date or cutoff>now or now-cutoff>dt.timedelta(hours=24):raise ValueError('Stale/future scan')
 if not dt.timedelta(hours=23)<=cutoff-start<=dt.timedelta(hours=25):raise ValueError('Invalid scan window')
 if not isinstance(scan.get('items'),list) or not scan['items']:raise ValueError('Missing scan items')
 if not any(v.get('status')=='OK' for v in scan.get('source_status',{}).values()):raise ValueError('No successful source')
 previous=[]
 for p in history_dir.glob('**/web_intel_*.json'):
  if p==scan_path:continue
  try:
   d=json.loads(p.read_text())
   if d.get('date','')<date:previous.extend(d.get('items',[]))
  except (ValueError,OSError):raise ValueError('Unreadable historical source: '+str(p))
 history_urls={}
 history_words={}
 history_topics={}
 for x in previous:
  history_urls.setdefault(urlnorm(x.get('url','')),[]).append(x)
  history_topics.setdefault(eventid(x),[]).append(x)
  for word in set(re.findall(r'[a-z]{4,}',clean(x.get('headline')).lower())):
   history_words.setdefault(word,[]).append(x)
 memory=[]
 for p in (ROOT/'data/daily-headlines').glob('????/??/????-??-??.json'):
  d=json.loads(p.read_text())
  if d['date']<date:memory.extend(d['headlines'])
 rows=[]
 for n,i in enumerate(scan['items']):
  category,priority=classify(i); reason=None
  if i.get('window_status')!='IN_WINDOW_24H':reason=i.get('window_status','UNKNOWN_WINDOW')
  else:
   try:
    t=stamp(i['published'])
    if not start<=t<=cutoff:reason='OUT_OF_WINDOW'
    elif i.get('time_source') not in ('FEED_PUBDATE','PAGE_METADATA'):reason='TIME_NOT_ABSOLUTELY_VERIFIED'
   except (ValueError,KeyError,TypeError):reason='TIME_UNVERIFIED'
  if not reason and i.get('noise_reason'):reason='NOISE_FILTERED'
  if not reason:reason=insufficient(i)
  if not reason and category=='OTHER':reason='NO_MCIS_RELEVANCE'
  if not reason and i.get('source')=='ZEROHEDGE':reason='SIGNAL_SOURCE_NEEDS_INDEPENDENT_EVIDENCE'
  prior=[]
  words=set(re.findall(r'[a-z]{4,}',i['headline'].lower()))
  possible={id(x):x for w in words for x in history_words.get(w,[]) if len(words & set(re.findall(r'[a-z]{4,}',clean(x.get('headline')).lower())))>=max(2,len(words)*.6)}
  possible.update({id(x):x for x in history_urls.get(urlnorm(i['url']),[])})
  possible.update({id(x):x for x in history_topics.get(eventid(i),[])})
  for x in possible.values():
   if eventid(x)==eventid(i) or urlnorm(x.get('url',''))==urlnorm(i['url']) or difflib.SequenceMatcher(None,clean(x.get('headline')).lower(),i['headline'].lower()).ratio()>.9:
    prior.append({'headline':x.get('headline'),'summary':clean(x.get('summary')),'source_url':x.get('url')})
  eid=eventid(i)
  published_before=[x for x in memory if x['event_id']==eid or urlnorm(x['source_url'])==urlnorm(i['url'])]
  score={1:85,2:80,3:80,4:78,5:76,6:72,7:0}[priority]
  relevance_text=i['headline'].lower()
  if re.search(r'hormuz|pipeline|aramco|refiner|houthi|sanction|tanker|private.credit|euro.*fiscal',relevance_text):score+=10
  if re.search(r'solar.*space|school buses|m&a|assets.*sale',relevance_text):score-=20
  if re.search(r'journalism|documentary|advert|review:|luxury|poll finds|last year|in june|last week',i['headline']+' '+clean(i.get('summary')),re.I):score-=35
  if re.search(r'ai task force',i['headline'],re.I):score+=5
  if not reason and score<75:reason='BELOW_MATERIALITY_THRESHOLD'
  rows.append({'item_index':n,'event_id':eid,'category':category,'priority':priority,'score':score,
    'headline':i['headline'],'source_name':i['source'],'source_url':i['url'],'source_publish_time':i.get('published'),
    'summary':clean(i.get('summary')),'importance':i.get('importance'),'reason':reason,
    'previous_source_matches':prior,'previous_published_events':published_before})
 # Relevance ranking independent of upstream importance. Clustering retains evidence rows.
 clusters={}
 for row in rows:
  clusters.setdefault(row['event_id'],[]).append(row)
 ranked=sorted(clusters.values(),key=lambda c:(min(x['priority'] for x in c),-max(x['score'] for x in c),c[0]['event_id']))
 report={'date':date,'scan_sha256':input_hash,'source_raw_count':len(rows),
  'source_in_window_count':sum(i.get('window_status')=='IN_WINDOW_24H' for i in scan['items']),
  'source_clean_window_count':sum(i.get('window_status')=='IN_WINDOW_24H' and not i.get('noise_reason') for i in scan['items']),
  'eligible_record_count':sum(not r['reason'] for r in rows),'event_cluster_count':len(clusters),
  'eligible_clusters':[c for c in ranked if any(not x['reason'] for x in c)],
  'ranked_clusters':ranked,'records':rows,'rss':{'status':'NOT_USED'}}
 if rss and rss.exists():
  text=rss.read_text()
  # Current RSS format has no article URLs; do not invent them or treat its CONFIRMED labels as evidence.
  report['rss']={'status':'CONTEXT_ONLY_NO_ARTICLE_URLS','sha256':digest(rss),
    'date_matches':bool(re.search(r'^date: '+re.escape(date)+r'$',text,re.M)),
    'note':'No machine completion marker or article URLs. Not accepted as public factual evidence.'}
 if digest(scan_path)!=input_hash:raise ValueError('Source changed during read')
 return scan,report

def check_url(url):
 u=urllib.parse.urlsplit(url)
 if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Invalid source URL')
 if u.hostname in ('localhost','127.0.0.1') or ':' in u.hostname or not '.' in u.hostname:raise ValueError('Nonpublic source URL')
 request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 DailyHeadlinesQA'},method='GET')
 try:
  with urllib.request.urlopen(request,timeout=20) as response:
   status=response.status; final=response.url
 except urllib.error.HTTPError as e:status=e.code;final=url
 if status!=200:raise ValueError('Source URL did not return 200: '+url+' '+str(status))
 if urllib.parse.urlsplit(final).scheme!='https':raise ValueError('Insecure source redirect')
 return {'url':url,'status':status,'final_url':final,'checked_at':dt.datetime.now(TZ).isoformat()}

def validate(scan,report,packet,verify):
 if packet.get('date')!=report['date'] or packet.get('scan_sha256')!=report['scan_sha256']:raise ValueError('Editorial input snapshot mismatch')
 if packet.get('review',{}).get('status')!='REVIEWED':raise ValueError('Editorial review required')
 required=['facts_vs_analysis','numbers_names','headline_summary_consistency','material_novelty','evidence_sufficiency']
 if not all(packet['review'].get(k) is True for k in required):raise ValueError('Missing editorial QA checklist')
 selected=packet.get('headlines',[])
 if len(selected)>5:raise ValueError('More than five headlines')
 decisions=packet.get('decisions',{})
 for c in report['eligible_clusters']:
  if c[0]['event_id'] not in decisions:raise ValueError('Unresolved candidate '+c[0]['event_id'])
 if not selected:
  if not packet.get('no_material_change_reason') or packet.get('coverage_complete') is not True:raise ValueError('Empty output needs completed materiality and coverage assessment')
  if any(v.get('status')!='OK' for v in scan.get('source_status',{}).values()):raise ValueError('Failed sources cannot imply no material change')
  for row in report['records']:
   if row['score']>=75 and row['reason'] not in ('OUT_OF_WINDOW','TIME_UNVERIFIED','NOISE_FILTERED') and row['event_id'] not in decisions:raise ValueError('Unresolved evidence gaps: output must remain PENDING')
 seen=set();headlines=[];urls=[]
 for rank,h in enumerate(selected,1):
  eid=h['event_id']
  if eid in seen:raise ValueError('Duplicate event')
  seen.add(eid)
  if decisions.get(eid,{}).get('action')!='SELECT':raise ValueError('Selection decision missing')
  indices=h.get('evidence_indices',[])
  if not indices:raise ValueError('No evidence')
  rows=[report['records'][n] for n in indices]
  if any(r['reason'] for r in rows):raise ValueError('Ineligible evidence')
  if any(r['event_id']!=eid for r in rows):raise ValueError('Cross-event evidence')
  if any(r['previous_source_matches'] or r['previous_published_events'] for r in rows):
   if not h.get('material_new_information') or not h.get('prior_comparison') or not h.get('novelty_quote'):raise ValueError('Old-news replay lacks comparison and new evidence quote')
   prior_text=' '.join(x.get('summary','') for r in rows for x in r['previous_source_matches'])
   if h['novelty_quote'] not in ' '.join(r['headline']+' '+r['summary'] for r in rows):raise ValueError('Novelty quote not in current evidence')
   if h['novelty_quote'] in prior_text:raise ValueError('Novelty quote already in historical evidence')
  if not h.get('material_new_information'):raise ValueError('Material novelty assessment missing')
  corpus=' '.join(scan['items'][n]['headline']+' '+clean(scan['items'][n].get('summary')) for n in indices)
  facts=h.get('fact_checks',[])
  if not facts:raise ValueError('No fact-to-evidence mapping')
  for f in facts:
   n=f['item_index']
   if n not in indices:raise ValueError('Fact uses unapproved source')
   original=scan['items'][n]['headline']+' '+clean(scan['items'][n].get('summary'))
   if not f.get('quote') or f['quote'] not in original or not f.get('fact_cn'):raise ValueError('Evidence quote not found')
  fact_text=''.join(f['fact_cn'] for f in facts)
  if h['fact_cn']!=fact_text:raise ValueError('Unmapped public facts')
  if not h.get('analysis_cn','').startswith('值得关注的是'):raise ValueError('Analysis must be separately signposted')
  summary=h['fact_cn']+h['analysis_cn']
  if not 50<=len(re.findall(r'[\u4e00-\u9fff]',summary))<=120:raise ValueError('Summary outside 50–120 Chinese characters')
  if len(h['headline_cn'])>50 or re.search(r'[↑↓→]{2,}',h['headline_cn']+summary):raise ValueError('Editorial style violation')
  for number in re.findall(r'\d+(?:[.,]\d+)*',h['headline_cn']+summary):
   if number not in corpus:raise ValueError('Unsupported number '+number)
  for name in h.get('entities',[]):
   if name['original'] not in corpus or name['cn'] not in h['headline_cn']+summary:raise ValueError('Name mapping mismatch')
  confidence=h['confidence']
  if confidence not in ('CONFIRMED','PARTIAL','DEVELOPING'):raise ValueError('Invalid confidence')
  domains={urllib.parse.urlsplit(r['source_url']).netloc for r in rows}
  if confidence=='CONFIRMED' and len(domains)<2:raise ValueError('CONFIRMED needs independent cross-source evidence')
  sources=[{'source_name':r['source_name'],'source_url':r['source_url'],'source_publish_time':r['source_publish_time']} for r in rows]
  r=rows[0]; t=stamp(r['source_publish_time'])
  headlines.append({'event_id':eid,'date':report['date'],'time':t.strftime('%m-%d %H:%M'),
   'headline_cn':h['headline_cn'],'headline_en':h.get('headline_en',''),'summary':summary,
   'category':r['category'],**sources[0],'sources':sources,'confidence':confidence,
   'mcis_relevance':h['mcis_relevance'],'rank':rank,'material_new_information':h['material_new_information']})
  urls.extend(r['source_url'] for r in rows)
 if seen!={eid for eid,d in decisions.items() if d.get('action')=='SELECT'}:raise ValueError('Selection list and decisions differ')
 for eid,d in decisions.items():
  if d.get('action') not in ('SELECT','REJECT') or not d.get('reason'):raise ValueError('Invalid candidate decision')
 receipts=[check_url(u) for u in sorted(set(urls))] if verify else []
 if selected and not verify:raise ValueError('Source URL verification required before preview generation')
 payload={'schema_version':1,'date':report['date'],'timezone':'Asia/Shanghai',
  'status':'PUBLISHED' if headlines else 'NO_MATERIAL_CHANGE','generated_at':dt.datetime.now(TZ).isoformat(),
  'headlines':headlines}
 return payload,receipts

def card(h):
 esc=html.escape
 source=' · '.join('<a href="'+esc(s['source_url'],quote=True)+'" rel="noopener noreferrer">'+esc(s['source_name'])+'</a> <time datetime="'+esc(s['source_publish_time'])+'">'+esc(stamp(s['source_publish_time']).strftime('%Y-%m-%d %H:%M'))+' CST</time>' for s in h['sources'])
 label={'CONFIRMED':'已交叉核实','PARTIAL':'部分核实 · 媒体报道口径','DEVELOPING':'事件发展中'}[h['confidence']]
 return '<article class="dh-card"><div class="dh-meta"><span class="dh-category">'+esc(h['category'])+'</span><span>'+esc(h['time'])+' CST</span></div><h3>'+esc(h['headline_cn'])+'</h3><p>'+esc(h['summary'])+'</p><p class="dh-note">'+label+'</p><p class="dh-source">来源：'+source+'</p></article>'
def widget():
 return '''<section class="dh-section" data-daily-headlines aria-labelledby="dh-heading"><div class="dh-wrap"><p class="dh-eyebrow">DAILY HEADLINES</p><h2 id="dh-heading">每日头条</h2><p class="dh-caption"><span data-dh-date></span> · 能源、宏观与产业链的新变化</p><div class="dh-grid" hidden></div><p class="dh-state" role="status">今日情报更新待完成<span>Daily Intelligence Update Pending</span></p><a class="dh-action" href="/intelligence/daily-headlines/">查看全部今日头条 <span lang="en">View All Daily Headlines</span></a><noscript><p class="dh-caption">请进入日期归档查看已发布内容；今日状态需要 JavaScript 校验。</p></noscript></div></section>'''

def generate(out,payload):
 if out.exists():raise ValueError('Preview destination already exists')
 if out==ROOT or ROOT in out.parents:raise ValueError('Preview must be outside repository')
 shutil.copytree(ROOT,out,ignore=shutil.ignore_patterns('.git','__pycache__'))
 date=payload['date']; rel=pathlib.Path('data/daily-headlines')/date[:4]/date[5:7]/(date+'.json')
 if (out/rel).exists() or (out/'intelligence/daily-headlines'/ (date+'.html')).exists():raise ValueError('Date already published; never overwrite archive')
 latest_path=out/'data/daily-headlines/latest.json'
 if latest_path.exists() and json.loads(latest_path.read_text())['date']>=date:raise ValueError('Latest must advance')
 (out/rel).parent.mkdir(parents=True,exist_ok=True)
 content=json.dumps(payload,ensure_ascii=False,indent=2)+'\n';(out/rel).write_text(content)
 latest_path.write_text(content)
 pages=out/'intelligence/daily-headlines';pages.mkdir(parents=True,exist_ok=True)
 dates=sorted([p.stem for p in pages.glob('????-??-??.html')]+[date],reverse=True)
 archive=''.join('<li><a href="/intelligence/daily-headlines/'+d+'.html">'+d+'</a></li>' for d in dates)
 template=string.Template((out/'tools/daily_headlines_page.html').read_text())
 body='<div class="dh-list">'+''.join(card(h) for h in payload['headlines'])+'</div>' if payload['headlines'] else '<p class="dh-state">今日暂无重大情报变化<span>No Material Intelligence Change</span></p>'
 (pages/(date+'.html')).write_text(template.substitute(title=date+' 每日头条',canonical='https://totalresources.info/intelligence/daily-headlines/'+date+'.html',subtitle=date+' · 发布时区 Asia/Shanghai',content=body,archive=archive,script=''))
 (pages/'index.html').write_text(template.substitute(title='Daily Headlines / 每日头条',canonical='https://totalresources.info/intelligence/daily-headlines/',subtitle='今天发生了什么，什么最重要',content=widget(),archive=archive,script='<script src="/assets/js/daily-headlines.js" defer></script>'))
 index=out/'index.html';text=index.read_text()
 marker='<!-- DAILY HEADLINES V1 -->'
 if marker not in text:
  match=re.search(r'<section class="global-pulse".*?</section>',text,re.S)
  if not match:raise ValueError('Global Pulse anchor not found')
  text=text[:match.end()]+'\n'+marker+'\n'+widget()+'\n<!-- END DAILY HEADLINES V1 -->'+text[match.end():]
  text=text.replace('</head>','<link rel="stylesheet" href="/assets/css/daily-headlines.css">\n</head>',1)
  text=text.replace('</body>','<script src="/assets/js/daily-headlines.js" defer></script>\n</body>',1)
 index.write_text(text)
 intelligence=out/'intelligence.html';text=intelligence.read_text()
 if marker not in text:
  text=text.replace('<section class="latest-section" id="research-archive">',marker+'\n<section class="dh-section"><div class="dh-wrap"><p class="dh-eyebrow">DAILY HEADLINES</p><h2>每日头条 / Daily Headlines</h2><p class="dh-caption">当日重要事实与市场意义，简洁呈现。</p><a class="dh-action" href="/intelligence/daily-headlines/">查看每日头条与历史归档 <span>View Daily Headlines</span></a></div></section>\n<section class="latest-section" id="research-archive">',1)
  text=text.replace('</head>','<link rel="stylesheet" href="/assets/css/daily-headlines.css">\n</head>',1)
 intelligence.write_text(text)
 sitemap=out/'sitemap.xml';tree=ET.parse(sitemap);ns='{http://www.sitemaps.org/schemas/sitemap/0.9}';ET.register_namespace('',ns[1:-1]);root=tree.getroot()
 existing={u.findtext(ns+'loc') for u in root}
 for url in ['https://totalresources.info/intelligence/daily-headlines/','https://totalresources.info/intelligence/daily-headlines/'+date+'.html']:
  if url not in existing:
   u=ET.SubElement(root,ns+'url');ET.SubElement(u,ns+'loc').text=url;ET.SubElement(u,ns+'lastmod').text=date
 tree.write(sitemap,encoding='utf-8',xml_declaration=True)
 # Protected files, Global Pulse content, latest card and existing sitemap URLs must survive.
 allowed={'index.html','intelligence.html','sitemap.xml','data/daily-headlines/latest.json','intelligence/daily-headlines/index.html'}
 for p in ROOT.rglob('*'):
  if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts:
   r=p.relative_to(ROOT)
   if str(r) not in allowed and digest(p)!=digest(out/r):raise ValueError('Protected file changed: '+str(r))
 for name,pattern in [('index.html',r'<section class="hero".*?</section>'),('index.html',r'<section class="global-pulse".*?</section>'),('intelligence.html',r'<section class="latest-section" id="research-archive">.*?</section>')]:
  if re.search(pattern,(ROOT/name).read_text(),re.S).group()!=re.search(pattern,(out/name).read_text(),re.S).group():raise ValueError('Existing section modified')
 newurls=[u.findtext(ns+'loc') for u in root]
 if not existing.issubset(set(newurls)) or len(newurls)!=len(set(newurls)):raise ValueError('Sitemap integrity failure')
 for d in dates:
  if not (pages/(d+'.html')).exists():raise ValueError('Archive page missing')
 return {str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file()}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--date',required=True);ap.add_argument('--scan',type=pathlib.Path,required=True)
 ap.add_argument('--history-dir',type=pathlib.Path,required=True);ap.add_argument('--rss',type=pathlib.Path)
 ap.add_argument('--editorial',type=pathlib.Path);ap.add_argument('--report-dir',type=pathlib.Path,required=True)
 ap.add_argument('--preview-dir',type=pathlib.Path);ap.add_argument('--verify-urls',action='store_true')
 a=ap.parse_args();a.report_dir.mkdir(parents=True,exist_ok=True)
 result={'date':a.date,'status':'QA_FAIL','website_changed':False,'deploy':'NOT_RUN'}
 try:
  if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',a.date):raise ValueError('Invalid date format')
  scan,report=discover(a.scan,a.date,a.history_dir,a.rss)
  (a.report_dir/'candidates.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  if not a.editorial:
   result.update(status='CANDIDATE_REVIEW_REQUIRED',eligible_records=report['eligible_record_count'])
  else:
   packet=json.loads(a.editorial.read_text());payload,urls=validate(scan,report,packet,a.verify_urls)
   (a.report_dir/'url-checks.json').write_text(json.dumps(urls,ensure_ascii=False,indent=2))
   if not a.preview_dir:raise ValueError('Preview destination required; production writes are intentionally unavailable in V1 Phase 2')
   if digest(a.scan)!=report['scan_sha256']:raise ValueError('Input snapshot changed before generation')
   hashes=generate(a.preview_dir,payload)
   (a.report_dir/'preview-manifest.json').write_text(json.dumps(hashes,indent=2))
   result.update(status='CONTENT_STATIC_QA_PASS',headlines=len(payload['headlines']),preview=str(a.preview_dir),
     visual_qa='NOT_RUN',semantic_qa='EDITORIAL_REVIEW_RECORDED_NOT_AN_AUTOMATIC_FACT_GUARANTEE',rss=report['rss'])
 except Exception as e:result['error']=str(e)
 if result['status']=='QA_FAIL':
  (a.report_dir/('qa-fail-'+dt.datetime.now(TZ).strftime('%Y%m%dT%H%M%S%f')+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 (a.report_dir/'qa-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False,indent=2))
 return 1 if result['status']=='QA_FAIL' else 0
if __name__=='__main__':sys.exit(main())

"""Bounded original-URL evidence recovery for the existing Daily Headlines run.
Private manifests only; this module cannot generate articles, commit or deploy.
"""
import copy, datetime as dt, fcntl, hashlib, html, json, os, pathlib, re
import subprocess, sys, time, urllib.parse, urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
TZ=ZoneInfo('Asia/Shanghai')
MAX_ARTICLES=5
TOTAL_SECONDS=180
ARTICLE_SECONDS=30
MAX_BYTES=3_000_000
DOMAINS={'AXIOS':'axios.com','ZEROHEDGE':'zerohedge.com','OILPRICE':'oilprice.com',
 'WSJ':'wsj.com','SEMAFOR':'semafor.com','GROUNDNEWS':'ground.news','NEWSQUAWK':'newsquawk.com',
 'WIRED':'wired.com','MARKETWATCH':'marketwatch.com','BARRONS':'barrons.com'}
GAPS={'EMPTY_SUMMARY','TRUNCATED_SUMMARY','INSUFFICIENT_FACTS','TITLE_ONLY','TIME_UNVERIFIED','TIME_NOT_ABSOLUTELY_VERIFIED'}
def timestamp(value):
 value=re.sub(r'([+-]\d{2})(\d{2})$',r'\1:\2',value.replace('Z','+00:00'))
 d=dt.datetime.fromisoformat(value)
 if d.tzinfo is None:raise ValueError('TIMEZONE_MISSING')
 return d.astimezone(TZ)
def norm(url):
 u=urllib.parse.urlsplit(url);return (u.hostname or '').removeprefix('www.')+u.path.rstrip('/')
def allowed(url,source):
 u=urllib.parse.urlsplit(url);domain=DOMAINS.get(source)
 if not domain or u.scheme!='https' or u.username or u.password or u.port not in (None,443) or not (u.hostname==domain or (u.hostname or '').endswith('.'+domain)):
  raise ValueError('URL_OUTSIDE_EXISTING_SOURCE')
 return url
def save(path,data):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def text(value):return re.sub(r'\s+',' ',html.unescape(value)).strip()

class ArticleParser(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.stack=[];self.paragraphs=[];self.paragraph_ranks=[];self.current=None;self.current_rank=0
  self.visible=[];self.h1=[];self.meta={};self.canonical=None;self.ld=[];self.script=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs);classes=a.get('class','')+' '+a.get('id','')+' '+a.get('itemprop','')
  blocked=tag in ('script','style','nav','footer','header','aside','noscript') or 'hidden' in a or a.get('aria-hidden')=='true' or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',a.get('style','')))
  scope=3 if re.search(r'article[-_]?body|article[-_]?content|story[-_]?body|post-content|entry-content|body-copy|news-content',classes,re.I) else 2 if tag=='article' else 1 if tag=='main' else 0
  if tag=='meta':self.meta.setdefault(a.get('property') or a.get('name') or '',[]).append(a.get('content',''))
  if tag=='link' and a.get('rel')=='canonical':self.canonical=a.get('href')
  if tag=='script' and a.get('type')=='application/ld+json':self.script=[]
  if tag not in ('meta','link','br','img','hr','input','source','wbr','area','base','embed','param','track'):
   self.stack.append((tag,blocked,scope))
  if tag=='p' and any(x[2] for x in self.stack) and not any(x[1] for x in self.stack):
   self.current=[];self.current_rank=max(x[2] for x in self.stack)
 def handle_endtag(self,tag):
  if tag=='script' and self.script is not None:
   try:self.ld.append(json.loads(''.join(self.script)))
   except ValueError:pass
   self.script=None
  if tag=='p' and self.current is not None:
   value=text(''.join(self.current))
   if value:self.paragraphs.append(value);self.paragraph_ranks.append(self.current_rank)
   self.current=None
  for n in range(len(self.stack)-1,-1,-1):
   if self.stack[n][0]==tag:self.stack=self.stack[:n];break
 def handle_data(self,data):
  if self.script is not None:self.script.append(data)
  if any(x[1] for x in self.stack):return
  self.visible.append(data)
  if any(x[0]=='h1' for x in self.stack):self.h1.append(data)
  if self.current is not None:self.current.append(data)

def objects(value):
 if isinstance(value,dict):
  yield value
  for v in value.values():yield from objects(v)
 elif isinstance(value,list):
  for v in value:yield from objects(v)

def extract(document,url,source,headline):
 allowed(url,source);p=ArticleParser();p.feed(document)
 articles=[x for x in objects(p.ld) if any(t in ('NewsArticle','Article','ReportageNewsArticle','AnalysisNewsArticle','BlogPosting') for t in (x.get('@type') if isinstance(x.get('@type'),list) else [x.get('@type')]))]
 if any(x.get('isAccessibleForFree') in (False,'false','False') for x in articles):raise ValueError('PAYWALL_NO_BYPASS')
 visible=text(' '.join(p.visible))
 if re.search(r'subscribe to (?:continue|read)|sign in to (?:continue|read)|already a subscriber|unlock this article',visible,re.I):raise ValueError('PAYWALL_NO_BYPASS')
 if not p.canonical or norm(urllib.parse.urljoin(url,p.canonical))!=norm(url):raise ValueError('ARTICLE_IDENTITY_UNVERIFIED')
 title=text(' '.join(p.h1)) or next((text(x['headline']) for x in articles if isinstance(x.get('headline'),str)),None) or next(iter(p.meta.get('og:title',[])),'')
 words=set(re.findall(r'[a-z]{4,}',headline.lower()));actual=set(re.findall(r'[a-z]{4,}',title.lower()))
 if not words or len(words&actual)<min(3,len(words)):raise ValueError('ARTICLE_TITLE_MISMATCH')
 dates=[x['datePublished'] for x in articles if x.get('datePublished')]
 dates += [v for k in ('article:published_time','datePublished','pubdate','parsely-pub-date') for v in p.meta.get(k,[])]
 parsed=[]
 for v in dates:
  try:parsed.append(timestamp(v))
  except (ValueError,TypeError,AttributeError):pass
 if not parsed:raise ValueError('ABSOLUTE_PUBLISHED_TIME_MISSING')
 if max(parsed)-min(parsed)>dt.timedelta(minutes=5):raise ValueError('PUBLISHED_TIME_CONFLICT')
 # JSON-LD body is accepted only when it is also present in the visible page.
 bodies=[text(x['articleBody']) for x in articles if isinstance(x.get('articleBody'),str) and re.sub(r'\s+','',text(x['articleBody'])) in re.sub(r'\s+','',visible)]
 body=max(bodies,key=len) if bodies else '\n\n'.join(v for v,rank in zip(p.paragraphs,p.paragraph_ranks) if rank==max(p.paragraph_ranks))
 byline=None
 for article in articles:
  for author in objects(article.get('author',[])):
   name=author.get('name')
   if name:
    match=re.search(r'\s+(By '+re.escape(name)+r'(?: for [^\n]{1,80})?)$',body)
    if match:byline=match.group(1);body=body[:match.start()].rstrip()
 if len(body)<200 or not re.search(r'[.!?。][”’"\']?$',body):raise ValueError('VISIBLE_ARTICLE_EVIDENCE_INCOMPLETE')
 if len(re.findall(r'[.!?。](?:\s|$)',body))<2:raise ValueError('INSUFFICIENT_FACTUAL_TEXT')
 return {'evidence_text':body,'page_title':title,'published':min(parsed).isoformat(),
  'byline':byline,'time_source':'PAGE_METADATA','canonical_url':p.canonical,'extraction':'VISIBLE_ARTICLE_TEXT',
  'text_sha256':sha(body),'document_sha256':sha(document)}

class SameSourceRedirect(urllib.request.HTTPRedirectHandler):
 def __init__(self,source):self.source=source
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  allowed(newurl,self.source)
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url,source,headline,snapshot):
 allowed(url,source)
 request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; DailyHeadlinesEvidence/1.0)','Accept':'text/html'})
 with urllib.request.build_opener(SameSourceRedirect(source)).open(request,timeout=20) as response:
  if response.status!=200 or 'html' not in response.headers.get('Content-Type',''):raise ValueError('ARTICLE_HTML_UNAVAILABLE')
  raw=response.read(MAX_BYTES+1)
  if len(raw)>MAX_BYTES:raise ValueError('ARTICLE_SIZE_LIMIT_NO_TRUNCATION')
  final=response.url;allowed(final,source)
  if norm(final)!=norm(url):raise ValueError('ARTICLE_REDIRECT_IDENTITY_CHANGED')
  document=raw.decode(response.headers.get_content_charset() or 'utf-8')
 pathlib.Path(snapshot).write_text(document)
 return dict(extract(document,final,source,headline),final_url=final,fetched_at=dt.datetime.now(TZ).isoformat())

def select(report):
 seen_urls=set();seen_events=set();selected=[]
 eligible=[r for r in report['records'] if r['reason'] in GAPS and r['score']>=75 and r['priority']<=5]
 # No source quota or source-name score: relevance, evidence readiness, recency.
 def key(r):
  try:published=timestamp(r['source_publish_time']).timestamp()
  except (ValueError,TypeError,AttributeError):published=0
  return (r['priority'],-r['score'],not bool(published),-published,r['item_index'])
 for row in sorted(eligible,key=key):
  if norm(row['source_url']) in seen_urls or row['event_id'] in seen_events:continue
  allowed(row['source_url'],row['source_name']);selected.append(row)
  seen_urls.add(norm(row['source_url']));seen_events.add(row['event_id'])
 return selected

def recover(scan,report,budget_dir,mode='PRODUCTION',rows=None):
 if mode not in ('PRODUCTION','HISTORICAL_TEST'):raise ValueError('INVALID_MODE')
 today=dt.datetime.now(TZ).date().isoformat()
 if mode=='PRODUCTION' and scan['date']!=today:raise ValueError('NO_HISTORICAL_PRODUCTION')
 path=pathlib.Path(budget_dir)/ (today+'.json');path.parent.mkdir(parents=True,exist_ok=True)
 result={'schema_version':1,'date':scan['date'],'scan_sha256':report['scan_sha256'],'mode':mode,'entries':[]}
 start=time.monotonic()
 with path.with_suffix('.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  budget=json.loads(path.read_text()) if path.exists() else {'date':today,'attempts':[]}
  candidates=select(report)
  if rows is not None:
   if mode!='HISTORICAL_TEST':raise ValueError('MANUAL_SELECTION_TEST_ONLY')
   requested={r['item_index'] for r in rows}
   candidates=[r for r in report['records'] if r['item_index'] in requested and r['reason'] in GAPS and r['score']>=75 and r['priority']<=5]
  for row in candidates:
   if dt.datetime.now(TZ).date().isoformat()!=today:break
   url=row['source_url'];previous=next((a for a in budget['attempts'] if norm(a['source_url'])==norm(url)),None)
   if previous:
    # Reuse only the exact input, mode and completed snapshot; never retry a URL today.
    if previous.get('scan_sha256')==report['scan_sha256'] and previous.get('mode')==mode and previous.get('result'):
     result['entries'].append(dict(previous['result'],item_index=row['item_index']))
    continue
   remaining=min(TOTAL_SECONDS-(time.monotonic()-start),TOTAL_SECONDS-sum(a['charged_seconds'] for a in budget['attempts']))
   if len(budget['attempts'])>=MAX_ARTICLES or remaining<=0:break
   timeout=min(ARTICLE_SECONDS,remaining)
   attempt={'source_url':url,'source_name':row['source_name'],'scan_sha256':report['scan_sha256'],'mode':mode,'charged_seconds':timeout}
   budget['attempts'].append(attempt);save(path,budget) # Reserve before network; crashes consume the reservation.
   snapshot=path.parent/(today+'-'+sha(url)[:16]+'.html')
   started=time.monotonic();entry={'item_index':row['item_index'],'source_url':url,'source_name':row['source_name'],'status':'FAILED'}
   try:
    process=subprocess.run([sys.executable,__file__,'--fetch',url,row['source_name'],row['headline'],str(snapshot)],capture_output=True,text=True,timeout=timeout)
    if process.returncode:raise ValueError(process.stderr.strip()[-500:] or 'FETCH_FAILED')
    content=json.loads(process.stdout);published=timestamp(content['published'])
    if not timestamp(scan['window_start'])<=published<=timestamp(scan['retrieval_time']):raise ValueError('ORIGINAL_WINDOW_MISMATCH')
    original=scan['items'][row['item_index']]
    if original.get('time_source') in ('FEED_PUBDATE','PAGE_METADATA') and original.get('published'):
     if abs((published-timestamp(original['published'])).total_seconds())>300:raise ValueError('FEED_PAGE_TIME_CONFLICT')
    entry.update(content,status='RECOVERED')
    entry['document_path']=str(snapshot)
   except Exception as e:entry['error']=str(e)
   attempt['charged_seconds']=round(time.monotonic()-started,3);entry['elapsed_seconds']=attempt['charged_seconds'];attempt['result']=entry
   save(path,budget);result['entries'].append(entry)
  result['daily_attempts']=len(budget['attempts']);result['daily_seconds']=round(sum(a['charged_seconds'] for a in budget['attempts']),3)
 result['elapsed_seconds']=round(time.monotonic()-start,3)
 return result

def overlay(scan,manifest,input_hash,allow_historical=False):
 if manifest.get('schema_version')!=1 or manifest.get('scan_sha256')!=input_hash or manifest.get('date')!=scan['date']:raise ValueError('EVIDENCE_SNAPSHOT_MISMATCH')
 if manifest.get('mode')!='PRODUCTION' and not (allow_historical and manifest.get('mode')=='HISTORICAL_TEST'):raise ValueError('HISTORICAL_EVIDENCE_NOT_PUBLISHABLE')
 if len(manifest['entries'])>MAX_ARTICLES:raise ValueError('EVIDENCE_LIMIT')
 out=copy.deepcopy(scan);out['evidence_mode']=manifest['mode'];seen=set()
 for e in manifest['entries']:
  n=e['item_index']
  if type(n) is not int or n<0 or n>=len(out['items']) or n in seen:raise ValueError('EVIDENCE_INDEX_MISMATCH')
  seen.add(n);item=out['items'][n]
  if item['url']!=e['source_url'] or item['source']!=e['source_name']:raise ValueError('EVIDENCE_URL_MISMATCH')
  allowed(e['source_url'],e['source_name'])
  if e['status']!='RECOVERED':continue
  if e.get('extraction')!='VISIBLE_ARTICLE_TEXT' or e.get('text_sha256')!=sha(e['evidence_text']):raise ValueError('EVIDENCE_INTEGRITY_FAILURE')
  if not timestamp(scan['window_start'])<=timestamp(e['published'])<=timestamp(scan['retrieval_time']):raise ValueError('EVIDENCE_TIME_WINDOW')
  timestamp(e['fetched_at'])
  item.update(evidence_text=e['evidence_text'],evidence_origin='ORIGINAL_URL',published=e['published'],time_source='PAGE_METADATA',window_status='IN_WINDOW_24H')
 return out

if __name__=='__main__':
 try:
  if len(sys.argv)!=6 or sys.argv[1]!='--fetch':raise ValueError('Original URL fetch only')
  print(json.dumps(fetch(*sys.argv[2:]),ensure_ascii=False))
 except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)

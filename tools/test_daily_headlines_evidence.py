"""Evidence recovery regressions. Synthetic pages only; no network or public output."""
import copy, datetime as dt, importlib.util, json, pathlib, tempfile, unittest, sys
from unittest.mock import patch
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('publisher',pathlib.Path(__file__).with_name('publish_daily_headlines.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p);m=p.evidence_module
URL='https://www.axios.com/energy/test-diesel-policy'
HEADLINE='Diesel policy changes global oil supply'
BODY='Officials announced a diesel policy change affecting global oil supply. '+('The published report identifies the policy and the affected supply routes. '*4)
def document(body=BODY,paywall=False,published='2026-10-10T03:00:00+08:00',visible=True):
 data={'@type':'NewsArticle','headline':HEADLINE,'datePublished':published,'articleBody':body,'isAccessibleForFree':not paywall}
 return '<html><head><link rel="canonical" href="'+URL+'"><script type="application/ld+json">'+json.dumps(data)+'</script></head><body><h1>'+HEADLINE+'</h1><article>'+('<p>'+body+'</p>' if visible else '')+'</article></body></html>'
class EvidenceTests(unittest.TestCase):
 def test_visible_complete_text_retained(self):
  result=m.extract(document(),URL,'AXIOS',HEADLINE);self.assertEqual(result['evidence_text'],BODY.strip())
 def test_paywall_refused_even_if_body_in_script(self):
  with self.assertRaisesRegex(ValueError,'PAYWALL'):m.extract(document(paywall=True),URL,'AXIOS',HEADLINE)
 def test_hidden_script_body_not_evidence(self):
  with self.assertRaisesRegex(ValueError,'INCOMPLETE'):m.extract(document(visible=False),URL,'AXIOS',HEADLINE)
 def test_time_never_inferred(self):
  for value in ['3 hours ago','2026-10-10T03:00:00']:
   with self.assertRaisesRegex(ValueError,'TIME_MISSING'):m.extract(document(published=value),URL,'AXIOS',HEADLINE)
 def test_visible_body_with_verified_byline(self):
  doc=document(body=BODY+' By Test Writer for Axios.com').replace('"isAccessibleForFree": true','"isAccessibleForFree": true, "author": {"name": "Test Writer"}')
  result=m.extract(doc,URL,'AXIOS',HEADLINE)
  self.assertEqual(result['evidence_text'],BODY.strip());self.assertEqual(result['byline'],'By Test Writer for Axios.com')
 def test_title_from_article_metadata_when_h1_missing(self):
  self.assertEqual(m.extract(document().replace('<h1>'+HEADLINE+'</h1>',''),URL,'AXIOS',HEADLINE)['page_title'],HEADLINE)
 def test_explicit_compact_timezone(self):
  self.assertEqual(m.timestamp('2026-10-09T15:30:00-0400').isoformat(),'2026-10-10T03:30:00+08:00')
 def test_wrong_article(self):
  with self.assertRaisesRegex(ValueError,'IDENTITY'):m.extract(document().replace(URL,URL+'-other'),URL,'AXIOS',HEADLINE)
 def test_no_other_sources(self):
  for url in ['http://www.axios.com/a','https://www.axios.com.evil.org/a','https://127.0.0.1/a','https://www.reuters.com/a']:
   with self.assertRaises(ValueError):m.allowed(url,'AXIOS')
 def test_truncated_400_with_terminal_period_still_rejected(self):
  self.assertEqual(p.insufficient({'headline':HEADLINE,'summary':'x'*399+'.'}),'TRUNCATED_SUMMARY')
 def test_full_evidence_separate_from_summary(self):
  item={'headline':HEADLINE,'summary':'x'*400,'evidence_text':BODY};self.assertIsNone(p.insufficient(item));self.assertEqual(item['summary'],'x'*400)
 def test_compound_verb_not_energy(self):
  self.assertNotEqual(p.classify({'headline':'WTO says trade grows despite conflict-fueled disruption','summary':'Global trade conditions remain uncertain.'})[0],'ENERGY')
  self.assertEqual(p.classify({'headline':'Diesel fuel shortage disrupts shipping','summary':''})[0],'ENERGY')
 def test_financial_coupon_not_shopping_noise(self):
  self.assertFalse(p.non_news({'headline':'Treasury bond coupon payments rise','url':'https://www.axios.com/article'}))
 def test_non_news_never_enriched(self):
  for title,url in [('Valvoline Coupons and Promo Codes','https://www.wired.com/a'),('7 Best Cheap Phones Tested and Reviewed','https://www.wired.com/b'),('Oil prices','https://www.marketwatch.com/investing/future/cl.1')]:
   self.assertTrue(p.non_news({'headline':title,'url':url}))
 def test_limit_shared_across_snapshots_and_failures(self):
  today=dt.datetime.now(m.TZ).date().isoformat();scan={'date':today};rows=[{'item_index':i,'source_url':URL+str(i),'source_name':'AXIOS','source_publish_time':today+'T01:00:00+08:00','headline':HEADLINE,'event_id':'dh-test-'+str(i),'reason':'TRUNCATED_SUMMARY','score':85,'priority':1} for i in range(10)]
  report={'scan_sha256':'one','records':rows}
  with tempfile.TemporaryDirectory() as temp,patch.object(m.subprocess,'run',side_effect=TimeoutError('TEST TIMEOUT')) as fetch:
   first=m.recover(scan,report,temp);second=m.recover(scan,{**report,'scan_sha256':'two'},temp)
   self.assertEqual(fetch.call_count,5);self.assertEqual(first['daily_attempts'],5);self.assertEqual(second['daily_attempts'],5)
 def test_time_budget_survives_crash_reservation(self):
  today=dt.datetime.now(m.TZ).date().isoformat()
  with tempfile.TemporaryDirectory() as temp,patch.object(m.subprocess,'run') as fetch:
   m.save(pathlib.Path(temp)/(today+'.json'),{'date':today,'attempts':[{'source_url':URL,'charged_seconds':180}]})
   rows=[{'item_index':1,'source_url':URL+'2','source_name':'AXIOS','source_publish_time':today+'T01:00:00+08:00','headline':HEADLINE,'event_id':'dh-test-2','reason':'TRUNCATED_SUMMARY','score':85,'priority':1}]
   m.recover({'date':today},{'scan_sha256':'one','records':rows},temp);fetch.assert_not_called()
 def test_historical_replay_cannot_enter_production(self):
  scan={'date':'2026-10-10','items':[]};manifest={'schema_version':1,'date':scan['date'],'scan_sha256':'test','mode':'HISTORICAL_TEST','entries':[]}
  with self.assertRaisesRegex(ValueError,'NOT_PUBLISHABLE'):m.overlay(scan,manifest,'test')
 def test_frozen_evidence_tampering_rejected(self):
  scan={'date':'2026-10-10','window_start':'2026-10-09T06:00:00+08:00','retrieval_time':'2026-10-10T06:00:00+08:00','items':[{'source':'AXIOS','url':URL}]}
  entry={'item_index':0,'source_url':URL,'source_name':'AXIOS','status':'RECOVERED',**m.extract(document(),URL,'AXIOS',HEADLINE),'fetched_at':'2026-10-10T07:10:00+08:00'}
  manifest={'schema_version':1,'date':scan['date'],'scan_sha256':'test','mode':'PRODUCTION','entries':[entry]}
  self.assertEqual(m.overlay(scan,manifest,'test')['items'][0]['evidence_text'],BODY.strip())
  entry['evidence_text']+=' fabricated'
  with self.assertRaisesRegex(ValueError,'INTEGRITY'):m.overlay(scan,manifest,'test')
if __name__=='__main__':unittest.main()

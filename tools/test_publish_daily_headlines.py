"""Safety tests use synthetic TEST fixtures only; no network or published fixture data."""
import copy, datetime as dt, importlib.util, pathlib, sys, tempfile, unittest
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('daily',pathlib.Path(__file__).with_name('publish_daily_headlines.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SafetyTests(unittest.TestCase):
 def setUp(self):
  self.date=dt.datetime.now(m.TZ).date().isoformat()
  self.item={'headline':'Fed reviews private-credit loans at TEST Bank','summary':'The Fed is reviewing loan valuations and collateral quality at TEST Bank.','source':'TEST SOURCE','url':'https://test.example.org/article','published':self.date+'T06:00:00+08:00','window_status':'IN_WINDOW_24H','time_source':'FEED_PUBDATE'}
  self.row={'item_index':0,'event_id':'dh-private-credit-review','reason':None,'headline':self.item['headline'],'summary':self.item['summary'],'source_url':self.item['url'],'source_name':'TEST SOURCE','source_publish_time':self.item['published'],'category':'MACRO','previous_source_matches':[],'previous_published_events':[],'score':90}
  self.report={'date':self.date,'scan_sha256':'test','records':[self.row],'eligible_clusters':[[self.row]]}
  self.scan={'items':[self.item],'source_status':{'TEST':{'status':'OK'}}}
  self.fact='测试媒体报道，美联储正在审查测试银行的贷款估值与抵押品质量。'
  self.h={'event_id':self.row['event_id'],'evidence_indices':[0],'headline_cn':'测试银行贷款估值审查','fact_cn':self.fact,'analysis_cn':'值得关注的是，估值审查可能影响银行风险偏好及信贷供给，尚不能据此判断已出现系统性损失。','confidence':'PARTIAL','material_new_information':'TEST 新监管审查','mcis_relevance':'TEST 金融条件','fact_checks':[{'item_index':0,'quote':self.item['summary'],'fact_cn':self.fact}],'entities':[]}
  self.packet={'date':self.date,'scan_sha256':'test','review':{'status':'REVIEWED',**{k:True for k in ['facts_vs_analysis','numbers_names','headline_summary_consistency','material_novelty','evidence_sufficiency']}},'headlines':[self.h],'decisions':{self.row['event_id']:{'action':'SELECT','reason':'TEST'}}}
  self.old=m.check_url;m.check_url=lambda url:{'url':url,'status':200}
 def tearDown(self):m.check_url=self.old
 def check(self):return m.validate(self.scan,self.report,self.packet,True)
 def test_valid_evidence(self):self.assertEqual(len(self.check()[0]['headlines']),1)
 def test_fabricated_number(self):
  self.h['headline_cn']+='99%';self.assertRaisesRegex(ValueError,'Unsupported number',self.check)
 def test_fabricated_quote(self):
  self.h['fact_checks'][0]['quote']='unsupported';self.assertRaisesRegex(ValueError,'quote not found',self.check)
 def test_unmapped_claim(self):
  self.h['fact_cn']+='贷款违约。';self.assertRaisesRegex(ValueError,'Unmapped',self.check)
 def test_single_source_confidence(self):
  self.h['confidence']='CONFIRMED';self.assertRaisesRegex(ValueError,'independent',self.check)
 def test_duplicate_event(self):
  self.packet['headlines'].append(copy.deepcopy(self.h));self.assertRaisesRegex(ValueError,'Duplicate',self.check)
 def test_old_news_without_comparison(self):
  self.row['previous_source_matches']=[{'summary':self.item['summary']}];self.assertRaisesRegex(ValueError,'Old-news',self.check)
 def test_replayed_novelty(self):
  self.row['previous_source_matches']=[{'summary':self.item['summary']}];self.h.update(prior_comparison='TEST',novelty_quote=self.item['summary']);self.assertRaisesRegex(ValueError,'already',self.check)
 def test_truncated_evidence(self):
  self.row['reason']='TRUNCATED_SUMMARY';self.assertRaisesRegex(ValueError,'Ineligible',self.check)
 def test_missing_review(self):
  self.packet['review']['status']='PENDING';self.assertRaisesRegex(ValueError,'review required',self.check)
 def test_snapshot_changed(self):
  self.packet['scan_sha256']='changed';self.assertRaisesRegex(ValueError,'snapshot',self.check)
 def test_analysis_not_signposted(self):
  self.h['analysis_cn']='必然引发市场崩溃。';self.assertRaisesRegex(ValueError,'signposted',self.check)
 def test_arrow_chain(self):
  self.h['headline_cn']+='→→';self.assertRaisesRegex(ValueError,'style',self.check)
 def test_url_failure(self):
  def fail(url):raise ValueError('URL unavailable')
  m.check_url=fail;self.assertRaisesRegex(ValueError,'URL',self.check)
 def test_empty_incomplete_not_no_change(self):
  self.packet['headlines']=[];self.assertRaisesRegex(ValueError,'coverage',self.check)
 def test_empty_failed_source_not_no_change(self):
  self.packet.update(headlines=[],no_material_change_reason='TEST',coverage_complete=True,decisions={self.row['event_id']:{'action':'REJECT','reason':'TEST'}})
  self.scan['source_status']['TEST']['status']='SOURCE_FAILED';self.assertRaisesRegex(ValueError,'Failed sources',self.check)
 def test_completed_no_change(self):
  self.packet.update(headlines=[],no_material_change_reason='TEST complete',coverage_complete=True,decisions={self.row['event_id']:{'action':'REJECT','reason':'TEST below threshold'}})
  self.assertEqual(self.check()[0]['status'],'NO_MATERIAL_CHANGE')
 def test_unknown_source_time(self):
  self.item['published']='UNKNOWN';self.row['reason']='TIME_UNVERIFIED';self.assertRaisesRegex(ValueError,'Ineligible',self.check)
 def test_product_noise(self):self.assertEqual(m.classify({'headline':'Omega has new James Bond watches','summary':'New watches.'})[0],'OTHER')
 def test_truncation_detection(self):self.assertEqual(m.insufficient({'headline':'test','summary':'<p>Enough words in this synthetic test sentence to pass minimum length before a dangling element.</p><p>'}),'TRUNCATED_SUMMARY')
 def test_negative_evidence_index(self):
  self.h['evidence_indices']=[-1];self.assertRaisesRegex(ValueError,'Invalid evidence',self.check)
 def test_number_substring_not_evidence(self):
  self.item['summary']+=' 1999.';self.h['headline_cn']+='99';self.assertRaisesRegex(ValueError,'Unsupported number',self.check)
 def test_relevance_override(self):
  self.row['reason']='BELOW_MATERIALITY_THRESHOLD';self.h.update(relevance_override_reason='TEST material regulation',category_override='MACRO');self.assertEqual(len(self.check()[0]['headlines']),1)
 def test_override_cannot_allow_truncated(self):
  self.row['reason']='TRUNCATED_SUMMARY';self.h.update(relevance_override_reason='TEST',category_override='MACRO');self.assertRaisesRegex(ValueError,'Ineligible',self.check)
 def test_cluster_identity_cannot_evade_memory(self):
  self.packet['clusters']=[{'event_id':'dh-invented-new-id','item_indices':[0],'rationale':'TEST'}];self.assertRaisesRegex(ValueError,'preserve',self.check)
 def test_cluster_duplicate_members(self):
  self.packet['clusters']=[{'event_id':self.row['event_id'],'item_indices':[0,0],'rationale':'TEST'}];self.assertRaisesRegex(ValueError,'Invalid editorial',self.check)
 def test_cluster_preserves_existing_identity(self):
  self.packet['clusters']=[{'event_id':self.row['event_id'],'item_indices':[0],'rationale':'TEST same event'}];self.assertEqual(len(self.check()[0]['headlines']),1)
 def test_unknown_gap_blocks_no_change(self):
  self.row['reason']='TRUNCATED_SUMMARY';self.packet.update(headlines=[],no_material_change_reason='TEST',coverage_complete=True,decisions={self.row['event_id']:{'action':'REJECT','reason':'TEST insufficient'}});self.assertRaisesRegex(ValueError,'evidence gap',self.check)
if __name__=='__main__':unittest.main()

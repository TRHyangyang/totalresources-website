"""Safety tests use synthetic TEST fixtures only; no network or published fixture data."""
import json, copy, datetime as dt, importlib.util, pathlib, sys, tempfile, unittest
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('daily',pathlib.Path(__file__).with_name('publish_daily_headlines.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SafetyTests(unittest.TestCase):
 def setUp(self):
  self.old_root=m.ROOT;self.fixture_root=tempfile.TemporaryDirectory();m.ROOT=pathlib.Path(self.fixture_root.name)
  self.date=dt.datetime.now(m.TZ).date().isoformat()
  self.item={'headline':'Fed reviews private-credit loans at TEST Bank','summary':'The Fed is reviewing loan valuations and collateral quality at TEST Bank.','source':'TEST SOURCE','url':'https://test.example.org/article','published':self.date+'T06:00:00+08:00','window_status':'IN_WINDOW_24H','time_source':'FEED_PUBDATE'}
  self.row={'item_index':0,'event_id':'dh-private-credit-review','reason':None,'headline':self.item['headline'],'summary':self.item['summary'],'source_url':self.item['url'],'source_name':'TEST SOURCE','source_publish_time':self.item['published'],'category':'MACRO','previous_source_matches':[],'previous_published_events':[],'score':90}
  self.report={'date':self.date,'scan_sha256':'test','records':[self.row],'eligible_clusters':[[self.row]]}
  self.scan={'items':[self.item],'source_status':{'TEST':{'status':'OK'}}}
  self.fact='测试媒体报道，美联储正在审查测试银行的贷款估值与抵押品质量。'
  self.h={'event_id':self.row['event_id'],'evidence_indices':[0],'headline_cn':'测试银行贷款估值审查','fact_cn':self.fact,'analysis_cn':'值得关注的是，估值审查可能影响银行风险偏好及信贷供给，尚不能据此判断已出现系统性损失。','confidence':'PARTIAL','material_new_information':'TEST 新监管审查','mcis_relevance':'TEST 金融条件','fact_checks':[{'item_index':0,'quote':self.item['summary'],'fact_cn':self.fact}],'entities':[]}
  self.packet={'date':self.date,'scan_sha256':'test','review':{'status':'REVIEWED',**{k:True for k in ['facts_vs_analysis','numbers_names','headline_summary_consistency','material_novelty','evidence_sufficiency']}},'headlines':[self.h],'decisions':{self.row['event_id']:{'action':'SELECT','reason':'TEST'}}}
  self.old=m.check_url;m.check_url=lambda url:{'url':url,'status':200}
 def tearDown(self):
  m.check_url=self.old;m.ROOT=self.old_root;self.fixture_root.cleanup()
 def check(self):return m.validate(self.scan,self.report,self.packet,True)
 def test_recovered_fact_quotes_use_full_evidence(self):
  recovered='The Fed confirmed a new collateral review affecting TEST Bank.'
  self.item['evidence_text']=recovered;self.row['evidence_text']=recovered
  self.h['fact_checks'][0]['quote']=recovered
  self.assertEqual(len(self.check()[0]['headlines']),1)
 def test_recovery_does_not_waive_editorial_review(self):
  self.item['evidence_text']=self.item['summary'];self.packet['review']['status']='PENDING'
  self.assertRaisesRegex(ValueError,'review required',self.check)
 def test_evidence_packet_hash_required(self):
  self.report['evidence_sha256']='frozen'
  self.assertRaisesRegex(ValueError,'evidence snapshot',self.check)
  self.packet['evidence_sha256']='frozen';self.assertEqual(len(self.check()[0]['headlines']),1)
 def test_historical_test_never_validates_for_publication(self):
  self.scan['evidence_mode']='HISTORICAL_TEST'
  self.assertRaisesRegex(ValueError,'Historical test',self.check)
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
 def test_private_body_never_enters_public_artifacts(self):
  secret='SYNTHETIC_PAYWALL_BODY_DO_NOT_PUBLISH ' * 12
  reference='/private/evidence/paid-article.txt'
  self.item.update(evidence_text=self.item['summary']+' '+secret,body_text=secret,evidence_ref=reference)
  self.row.update(evidence_text=self.item['evidence_text'],body_text=secret,evidence_ref=reference)
  self.h.update(mcis_relevance=secret,material_new_information=secret,body_text=secret,evidence_ref=reference)
  self.row['previous_source_matches']=[{'headline':'TEST old event','evidence_text':secret}]
  self.h.update(prior_comparison=secret,novelty_quote=self.item['summary'])
  payload,_=self.check()
  self.assertNotIn(secret,json.dumps(payload));self.assertNotIn('mcis_relevance',payload['headlines'][0])
  # Defense in depth: callers attaching private data after validation cannot serialize it.
  payload.update(evidence_text=secret,body_text=secret,evidence_ref=reference)
  payload['headlines'][0].update(evidence_text=secret,body_text=secret,evidence_ref=reference)
  payload['headlines'][0]['sources'][0].update(body_text=secret,evidence_ref=reference)
  root=m.ROOT
  (root/'tools').mkdir();(root/'tools/daily_headlines_page.html').write_text((self.old_root/'tools/daily_headlines_page.html').read_text())
  (root/'index.html').write_text('<html><head></head><body><section class="hero">KEEP HERO</section><section class="global-pulse">KEEP PULSE</section><!-- DAILY HEADLINES V1 --></body></html>')
  (root/'intelligence.html').write_text('<html><head></head><body><!-- DAILY HEADLINES V1 --><section class="latest-section" id="research-archive">KEEP RESEARCH</section></body></html>')
  (root/'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://totalresources.info/</loc></url></urlset>')
  archive=root/'intelligence/daily-headlines';archive.mkdir(parents=True)
  (archive/'2000-01-01.html').write_text('KEEP OLD ARTICLE')
  old=root/'data/daily-headlines/2000/01/2000-01-01.json';old.parent.mkdir(parents=True);old.write_text('{"date":"2000-01-01","headlines":[]}')
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp)/'preview';m.generate(out,payload)
   public=list(out.rglob('*.html'))+list(out.rglob('*.json'))
   for path in public:
    text=path.read_text()
    for forbidden in ('SYNTHETIC_PAYWALL_BODY_DO_NOT_PUBLISH',reference,'evidence_text','body_text','evidence_ref','prior_comparison','fact_checks'):
     self.assertNotIn(forbidden,text,str(path))
   published=json.loads((out/'data/daily-headlines/latest.json').read_text())
   self.assertEqual(published['headlines'][0]['summary'],self.h['fact_cn']+self.h['analysis_cn'])
   self.assertIn(self.h['headline_cn'],(out/'intelligence/daily-headlines'/ (self.date+'.html')).read_text())
   self.assertEqual((out/'intelligence/daily-headlines/2000-01-01.html').read_text(),'KEEP OLD ARTICLE')
   self.assertEqual((out/old.relative_to(root)).read_bytes(),old.read_bytes())
   dated=out/'data/daily-headlines'/self.date[:4]/self.date[5:7]/(self.date+'.json')
   self.assertEqual(json.loads(dated.read_text()),published)
 def test_body_cannot_be_disguised_as_editorial_summary(self):
  self.item['body_text']=self.fact
  self.assertRaisesRegex(ValueError,'copies source body',self.check)
 def test_body_cannot_be_disguised_as_english_headline(self):
  self.item['evidence_text']='Private paid article sentence with confidential original wording. '*5
  self.item['evidence_text']+=self.item['summary']
  self.h['headline_en']=self.item['evidence_text'][:130]
  self.assertRaisesRegex(ValueError,'copies source body',self.check)
 def test_public_field_cannot_contain_nested_private_object(self):
  payload,_=self.check();payload['headlines'][0]['summary']={'body_text':'PRIVATE'}
  self.assertRaisesRegex(ValueError,'public text',m.public_payload,payload)
 def test_private_reports_cannot_be_written_into_public_tree(self):
  self.assertRaisesRegex(ValueError,'outside website',m.private_report_destination,m.ROOT/'data/private')
  with tempfile.TemporaryDirectory() as tmp:
   m.private_report_destination(pathlib.Path(tmp))
 def test_historical_private_body_remains_available_for_novelty_qa(self):
  self.row['previous_source_matches']=[{'evidence_text':self.item['summary']}]
  self.h.update(prior_comparison='TEST comparison',novelty_quote=self.item['summary'])
  self.assertRaisesRegex(ValueError,'already in historical',self.check)
 def assert_copy_requires_review(self,body,edited=None,field='summary'):
  self.item[field]=body
  # Full evidence remains available for factual mapping; REVIEWED cannot waive copy QA.
  self.item['evidence_text']=self.item.get('evidence_text','')+' '+body
  self.h['fact_cn']=self.fact+(body if edited is None else edited)
  self.h['fact_checks'][0].update(quote=body,fact_cn=self.h['fact_cn'])
  with self.assertRaisesRegex(ValueError,'HUMAN_REVIEW_REQUIRED'):
   self.check()
 def test_72_character_full_paid_summary_requires_review(self):
  paid='Private subscribers receive the full report. Oil supply remains limited.'
  self.assertEqual(len(paid),72)
  self.assert_copy_requires_review(paid)
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp)/'preview'
   with self.assertRaisesRegex(ValueError,'HUMAN_REVIEW_REQUIRED'):
    payload,_=self.check();m.generate(out,payload)
   self.assertFalse(out.exists())
 def test_copy_gate_has_no_short_body_length_exemption(self):
  for body in ['Oil fell.','Oil supply is tight.','Subscribers received the complete oil market report.']:
   with self.subTest(body=body):self.assert_copy_requires_review(body)
 def test_short_chinese_paid_body_requires_review(self):
  self.assert_copy_requires_review('油轮运输受阻，炼厂原料供应趋紧。')
 def test_mixed_language_paid_body_requires_review(self):
  self.assert_copy_requires_review('Oil supply趋紧，炼厂正在调整采购计划。')
 def test_cosmetic_changes_do_not_hide_paid_body(self):
  self.assert_copy_requires_review('Oil supply remains limited.','ＯＩＬ supply—REMAINS\u200b limited!')
 def test_light_english_rewrite_requires_review(self):
  self.assert_copy_requires_review('Private subscribers receive the full report. Oil supply remains limited.',
   'Private readers receive the complete report. Oil supply is still limited.')
 def test_light_chinese_rewrite_requires_review(self):
  self.assert_copy_requires_review('油轮运输受阻，炼厂原料供应趋紧。','油轮运输遇阻，炼厂原料供应偏紧。')
 def test_light_mixed_rewrite_requires_review(self):
  self.assert_copy_requires_review('Oil supply趋紧，炼厂正在调整采购计划。','Oil supply偏紧，炼厂正在调整采购安排。')
 def test_each_private_evidence_field_is_compared(self):
  for field in ('summary','evidence_text','body_text'):
   with self.subTest(field=field):self.assert_copy_requires_review('Oil supply remains limited.',field=field)
 def test_missing_editorial_summary_never_falls_back_to_body(self):
  self.item['summary']='Private subscribers receive the full report. Oil supply remains limited.'
  self.h.pop('fact_cn')
  with self.assertRaisesRegex(ValueError,'HUMAN_REVIEW_REQUIRED'):self.check()
 def test_raw_full_summary_stays_private_in_all_generated_outputs(self):
  self.item['summary']+=' '+'SYNTHETIC_PAYWALL_BODY_DO_NOT_PUBLISH '*12
  self.test_private_body_never_enters_public_artifacts()
 def test_split_body_across_editorial_fields_requires_review(self):
  body='Private subscribers receive the full report about oil supply and refinery constraints.'
  self.item['summary']=body
  self.h['fact_cn']=self.fact+'Private subscribers receive the full report'
  self.h['analysis_cn']='值得关注的是，about oil supply and refinery constraints. 信贷风险仍有待进一步核实。'
  self.h['fact_checks'][0].update(quote=body,fact_cn=self.h['fact_cn'])
  with self.assertRaisesRegex(ValueError,'HUMAN_REVIEW_REQUIRED'):self.check()
 def test_unapproved_summary_field_cannot_replace_editorial_fields(self):
  self.h['summary']='PRIVATE UNREVIEWED RAW BODY'
  payload,_=self.check()
  self.assertEqual(payload['headlines'][0]['summary'],self.fact+self.h['analysis_cn'])
  self.assertNotIn('PRIVATE UNREVIEWED RAW BODY',json.dumps(payload))
class ExtractionAndStatusTests(unittest.TestCase):
 def test_html_block_boundaries_preserved(self):
  self.assertEqual(m.clean('<p>First <a href="https://example.org">fact</a>.</p><p>Second fact &amp; detail.</p>'), 'First fact. Second fact & detail.')
 def test_incomplete_html_still_rejected(self):
  self.assertEqual(m.insufficient({'headline':'TEST','summary':'<p>'+('Evidence words '*8)+'</p><p><st'}),'TRUNCATED_SUMMARY')
 def test_public_failure_has_no_private_details(self):
  receipt={'date':'2026-10-11','status':'QA FAIL','end_time':'2026-10-11T07:11:41+08:00','error':'PRIVATE','folder':'PRIVATE','input_files':['PRIVATE']}
  result=m.public_status(receipt)
  self.assertEqual(result['status'],'NO_VERIFIED_UPDATE');self.assertNotIn('PRIVATE',str(result))
  self.assertEqual(set(result),{'schema_version','date','timezone','status','updated_at'})
 def test_incomplete_run_cannot_be_public_failure(self):
  for status in ['INPUT NOT READY','DEPLOY FAIL','SUCCESS']:
   with self.assertRaises(ValueError):m.public_status({'date':'2026-10-11','status':status,'end_time':'2026-10-11T07:11:41+08:00'})
  with self.assertRaises(KeyError):m.public_status({'date':'2026-10-11','status':'QA FAIL'})
 def test_column_has_no_duplicate_heading(self):
  self.assertNotIn('<h2',m.widget(column=True));self.assertIn('#archive',m.widget(column=True))
if __name__=='__main__':unittest.main()

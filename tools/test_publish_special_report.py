"""Regression checks for the shared homepage and independent Special Reports archive."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SpecialHomeTest(unittest.TestCase):
    def test_publish_latest_and_backfill_preserve_other_home_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            site = tmp/'site'
            shutil.copytree(ROOT, site, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            baseline = (site/'index.html').read_text()
            before, rest = baseline.split('<!-- SPECIAL REPORTS HOME -->')
            _, after = rest.split('<!-- END SPECIAL REPORTS HOME -->')
            article_files = {p.relative_to(site):p.read_bytes() for folder in ('intelligence','weekly-outlook') for p in (site/folder).rglob('*') if p.is_file()}
            for day, slug in [('2099-10-18', 'fixture-new'), ('2099-10-11', 'fixture-old')]:
                source = tmp/(slug+'.md')
                source.write_text(f'---\ntitle: "新专题 <标题>"\nsummary: "简短摘要 & 完整说明"\nslug: {slug}\npublication_date: {day}\nstatus: FINAL\nauthors: [作者]\nsource: 测试来源\n---\n# 标题\n\n正文[^n]\n\n## 附录\n\n完整附录\n\n[^n]: 脚注内容\n')
                approval = tmp/(slug+'.json')
                approval.write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),publication_date=day,rights_cleared=True,image_rights_cleared_or_no_image=True,file_checks_completed=True,publish_approved=True,reviewer='test fixture',evidence=['test only'])))
                result = subprocess.run([sys.executable,str(site/'tools/publish_special_report.py'),str(source),'--publish','--approval',str(approval)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                home = (site/'index.html').read_text()
                head, block = home.split('<!-- SPECIAL REPORTS HOME -->')
                block, tail = block.split('<!-- END SPECIAL REPORTS HOME -->')
                self.assertEqual(head,before)
                self.assertEqual(tail,after)
                self.assertIn('fixture-new.html',block)
                self.assertNotIn('fixture-old.html',block)
                self.assertIn('简短摘要 &amp; 完整说明',block)
                self.assertIn('&lt;标题&gt;',block)
                self.assertEqual(block.count('<article '),1)
                self.assertLess(home.index('<!-- END WEEKLY OUTLOOK HOME -->'),home.index('<!-- SPECIAL REPORTS HOME -->'))
            archive = (site/'special-reports/index.html').read_text()
            self.assertIn('fixture-new.html',archive)
            self.assertIn('fixture-old.html',archive)
            for path, data in article_files.items():
                self.assertEqual((site/path).read_bytes(),data)

if __name__ == '__main__':
    unittest.main()

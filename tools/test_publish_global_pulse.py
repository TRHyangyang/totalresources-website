import unittest
from publish_global_pulse import simple_table_cells, render_markdown, frontmatter


class TableParsingTests(unittest.TestCase):
    def test_soft_wrapped_emphasis(self):
        self.assertEqual(render_markdown("**FIRST\nSECOND**"), "<p><strong>FIRST SECOND</strong></p>")

    def test_pipe_columns(self):
        self.assertEqual(simple_table_cells('| A | B | C |', [(0,3),(4,7),(8,11)]), ['A','B','C'])

    def test_pipe_count_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            simple_table_cells('| A | B |', [(0,3),(4,7),(8,11)])

    def test_display_columns_and_single_space(self):
        self.assertEqual(simple_table_cells('  名称  值  说明', [(2,6),(8,10),(12,20)]), ['名称','值','说明'])
        self.assertEqual(simple_table_cells('  A      42 note', [(2,6),(8,11),(12,20)]), ['A','42','note'])

    def test_pipe_render(self):
        output = render_markdown('|名称|数值|说明|\n|---|---|---|\n|甲|42|待确认|')
        self.assertIn('<th>数值</th>', output)
        self.assertIn('<td>甲</td><td>42</td><td>待确认</td>', output)

    def test_ambiguous_display_boundary_rejected(self):
        with self.assertRaises(ValueError):
            simple_table_cells('中A', [(0,1),(1,4)])


class MarketSectionTests(unittest.TestCase):
    def source(self, heading):
        return "---\ndate: 2026-01-01\npublication_status: FINAL\nsystem: MCIS\ntype: MCIS Global Pulse\n---\n# 标题\n" + heading + "\n市场正文\n## 关于我们\n说明\n## 免责声明\n说明"

    def test_market_narrative_heading(self):
        metadata, body = frontmatter(self.source("## 一、今天市场真正发生了什么"))
        self.assertEqual(metadata["date"], "2026-01-01")
        self.assertIn("市场正文", body)

    def test_unknown_market_heading_rejected(self):
        with self.assertRaises(ValueError):
            frontmatter(self.source("## 未知标题"))


if __name__ == '__main__':
    unittest.main()

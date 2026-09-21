#!/usr/bin/env python3
"""Render one archived FINAL MCIS Global Pulse Markdown file as a static page.

Usage: python3 tools/publish_global_pulse.py /absolute/path/to/final.md
Only the article is generated. Curated index/homepage/sitemap changes remain explicit.
"""

import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "tools" / "global_pulse_article.html"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
PRIVATE_TERMS = re.compile(r"MCIS|OpenClaw|Vault|Truth Layer|\bGate\b|VERIFIED|Human CIO|\bRaw\b|\bShadow\b", re.I)


def public_body(markdown):
    """Preserve the analysis while translating internal production labels."""
    marker = "\n## 免责声明\n"
    if markdown.count(marker) != 1:
        raise ValueError("A single disclaimer section is required")
    research, internal_disclaimer = markdown.split(marker, 1)
    research = research.replace("写入Vault", "归档")
    research = research.replace("自动包抓到", "晨间资料记录")
    research = research.replace("研究包", "研究材料")
    research = research.replace("精确的Truth Layer价格", "精确核验的价格")

    disclaimer = internal_disclaimer.strip()
    replacements = (
        ("MCIS/OpenClaw晨间研究", "晨间研究材料"),
        ("MCIS/OpenClaw RSS情报", "晨间公开资讯"),
        ("已落盘", "已归档"),
        ("RSS与原始数据", "公开资讯与原始数据"),
        ("主要来自单一媒体或知情人士口径", "部分来自二级来源、单一媒体或知情人士口径"),
        ("未重新采集或联网补缺", "数据和信息来源可能存在时点差异，缺口未以推测填补"),
        ("Truth Layer有效人工核验内容及市场价格Gate锚为空，状态为DEGRADED", "部分市场价格缺少足够的直接核验依据"),
        ("Truth Layer有效内容为空，市场价格Gate锚为零，状态为DEGRADED", "部分市场价格缺少足够的直接核验依据"),
        ("交易所机器层核验", "交易所直接核验"),
        ("不自动升级为正式VERIFIED价格", "不能视为完全确认的价格"),
        ("不标记为VERIFIED结算", "不能视为完全确认的结算"),
        ("Human CIO已批准任何投资决定", "已获批准的投资决定"),
        ("涉及投资与交易的最终决定仅由 Human CIO 作出。", "涉及投资与交易的最终决定应由相关决策主体独立作出。"),
        ("部分媒体条目的准确发布时间或完整正文不可得", "部分信息来自二级来源，且部分媒体条目的准确发布时间或完整正文不可得"),
        ("研究包", "研究材料"),
    )
    for internal, public in replacements:
        disclaimer = disclaimer.replace(internal, public)
    disclaimer = disclaimer.replace("本文仅供研究与信息交流，不构成投资建议。", "").strip()
    if "冲突" not in disclaimer or "待核" not in disclaimer:
        disclaimer += " 不同来源可能存在时点差异；冲突或待核信息不能视为完全确认。"
    disclaimer += "本文仅供研究与信息交流，不构成投资建议，也不构成交易执行建议；读者应独立核验并作出判断。"
    published = research + marker + disclaimer
    if PRIVATE_TERMS.search(published):
        raise ValueError("Unreviewed internal production term remains in public article")
    for required in ("研究截止", "二级来源", "冲突", "待核", "不构成投资建议", "不构成交易执行建议", "独立核验"):
        if required not in disclaimer:
            raise ValueError("Public disclaimer misses: " + required)
    return published


def frontmatter(source):
    lines = source.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("Missing YAML front matter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("Unclosed YAML front matter") from exc
    metadata = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    if metadata.get("publication_status") != "FINAL":
        raise ValueError("publication_status must be FINAL")
    if metadata.get("system") != "MCIS" or metadata.get("type") != "MCIS Global Pulse":
        raise ValueError("Source must be an MCIS Global Pulse")
    date = metadata.get("date", "")
    if not DATE_RE.fullmatch(date):
        raise ValueError("Invalid or missing publication date")
    body = "\n".join(lines[end + 1:]).strip()
    for required in ("## 市场留下来的几组数字", "## 关于我们", "## 免责声明"):
        if required not in body:
            raise ValueError("Missing required article section: " + required)
    return metadata, body


def safe_url(value):
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in ("http", "https", "mailto"):
        raise ValueError("Unsafe Markdown link scheme")
    if value.startswith("//") or any(c in value for c in ('"', "<", ">")):
        raise ValueError("Unsafe Markdown link")
    return html.escape(value, quote=True)


def inline(text):
    # Escape text before adding the small set of supported Markdown spans.
    placeholders = []

    def save(markup):
        placeholders.append(markup)
        return "\x00{}\x00".format(len(placeholders) - 1)

    def link(match):
        label = html.escape(match.group(1))
        return save('<a href="{}">{}</a>'.format(safe_url(match.group(2)), label))

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    for i, markup in enumerate(placeholders):
        text = text.replace("\x00{}\x00".format(i), markup)
    return text


def table_cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line):
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def render_markdown(markdown):
    lines = markdown.splitlines()
    out = []
    i = 0
    section = ""
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if re.fullmatch(r"-{3,}|\*{3,}", line):
            out.append("<hr>")
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            if level == 2:
                section = heading.group(2)
            extra = ' class="disclaimer-heading"' if section == "免责声明" and level == 2 else ""
            out.append("<h{0}{1}>{2}</h{0}>".format(level, extra, inline(heading.group(2))))
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and is_table_separator(lines[i + 1]):
            headers = table_cells(line)
            out.append('<div class="table-scroll" role="region" aria-label="研究数据表" tabindex="0"><table class="research-table"><thead><tr>')
            out.extend("<th>{}</th>".format(inline(c)) for c in headers)
            out.append("</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = table_cells(lines[i])
                if len(cells) != len(headers):
                    raise ValueError("Table cell count differs from header")
                out.append("<tr>" + "".join("<td>{}</td>".format(inline(c)) for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table></div>")
            continue
        if line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            extra = ' class="publication-signature"' if section == "最后一句" else ""
            out.append("<blockquote{}><p>{}</p></blockquote>".format(extra, inline(" ".join(quote))))
            continue
        if re.match(r"^(?:[-*+]\s+|\d+\.\s+)", line):
            ordered = bool(re.match(r"^\d+\.\s+", line))
            tag = "ol" if ordered else "ul"
            out.append("<{}>".format(tag))
            while i < len(lines) and re.match(r"^(?:[-*+]\s+|\d+\.\s+)", lines[i].strip()):
                item = re.sub(r"^(?:[-*+]\s+|\d+\.\s+)", "", lines[i].strip())
                out.append("<li>{}</li>".format(inline(item)))
                i += 1
            out.append("</{}>".format(tag))
            continue
        paragraph = []
        previous_hard_break = False
        while i < len(lines) and lines[i].strip():
            raw = lines[i]
            current = raw.strip()
            if paragraph and (current.startswith(("#", ">", "|")) or re.fullmatch(r"-{3,}", current)):
                break
            if paragraph:
                paragraph.append("<br>" if previous_hard_break else " ")
            paragraph.append(inline(current.rstrip("\\")))
            previous_hard_break = raw.endswith("  ") or raw.rstrip().endswith("\\")
            i += 1
        out.append("<p>{}</p>".format("".join(paragraph)))
    return "\n".join(out)


def render(source_path):
    source = source_path.read_text(encoding="utf-8")
    metadata, body = frontmatter(source)
    body = public_body(body)
    date = metadata["date"]
    headings = re.findall(r"^##\s+(.+)$", body, re.MULTILINE)
    if not headings or not body.startswith("# "):
        raise ValueError("Article title or sections missing")
    subtitle = headings[0]
    canonical = "https://totalresources.info/intelligence/{}.html".format(date)
    description = "{}｜{} 研究截止：{}。".format(metadata["title"], subtitle, metadata.get("research_cutoff", ""))
    rendered = TEMPLATE.read_text(encoding="utf-8")
    values = {
        "TITLE": html.escape(metadata["title"] + "｜" + subtitle),
        "DESCRIPTION": html.escape(description, quote=True),
        "CANONICAL": canonical,
        "DATE": date,
        "CUTOFF": html.escape(metadata.get("research_cutoff", "未提供")),
        "ARTICLE": render_markdown(body),
    }
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    if "{{" in rendered:
        raise ValueError("Unfilled template placeholder")
    output = ROOT / "intelligence" / (date + ".html")
    output.parent.mkdir(exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Explicit archived FINAL Markdown source")
    args = parser.parse_args()
    try:
        print(render(args.source))
    except (OSError, ValueError) as error:
        print("Publication rejected: {}".format(error), file=sys.stderr)
        sys.exit(1)

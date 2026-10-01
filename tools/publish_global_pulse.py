#!/usr/bin/env python3
"""Render one archived FINAL MCIS Global Pulse Markdown file as a static page.

Usage: python3 tools/publish_global_pulse.py /absolute/path/to/final.md
Only the article is generated. Curated index/homepage/sitemap changes remain explicit.
"""

import argparse
import html
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "tools" / "global_pulse_article.html"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
PRIVATE_TERMS = re.compile(r"MCIS|OpenClaw|Vault|Truth Layer|市场价格真值门|\bGate\b|VERIFIED|Human CIO|\bRaw\b|\bShadow\b", re.I)
INTERNAL_PROCESS_TERMS = re.compile(r"系统(?:自己)?(?:已经|已)?识别|自动包|研究包")
PUBLIC_DISCLAIMER = "免责声明：本文仅供研究与信息参考，不构成任何投资、交易或其他决策建议。"


# Bounded phrase mappings: leave unfamiliar contexts for the residual gate.
PUBLIC_LANGUAGE_RULES = (
    (r"MCIS\s*((?:[01]?\d|2[0-3]):[0-5]\d)\s*快照", r"\1市场数据快照"),
    (r"((?:今天|今日|当天))的Truth Layer应该写成", r"\1可以确认的事实状态应表述为"),
    (r"Truth Layer应该写成", "截至目前可以确认的事实状态应表述为"),
    (r"MCIS在这里一直坚持", "本研究在这里一直坚持"),
    (r"MCIS((?:今天|今日|当天)的)研究(?:包|材料)", r"\1研究材料"),
    (r"MCIS研究(?:包|材料)", "研究材料"),
    (r"MCIS自动包", "晨间研究材料"),
    (r"系统(?:自己)?(?:已经|已)识别", "资料核对已识别"),
)


def map_public_language(research):
    for pattern, replacement in PUBLIC_LANGUAGE_RULES:
        research = re.sub(pattern, replacement, research)
    return research


def frontmatter_scalar(value):
    """Normalize the small YAML scalar subset accepted by this publisher."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def public_body(markdown, research_cutoff):
    """Preserve the analysis while translating internal production labels."""
    marker = "\n## 免责声明\n"
    if markdown.count(marker) != 1:
        raise ValueError("A single disclaimer section is required")
    research, _internal_disclaimer = markdown.split(marker, 1)
    research = map_public_language(research)
    research = research.replace("写入Vault", "归档")
    research = research.replace("自动包抓到", "晨间资料记录")
    research = research.replace("研究包", "研究材料")
    research = research.replace("MCIS晨间价格快照", "晨间价格快照")
    research = research.replace("MCIS晨间快照", "晨间价格快照")
    research = research.replace("MCIS晨间包", "晨间研究材料")
    research = research.replace("MCIS判断", "研究判断")
    research = research.replace("此前MCIS一直等待", "此前研究一直等待")
    research = research.replace("MCIS采集显示", "晨间资料显示")
    research = research.replace("Truth Layer为空", "直接核验资料缺失")
    research = research.replace("更准确的Truth Layer应该拆成三层", "更准确的核验状态应该拆成三层")
    research = research.replace("精确的Truth Layer价格", "精确核验的价格")
    research = research.replace("Truth Layer已验证的官方结算", "充分核验的官方结算")
    research = research.replace("均未进入当日Truth Gate", "均未获得当日直接核验")
    research = research.replace("Truth Gate无锚", "缺少直接核验锚点")
    research = research.replace("当天市场价格真值门没有形成任何可用锚", "当天市场价格缺少足够的直接核验依据")

    published = research + marker + PUBLIC_DISCLAIMER
    if PRIVATE_TERMS.search(published) or INTERNAL_PROCESS_TERMS.search(published):
        raise ValueError("Unreviewed internal production term remains in public article")
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
    key = None
    for line in lines[1:end]:
        if line.startswith("  ") and key == "title":
            metadata[key] += " " + line.strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = frontmatter_scalar(value)
    if metadata.get("publication_status") != "FINAL":
        raise ValueError("publication_status must be FINAL")
    if metadata.get("system") != "MCIS" or metadata.get("type") != "MCIS Global Pulse":
        raise ValueError("Source must be an MCIS Global Pulse")
    date = metadata.get("date", "")
    if not DATE_RE.fullmatch(date):
        raise ValueError("Invalid or missing publication date")
    body = "\n".join(lines[end + 1:]).strip()
    market_sections = (
        "## 市场留下来的几组数字",
        "## 一、市场温度计",
        "## 一、今天市场真正发生了什么",
    )
    if not any(section in body for section in market_sections) and not re.search(r"^##\s+一、(?:今天的)?市场温度计(?:[：:]|$)", body, re.MULTILINE):
        raise ValueError("Missing required market-data section")
    for required in ("## 关于我们", "## 免责声明"):
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


def simple_table_spans(line):
    spans = [(match.start(), match.end()) for match in re.finditer(r"-{3,}", line)]
    return spans if len(spans) >= 2 else []


def simple_table_cells(line, spans):
    if "|" in line:
        cells = table_cells(line)
        if len(cells) != len(spans):
            raise ValueError("Table cell count differs from header")
        return cells
    if not spans:
        raise ValueError("Missing simple-table column boundaries")
    # Pandoc simple-table separator positions are display columns, not
    # Python character offsets: CJK characters occupy two display columns.
    cells = [""] * len(spans)
    column = 0
    cell = 0
    for char in line.expandtabs(8):
        width = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in "WF" else 1)
        while cell + 1 < len(spans) and column >= spans[cell + 1][0]:
            cell += 1
        if cell + 1 < len(spans) and column < spans[cell + 1][0] < column + width:
            raise ValueError("Table boundary splits a display character")
        cells[cell] += char
        column += width
    return [value.strip() for value in cells]


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
        if (
            re.fullmatch(r"-{6,}", line)
            and i + 2 < len(lines)
            and simple_table_spans(lines[i + 2])
        ):
            spans = simple_table_spans(lines[i + 2])
            headers = simple_table_cells(lines[i + 1], spans)
            out.append('<div class="table-scroll" role="region" aria-label="研究数据表" tabindex="0"><table class="research-table"><thead><tr>')
            out.extend("<th>{}</th>".format(inline(cell)) for cell in headers)
            out.append("</tr></thead><tbody>")
            i += 3
            while i < len(lines):
                current = lines[i]
                if re.fullmatch(r"\s*-{6,}\s*", current):
                    i += 1
                    break
                if current.strip():
                    cells = simple_table_cells(current, spans)
                    out.append("<tr>" + "".join("<td>{}</td>".format(inline(cell)) for cell in cells) + "</tr>")
                i += 1
            out.append("</tbody></table></div>")
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
                paragraph.append("\n" if previous_hard_break else " ")
            paragraph.append(current.rstrip("\\"))
            previous_hard_break = raw.endswith("  ") or raw.rstrip().endswith("\\")
            i += 1
        out.append("<p>{}</p>".format("<br>".join(inline(part) for part in "".join(paragraph).split("\n"))))
    return "\n".join(out)


def render(source_path):
    source = source_path.read_text(encoding="utf-8")
    metadata, body = frontmatter(source)
    body = public_body(body, metadata.get("research_cutoff", ""))
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

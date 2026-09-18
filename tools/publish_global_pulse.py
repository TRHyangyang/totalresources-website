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
            out.append("<h{0}>{1}</h{0}>".format(level, inline(heading.group(2))))
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and is_table_separator(lines[i + 1]):
            headers = table_cells(line)
            out.append('<div class="table-scroll"><table><thead><tr>')
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
            out.append("<blockquote><p>{}</p></blockquote>".format(inline(" ".join(quote))))
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

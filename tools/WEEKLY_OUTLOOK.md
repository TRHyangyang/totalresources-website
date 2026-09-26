# Weekly Outlook publication

Explicit human-approved FINAL Markdown is the sole content source. Archive the original bytes in the Obsidian vault at:

`02 Global Intelligence（全球情报）/Weekly Outlook（每周展望）/YYYY/MM/`

YYYY/MM comes from the publication `date`. Required YAML fields: `date: YYYY-MM-DD`, `status: FINAL` (or `publication_status: FINAL`), `title`; optional `subtitle`.

From a clean checkout of current origin/main, run:

```sh
python3 tools/publish_weekly_outlook.py '/absolute/vault/path/02 Global Intelligence（全球情报）/Weekly Outlook（每周展望）/YYYY/MM/issue_FINAL.md'
```

The command uses only that file. It renders the entire Markdown body through the existing Daily renderer, without research, editorial rewriting, disclaimer substitution, or content QA. The Weekly template retains the Daily layout and styles. Output: `weekly-outlook/YYYY-MM-DD.html`, the independent Weekly section and archive at `intelligence.html#weekly-outlook`, and a sitemap entry. Existing Daily entries are preserved. Existing output, duplicate sitemap URLs, and dates not newer than the latest Weekly issue are rejected before writing. No source discovery or scheduling is included.

Check the generated files, links and `git diff --check`. Fetch origin again and stop if origin/main changed. Stage only the publication files, commit and push normally to main; never force-push. GitHub Pages continues publishing main at repository root. Verify the article and Weekly entry after deployment.

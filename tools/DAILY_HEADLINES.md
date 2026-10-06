# Daily Headlines V1 — Phase 2

Static publishing layer; no collector, mail integration, paid service or unattended job.
Primary input: existing OpenClaw `mcis-web-intel-scan/data/YYYY/MM/web_intel_YYYY-MM-DD.json`.
Secondary input: completed current-date RSS Intelligence. The current RSS Markdown has no per-article URLs or machine completion marker: it is context only, not factual evidence. ChatGPT 07:00 Morning Brief is future enrichment.

## Review contract

1. Run `publish_daily_headlines.py --date YYYY-MM-DD --scan <current JSON> --history-dir <existing Scan data root> --rss <optional daily Markdown> --report-dir <private audit directory>`.
2. Review `candidates.json`. Importance S/A never grants eligibility. Empty, truncated, title-only, relative/unknown-time records are rejected. Relevance scoring is a conservative rule-based shortlist, not a replacement for editorial judgment.
3. Supply a private editorial JSON tied to `scan_sha256`: every eligible event gets a SELECT/REJECT reason; selected events include evidence indices, exact source quotes mapped to Chinese facts, separate analysis, category relevance and material novelty. Any prior topic/URL/title match needs an explicit comparison and new evidence quote. Historic date JSON is the published event memory; prior Scan files add pre-launch memory. Do not publish raw Scan, internal audit files or input paths.
4. Run again with `--editorial <reviewed JSON> --verify-urls --preview-dir <new directory outside repository>`. This generates a complete local static preview only. No git writes, no deployment, no same-date overwrite. URL checks are GET requests to already supplied source URLs; no article discovery or new factual inputs.
5. Run tests, browser checks at desktop and 390px, and inspect screenshots. Verify all existing article hashes, hero, Global Pulse section and `global-pulse.js` remain identical. Review source names, dates, numbers and semantic translation. Automatic token and quote checks cannot prove semantic truth; recorded editorial review is mandatory.
6. Human CIO accepts content and page effects before Phase 3. No unattended cron exists. Current GitHub Pages is legacy `main` `/`: it has no native feature-branch preview. Local HTTP preview is the Phase 2 test deployment; any main merge/deployment needs the accepted content and completed QA.

## Public data

`schema_version=1`, `date`, `timezone=Asia/Shanghai`, `generated_at`, `status=PUBLISHED|NO_MATERIAL_CHANGE`, `headlines`.
Each headline: `event_id`, `date`, `time` (source publication month/day/time in CST), `headline_cn`, `headline_en`, `summary`, `category`, `source_name`, `source_url`, `source_publish_time`, `sources`, `confidence`, `mcis_relevance`, `rank`, `material_new_information`.
All sources are retained. PARTIAL means a source-attributed report, not an independent confirmation. CONFIRMED requires multiple independent evidence domains plus editorial verification; domains alone do not establish independence.

Date JSON and date HTML are immutable archives. `latest.json` mirrors the latest successful daily result. On the homepage and column index, stale/missing/failed/malformed data shows PENDING and zero cards; a real completed no-change assessment shows NO_MATERIAL_CHANGE. Pending is a display state, never an archived successful production. Open tabs recheck every minute and on visibility change. The homepage displays at most the first three ranked events; date pages display all (maximum five).

## Safety boundaries

No public output is produced if evidence, source URLs, snapshots or archive checks fail. A timestamped QA FAIL receipt is retained. A completed no-change result additionally requires a coverage assessment and no unresolved high-priority evidence gaps. Existing production remains untouched. Do not refresh an old event merely because a feed updated its timestamp. Comparison and editorial judgment are necessary for substantive novelty.

Before a later accepted deployment, refresh origin/main, stop on remote changes or dirty state, stage only reviewed files, use normal commit/push, and verify GitHub Pages plus prior articles. Coordinate with other publishers; never auto-merge, rebase or force-push.

Tests: `python3 tools/test_publish_daily_headlines.py` (synthetic TEST fixtures only; no network).

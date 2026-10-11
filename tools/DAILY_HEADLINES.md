# Daily Headlines V1 — Production

Static publishing layer with bounded recovery from existing candidate URLs; no independent collector, mail integration or paid service. The approved daily schedule is 07:10 Asia/Shanghai, dispatched through the existing OpenClaw scheduler.
Primary input: existing OpenClaw `mcis-web-intel-scan/data/YYYY/MM/web_intel_YYYY-MM-DD.json`.
Secondary input: completed current-date RSS Intelligence. The current RSS Markdown has no per-article URLs or machine completion marker: it is context only, not factual evidence. ChatGPT 07:00 Morning Brief is future enrichment.

## Review contract

1. Run `publish_daily_headlines.py --date YYYY-MM-DD --scan <current JSON> --history-dir <existing Scan data root> --rss <optional daily Markdown> --report-dir <private audit directory>`.
2. Review `candidates.json`. Importance S/A never grants eligibility. Empty, truncated, title-only, relative/unknown-time records remain rejected unless a bound original-URL snapshot supplies complete visible article evidence and a reliable absolute publication time. Relevance scoring is a conservative rule-based shortlist, not a replacement for editorial judgment.
3. Supply a private editorial JSON tied to `scan_sha256`: every eligible event gets a SELECT/REJECT reason; selected events include evidence indices, exact source quotes mapped to Chinese facts, separate analysis, category relevance and material novelty. Any prior topic/URL/title match needs an explicit comparison and new evidence quote. Historic date JSON is the published event memory; prior Scan files add pre-launch memory. Do not publish raw Scan, internal audit files or input paths.
4. Run again with `--editorial <reviewed JSON> --verify-urls --preview-dir <new directory outside repository>`. This generates a complete local static preview only. No git writes, no deployment, no same-date overwrite. Publication URL checks are GET requests to supplied source URLs. Optional evidence recovery is a separate bounded step within the same prepare call; it never discovers new articles or sources.
5. Run tests, browser checks at desktop and 390px, and inspect screenshots. Verify all existing article hashes, hero, Global Pulse section and `global-pulse.js` remain identical. Review source names, dates, numbers and semantic translation. Automatic token and quote checks cannot prove semantic truth; recorded editorial review is mandatory.
6. Human CIO approved production deployment and unattended daily publishing. The private Vault runtime performs preview QA, safe promotion, exact dated commit, ordinary push, Pages propagation and live desktop/390px checks. It keeps immutable successful-publication receipts, same-day leases and exact interrupted-deployment resume state. Current GitHub Pages remains legacy `main` `/`.

## Public data

`schema_version=1`, `date`, `timezone=Asia/Shanghai`, `generated_at`, `status=PUBLISHED|NO_MATERIAL_CHANGE`, `headlines`.
Each headline: `event_id`, `date`, `time` (source publication month/day/time in CST), `headline_cn`, `headline_en`, `summary`, `category`, `source_name`, `source_url`, `source_publish_time`, `sources`, `confidence`, `mcis_relevance`, `rank`, `material_new_information`.
All sources are retained. PARTIAL means a source-attributed report, not an independent confirmation. CONFIRMED requires multiple independent evidence domains plus editorial verification; domains alone do not establish independence.

Date JSON and date HTML are immutable archives. `latest.json` mirrors the latest successful daily result. On the homepage and column index, stale/missing/malformed data without a current completed review failure shows PENDING and zero cards; a real completed no-change assessment shows NO_MATERIAL_CHANGE. Pending is a display state, never an archived successful production. Open tabs recheck every minute and on visibility change. The homepage displays at most the first three ranked events; date pages display all (maximum five).

## Safety boundaries

No article or successful-content output is produced if evidence, source URLs, snapshots or archive checks fail. A timestamped QA FAIL receipt is retained. A completed no-change result additionally requires a coverage assessment and no unresolved high-priority evidence gaps. Existing production remains untouched. Do not refresh an old event merely because a feed updated its timestamp. Comparison and editorial judgment are necessary for substantive novelty.

Before a later accepted deployment, refresh origin/main, stop on remote changes or dirty state, stage only reviewed files, use normal commit/push, and verify GitHub Pages plus prior articles. Coordinate with other publishers; never auto-merge, rebase or force-push.

Tests: `python3 tools/test_publish_daily_headlines.py` (synthetic TEST fixtures only; no network).

## Production editorial extensions

MCIS categories are ranking priors, not quotas. Credible single-source factual reports are allowed with PARTIAL. No source is rejected solely for being single-source; source credibility and materiality still require editorial review. CONFIRMED additionally requires explicitly verified independence, not simply two domains. The default lexical rank is provisional: `relevance_override_reason` plus `category_override` may correct a below-threshold/out-of-scope suggestion, but can never override empty/truncated/unverified evidence.

Optional `clusters` (`event_id`, `item_indices`, `rationale`) merge semantically duplicate records before final decisions. The identity must preserve an existing input or published event ID; new IDs cannot be invented daily to evade history. Every published claim retains a literal quote and a source index. Previously published events require substantive new evidence and an explicit comparison; continuation alone is insufficient.

The private production runtime is under the existing Vault automation area, outside this public website repository. Inputs, editorial packets, runtime config, credentials, receipts and screenshots must never be committed to the website. The existing wake-recovery service supports current-day catch-up and bounded network/input retries. Its success check requires a verified production receipt, not merely an agent run returning OK.

## Review outcome display

The existing 07:10 runtime publishes `data/daily-headlines/status.json` after a completed QA FAIL, using `public_status(receipt)` to expose only schema version, date, timezone, NO_VERIFIED_UPDATE and completion time. Internal errors, paths and candidate data remain private. A status-only commit never modifies latest.json, dated articles, the sitemap or accepted publication receipts. It uses the same clean-main, unchanged-remote and ordinary-push checks; failures are recorded separately as status_publication_error/status_deployment_result.

Both current-date readers show `No Verified Update｜今日暂无符合发布标准的更新` for this outcome, explicitly stating that review failure does not mean no major news occurred. A verified current-day article always takes precedence; a previous-day outcome is ignored. Pending and failed-review buttons link to `#archive`. No new schedule or news source is added.

HTML-to-text conversion preserves paragraph and list boundaries. Truncated or missing upstream summaries and unverified timestamps remain ineligible. This does not reconstruct missing evidence or relax editorial gates.

## Bounded original-URL evidence recovery

`daily_headlines_evidence.py` is an optional helper within the existing private runtime, not a second collector or scheduled job. The existing prepare command enables it with `--recover-evidence`. The default prepare invocation remains compatible with the previous scheduled prompt; no network recovery is enabled by changing the local prompt template alone. Operators must update only the existing job's message to the revised private prompt to activate it. Keep the 06:00/07:10 schedules, ten sources, model settings and all publication QA unchanged.

Recovery ranks existing high-value evidence gaps by research priority, score, evidence readiness and recency. It skips non-news, out-of-window articles, duplicate URLs/events and low-relevance records. It has no source quota or Semafor preference. Private calendar-day reservations cap recovery at five original URLs and 180 seconds across retries, with a 30-second hard subprocess timeout per article. Failed attempts consume a slot; crashes consume their reserved time. Redirects must stay at the same existing source and article identity. No credentials, paywall workarounds, inferred timezone or relative-time reconstruction are used.

The complete accessible HTML and extracted visible evidence stay in private files. A completed manifest records original URL, item index, source, absolute publication time, retrieval time, extraction method and hashes. The original Scan and its summary remain unchanged. `evidence_text` is distinct from the public 50–120-Chinese-character editorial summary. Publishing rechecks the frozen manifest hash; the editorial packet must acknowledge `evidence_sha256`. Recovered evidence still needs fact/quote mapping, novelty, source independence, URL checks and all existing publication QA.

The helper also accepts complete upstream `evidence_text` without a second fetch. A 400-character legacy summary is conservatively marked truncated even if it happens to end in punctuation. Coupon/promo pages, shopping guides and market tools are rejected; whole-word energy matching prevents `conflict-fueled` from becoming an energy keyword.

Historical validation manifests are `HISTORICAL_TEST`: they can be inspected offline but cannot enter production overlay or editorial validation. Current page retrieval for an old URL is not evidence of what that page contained at the historical cutoff. Never publish historical test output as today's news.

The upstream OpenClaw collector was unavailable during this change. Its 400-character truncation has NOT been fixed here. On that host, retain the full feed/article text before any display-length slicing, save it as private `evidence_text`, retain original URL and absolute timestamp provenance, and keep the short display `summary` separate. No missing body or timestamp may be fabricated.

Tests: `python3 tools/test_daily_headlines_evidence.py` and the existing publishing safety tests. Historical network results are private and must not be committed to this public repository.

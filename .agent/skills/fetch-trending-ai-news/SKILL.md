---
name: fetch-trending-ai-news
description: Curates 3-4 top trending AI news stories of the day by running targeted queries for distinct founder segments against the Hacker News Algolia API and Google News RSS, pre-filtering low-signal/evergreen noise, classifying real industry event types, and ranking by segment relevance.
---

# Fetch Trending AI News (`fetch-trending-ai-news`)

## 1. Overview & Strategy

This skill handles Step 1 of the Content Repurposer pipeline. Its role is to discover genuine, high-signal industry events from the trailing 24 hours and map each event to a specific founder persona.

> [!IMPORTANT]
> **Anti-Hallucination Mandate:**
> You must not answer from prior/training knowledge. Every fact, quote, and detail must come from a page you actually fetched during this run. If you cannot successfully fetch a page, report `fetch_status: failed` — do not fill in plausible-sounding details instead.

### Core Philosophy: Genuine Industry Events Over Evergreen Listicles
Founders cannot build an engaging personal brand or thought leadership around generic "Top 10 Tools" or "How to use ChatGPT" guides. They need real, consequential events—product releases, funding rounds, strategic pivots, architecture shifts, and major partnerships—that directly affect their roadmap, tech stack, or market positioning.

---

## 2. Strict Pipeline Flow (6-Stage with Post-Routing Validation)

```
[1. Pre-filter & Freshness]
  └── Reject stale (>48h), evergreen guides, negative drama / controversy / lawsuit content
          │
[2. Fix 1: Multi-topic Digest / Roundup Filter]
  └── Detect weekly digests, trailing 'and more', non-tech bundles. Re-source dedicated coverage or filter out.
          │
[3. Fix 3: Event-Type Gate (Pass 1 Hard Filter)]
  └── Classify and immediately hard-reject anything not in ELIGIBLE_EVENT_TYPES (no soft tagging).
          │
[4. Fix 2: Audience-Fit / Segment-Relevance Check]
  └── Compare against canonical segment profiles. Re-route cross-segment matches; filter mismatches.
          │
[5. Fix 3: Event-Type Gate (Pass 2 Post-Routing)]
  └── Re-validate re-routed candidates against ELIGIBLE_EVENT_TYPES before destination pool scoring.
          │
[6. Scoring, Deduplication & Pre-Publish Assertion]
  └── Score by event eligibility + segment relevance + recency tiebreaker. Exclude 14-day history repeats.
      Hard invariant assertion before winner lock-in.
```

---

## 3. Pre-Filter & Freshness Gate (Hard Reject Before Scoring)

Candidates are filtered immediately upon ingestion. Matching candidates are dropped from the evaluation pool and recorded in `filtered_out`:

### A. Stale Content Gate (`stale_exceeds_48h`)
* Reject any candidate whose `published_at` timestamp is more than **48 hours** old.
* Prevents resurfacing old announcements or historical training data.

### B. Evergreen / Guide Content (`evergreen_pattern_match`)
* `N best/top X` (e.g. "7 Best...", "Top 10...", "5 essential...")
* `how to`, `guide to`, `tips for`, `ways to`
* `explained`, `what is`, `everything you need to know`
* Generic `vs` / comparison roundups not tied to a specific launch event
* Tutorials, cheat sheets, and product reviews

### C. Negative / Legal / Drama Content (`legal_or_controversy`)
* Lawsuits, legal disputes, litigation, copyright infringement
* Layoffs framed as scandal or corporate decline
* General controversy, outrage, or drama
* Company shutdowns, bankruptcies, collapses, or flops

---

## 4. Fix 1: Multi-Topic Digest & Roundup Filter

Weekly roundups and multi-topic digests bundle unrelated stories under a single URL (e.g. tech mixed with geopolitics). 

### Detection Rules:
1. **Date-Range Pattern:** Matches date spans in title or URL slug (e.g. `Aug 31-Sep 4`, `Week of Sept 1`, `weekly roundup`, `daily digest`).
2. **Trailing Catch-Alls:** Matches `, more`, `and more`, `- more`, `... and more` at the end of the headline.
3. **Multiple Unrelated Topics:** Mentions non-tech/geopolitical figures or topics (e.g. `Trump`, `Hormuz`, `election`, `tariffs`) alongside tech stories.
4. **Compound Hyphenated Slugs:** URL slugs with 8+ dashes containing unrelated keywords or date markers.

### Re-sourcing Mechanism:
* Extracts the core AI sub-topic (e.g. "NVIDIA buys open AI developer").
* Searches Google News RSS and HN Algolia for single-topic dedicated coverage within the trailing 48 hours.
* **If found:** Replaces candidate URL with dedicated article, sets `digest_format: true`, and records `resolved_from_digest: {"original_url": ..., "replacement_url": ...}`.
* **If not found:** Drops candidate from the pool and logs `filtered_out` with `reason: "digest_only_no_dedicated_source"`.

---

## 5. Event-Type Gate Re-Enforcement (Fix 3: Hard Filter & Pass 2 Post-Routing)

The Event-Type Gate enforces a **hard reject**, never a soft tag. Any candidate not matching one of the six eligible types is dropped immediately.

### Eligible Event Types (Only these can win under any circumstances):

| Event Type | Scope & Definition |
| :--- | :--- |
| `funding_round` | Capital raises, seed/Series rounds, valuations tied to new capital deployment. |
| `acquisition` | M&A transactions, strategic buyouts, corporate acquisitions. |
| `product_launch` | New product, model release, major feature, or framework shipping from a company/lab. |
| `strategic_pivot` | Company changing business model, market focus, or fundamental platform direction. |
| `partnership` | Strategic integrations, joint commercial deployments, infrastructure alliances. |
| `research_breakthrough` | New foundation model, benchmark breakthrough, or novel architecture shipped by a lab. |

### Ineligible Event Types:
* `other` (general commentary, op-eds, macro reports) $\rightarrow$ **strictly ineligible, never permitted to win**
* `controversy` (criticism, backlash, disputes)
* `notable_failure` (shutdowns, failed initiatives)
* `regulatory_move` (probes, antitrust, regulatory bans)

### Re-Enforcement Rules:
1. **Pass 1 Hard Filter:** Native candidates classified as non-eligible are rejected immediately with `filtered_out: {"reason": "event_type_ineligible"}`.
2. **Pass 2 Post-Routing Gate:** When Fix 2 redirects a candidate to a new segment pool, that candidate must re-clear the event-type gate before scoring. If it fails, it is dropped with `filtered_out: {"reason": "event_type_ineligible_post_routing"}`.
3. **Pre-Publish Safety Invariant:** Before any segment winner is locked in, `assert winner.event_type in ELIGIBLE_EVENT_TYPES`. Failure triggers `filtered_out: {"reason": "event_type_ineligible_final_check"}` and falls through.
4. **Audit Field:** Every candidate tracks `event_type_gate_passes: [1]` (or `[1, 2]` if re-routed).
5. **No `other` Fallback:** If a segment has zero eligible candidates in the trailing 24 hours, the segment is cleanly reported under `skipped_segments` rather than selecting an `other` story.

---

## 6. Fix 2: Audience-Fit Gate & Cross-Segment Routing

Prevents tagging deep-infrastructure stories under consumer software or vice-versa.

### Canonical Target Profiles:
* **Deep Tech (`deep_tech`):** Foundation models, GPU compute, clusters, datacenters, kernels, weights, silicon, inference latency, infrastructure M&A.
* **SaaS B2B (`saas_b2b`):** Enterprise software, business workflows, corporate automation, RAG for private enterprise data, compliance, security.
* **SaaS D2C (`saas_d2c`):** Consumer apps, creator tools, photo/video/audio editors, mobile micro-apps, consumer subscriptions.
* **AI-native / Consumer Tech (`ai_native_consumer`):** Autonomous AI agents, multimodal interaction, voice agents, interactive AI systems, consumer AI hardware.

### Re-Routing & Mismatch Handling:
* Evaluates `best_fit_segment` and checks if `best_fit_segment == segment_id` (`segment_match`).
* If `segment_match == false`:
  - Logs `filtered_out` in current segment: `{"title": ..., "reason": "segment_mismatch", "redirected_to": "<best_fit_segment>"}`.
  - Re-routes the candidate to the candidate pool of `<best_fit_segment>` to compete fairly under that segment's profile.

---

## 7. Ranking Precedence Logic & Repeat Prevention

1. **Event-Type Gate:** Candidate must be one of the 6 eligible event types (enforced hard in Step 3 and Step 5).
2. **Segment Relevance:** Measures how directly the story engages the specific founder profile.
   $$\text{Score} = 100.0 + (\text{segment\_relevance\_score} \times 10.0) + \text{recency\_tiebreaker} + \text{community\_bonus}$$
3. **Recency Tiebreaker:** Normalized between `0.0` and `1.0` based on age within 24h.
4. **Story History Tracking (Repeat Prevention):**
   - Checks `data/used_stories_log.json` for winning story URLs from the trailing **14 days**.
   - Excludes any repeat candidates and logs them in `duplicate_check.excluded_as_repeat`.

---

## 8. Google News Redirect Resolution

Google News RSS URLs (`news.google.com/rss/articles/...`) are decoded via `batchexecute` into genuine publisher article URLs.
* Sets `"url"` to the genuine article destination.
* Preserves `"google_news_redirect_url"` for auditability.
* Sets `"url_resolved": true` (or `false` if resolution failed).

---

## 9. Output Contract

```json
{
  "fetched_at": "2026-09-07T06:15:00Z",
  "sources_queried": ["hn_algolia", "google_news_rss"],
  "counts_returned": {
    "hn_algolia": 4,
    "google_news_rss": 14
  },
  "total_selected": 1,
  "stories": [
    {
      "segment_id": "deep_tech",
      "segment_name": "Deep Tech",
      "target_profile": "Founders building foundation models, AI infrastructure, custom architectures, GPU compute...",
      "counts_returned": {
        "hn_algolia": 0,
        "google_news_rss": 14
      },
      "filtered_out": [
        {
          "title": "7 Best Open-Source AI Tools You Can Run Locally in 2026 - Analytics Insight",
          "reason": "evergreen_pattern_match"
        },
        {
          "title": "Consumer Tech (Aug 31-Sep 4): NVIDIA Buys World's Largest...",
          "reason": "digest_only_no_dedicated_source"
        },
        {
          "title": "Magna AI and MBUZZ partner to deliver enterprise AI infrastructure",
          "reason": "segment_mismatch",
          "redirected_to": "SaaS (B2B)"
        }
      ],
      "fallback_used": false,
      "duplicate_check": {
        "excluded_as_repeat": [],
        "history_window_days": 14
      },
      "candidates": [
        {
          "source": "google_news_rss",
          "title": "NVIDIA Acquires Hugging Face for $13 Billion",
          "url": "https://news.google.com/rss/articles/...",
          "url_resolved": false,
          "google_news_redirect_url": "https://news.google.com/rss/articles/...",
          "published_at": "Mon, 07 Sep 2026 05:18:53 GMT",
          "event_type": "acquisition",
          "event_type_gate_passes": [1],
          "digest_format": false,
          "resolved_from_digest": null,
          "best_fit_segment": "Deep Tech",
          "segment_match": true,
          "segment_relevance_score": 6.0,
          "score": 160.62,
          "fallback_used": false,
          "score_components": {
            "source": "google_news_rss",
            "event_type": "acquisition",
            "is_eligible_event": true,
            "segment_relevance_score": 6.0,
            "recency_tiebreaker": 0.619,
            "hn_bonus": 0.0,
            "formula_used": "100.0 (if eligible) + (segment_relevance * 10.0) + recency_tiebreaker + hn_bonus"
          },
          "snippet": "NVIDIA Acquires Hugging Face..."
        }
      ],
      "story": {
        "source": "google_news_rss",
        "title": "NVIDIA Acquires Hugging Face for $13 Billion",
        "url": "https://www.indexbox.io/blog/nvidia-acquires-hugging-face-for-13-billion/",
        "url_resolved": true,
        "google_news_redirect_url": "https://news.google.com/rss/articles/...",
        "published_at": "Mon, 07 Sep 2026 05:18:53 GMT",
        "event_type": "acquisition",
        "event_type_gate_passes": [1],
        "digest_format": false,
        "resolved_from_digest": null,
        "best_fit_segment": "Deep Tech",
        "segment_match": true,
        "segment_relevance_score": 6.0,
        "score": 160.62,
        "fallback_used": false,
        "score_components": {
          "source": "google_news_rss",
          "event_type": "acquisition",
          "is_eligible_event": true,
          "segment_relevance_score": 6.0,
          "recency_tiebreaker": 0.619,
          "hn_bonus": 0.0,
          "formula_used": "100.0 (if eligible) + (segment_relevance * 10.0) + recency_tiebreaker + hn_bonus"
        },
        "snippet": "NVIDIA Acquires Hugging Face..."
      }
    }
  ],
  "skipped_segments": []
}
```

---

## 10. CLI Execution Reference

```bash
# Run for all segments:
python .agent/skills/fetch-trending-ai-news/scripts/fetch_news.py

# Run for a specific segment:
python .agent/skills/fetch-trending-ai-news/scripts/fetch_news.py --segment "Deep Tech"
```

---
name: extract-insights
description: Extracts central facts, notable quotes, and surprising founder angles from verified news article URLs, enforcing strict publication date freshness checks and zero-hallucination constraints.
---

# Extract Insights (`extract-insights`)

## 1. Overview & Strategy

This skill handles Step 2 of the autonomous Content Repurposer pipeline. It sits between `fetch-trending-ai-news` (story sourcing) and `apply-post-pattern` (blueprint selection).

Its responsibility is to perform an authentic, live fetch of the winning article URL, distill signal from noise, extract verified facts and quotes, and uncover the most counter-intuitive or consequential angle for the target founder segment.

> [!IMPORTANT]
> **Anti-Hallucination Mandate:**
> You must not answer from prior/training knowledge. Every fact, quote, and detail must come from a page you actually fetched during this run. If you cannot successfully fetch a page, report `fetch_status: failed` — do not fill in plausible-sounding details instead.

---

## 2. Freshness Verification Protocol

To prevent answering from outdated articles or silent stale resurfacing, this skill verifies that the publication date on the fetched page matches what `fetch-trending-ai-news` reported.

### `freshness_flag` Values:

| Flag | Meaning | Action Taken |
| :--- | :--- | :--- |
| `verified_fresh` | The publish date found on the page matches the reported date (within 48 hours). | Proceed with pipeline. |
| `date_mismatch` | The article's actual publish date (visible on page) does not match what was reported. | Flagged in output: includes both `reported_date` and `actual_date_on_page` for auditing. |
| `no_date_found` | No extractable timestamp could be found in page metadata or text. | Flagged as `no_date_found` (indicates page layout anomaly or dynamic wall). |

---

## 3. Extraction Requirements

For each winning story, the skill must extract:
1. **`fetch_status`:**
   * `"success"`: Full article body retrieved and parsed.
   * `"blocked"`: Blocked by paywall, Cloudflare, CAPTCHA, or JS hydration wall.
   * `"failed"`: HTTP 404/500, DNS resolution failure, or connection timeout.
2. **`key_facts`:** 3 to 5 concrete, verifiable details (numbers, names, specs, dates, funding amounts) directly from the page text.
3. **`notable_quote`:** A direct quote with attributed speaker (or `null` if no quote exists—never fabricate quotes).
4. **`surprising_angle`:** The single most interesting, non-obvious angle for that founder segment.

---

## 4. Output Contract

```json
{
  "segment": "Deep Tech",
  "source_url": "https://www.chosun.com/english/industry-en/2026/09/06/QYUPBDLY45CLJM3QV436YJ5KEI/",
  "fetch_status": "success",
  "freshness_flag": "verified_fresh",
  "reported_date": "2026-09-06",
  "actual_date_on_page": "2026-09-06",
  "key_facts": [
    "LG Uplus unveiled Power Cube, a standardized modular AI data center model.",
    "Cuts facility construction time from standard 2–3 years down to 10–12 months (over 50% faster).",
    "Modular architecture supports scaling up to 100MW with containerized liquid cooling."
  ],
  "notable_quote": null,
  "surprising_angle": "AI infrastructure bottlenecks are usually discussed as GPU allocation or power grid contracts; physical civil engineering and 3-year building construction latency is being turned into a prefabricated modular hardware appliance."
}
```

---

## 5. Execution Reference

Run programmatic extraction:
```bash
python .agent/skills/extract-insights/scripts/extract_insights.py --url "<url>" --segment "<segment>" --reported-date "YYYY-MM-DD"
```

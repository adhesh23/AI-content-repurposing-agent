---
name: store-and-publish
description: Formats, validates, persists local backups, and delivers daily LinkedIn posts to an n8n webhook endpoint using an exact JSON contract keyed by founder segment.
---

# Store and Publish (`store-and-publish`)

## 1. Overview & Dual Mode Operation

This skill is the final step (Step 5) of the autonomous Content Repurposer pipeline. 

It formats, validates, persists local backups, and delivers LinkedIn posts to a configurable webhook endpoint (such as an n8n or Make workflow). It operates in two distinct modes:

1. **`single_segment` mode (Isolated Runs & Testing):**
   * Invoked with a single segment's post data.
   * Immediately POSTs that single post to the webhook.
   * Saves an individual backup file: `output/{date}_{segment_slug}.json`.
   * Used for manual testing, single-post regenerations, and isolated debugging.

2. **`daily_batch` mode (Scheduled Production Pipeline):**
   * Invoked after all 4 segments have completed `shape-narrative`.
   * Combines all 4 posts into a single consolidated payload containing a `posts` array.
   * Sends **one** combined webhook POST to downstream automations (e.g. Make / n8n).
   * Saves **one** combined local backup file: `output/{date}_all_segments.json`.

---

## 2. JSON Payload Schemas

### A. `single_segment` Mode Schema:
```json
{
  "date": "YYYY-MM-DD",
  "segment": "SaaS (B2B)",
  "source_title": "vLLM introduces unified KV-cache memory manager",
  "source_url": "https://news.ycombinator.com/item?id=12345678",
  "pattern_used": "The Roadmap & ROI Teardown",
  "post_text": "If your team is budgeting two quarters of engineering to build a custom RAG cache, stop.\n\nYesterday's unified memory release dropped self-hosted LLM cache fragmentation by 40%.\n\nThat's a direct 30% reduction on your monthly cloud GPU bill.\n\nAre you planning to build caching in-house, or take the open-source win?",
  "hook": "If your team is budgeting two quarters of engineering to build a custom RAG cache, stop."
}
```

### B. `daily_batch` Mode Schema:
```json
{
  "date": "2026-09-06",
  "posts": [
    {
      "date": "2026-09-06",
      "segment": "Deep Tech",
      "hook": "I used to think securing GPU clusters...",
      "post_text": "I used to think securing GPU clusters...",
      "source_title": "LG Uplus Unveils Modular AI Data Center Model...",
      "source_url": "https://www.chosun.com/...",
      "pattern_used": "Vulnerability/pain confession + Declarative/stakes close"
    },
    {
      "date": "2026-09-06",
      "segment": "SaaS (B2B)",
      "hook": "If your B2B go-to-market strategy...",
      "post_text": "If your B2B go-to-market strategy...",
      "source_title": "SEOPulse Announced the Launch...",
      "source_url": "https://www.martechcube.com/...",
      "pattern_used": "Contrarian claim + Declarative/stakes close"
    },
    {
      "date": "2026-09-06",
      "segment": "SaaS (D2C)",
      "hook": "The open-source AI ecosystem's neutral Switzerland is gone...",
      "post_text": "The open-source AI ecosystem's neutral Switzerland is gone...",
      "source_title": "Consumer Tech: NVIDIA Buys Hugging Face for $12.93B",
      "source_url": "https://www.benzinga.com/...",
      "pattern_used": "Stakes-opener + Declarative/stakes close"
    },
    {
      "date": "2026-09-06",
      "segment": "AI-native / Consumer Tech",
      "hook": "Aslan just closed a $20.8M Series A for autonomous AI agents...",
      "post_text": "Aslan just closed a $20.8M Series A for autonomous AI agents...",
      "source_title": "Aslan Raises $20.8M for Undercover AI Agents...",
      "source_url": "https://quasa.io/...",
      "pattern_used": "Subvert-the-expected + Declarative/stakes close"
    }
  ]
}
```

### Field Definitions:

| Field | Type | Description & Constraints |
| :--- | :--- | :--- |
| `date` | `string` | ISO date format: `YYYY-MM-DD` (UTC generation date). |
| `segment` | `string` | **Strict enum.** Must be one of the four fixed segment values (see Section 3). |
| `source_title` | `string` | Headline of the original news story or breakthrough. |
| `source_url` | `string` | Direct URL to the primary news source or community discussion. |
| `pattern_used` | `string` | Full name or composite of the narrative blueprint from `apply-post-pattern`. |
| `post_text` | `string` | 100% complete, publish-ready LinkedIn copy with native line breaks. |
| `hook` | `string` | The single opening sentence of `post_text` before line breaks. |
| `posts` | `array` | List of post objects in `daily_batch` mode matching the schema above. |

---

## 3. The Four Fixed Segment Values

The `segment` field is the primary discriminator used by downstream n8n switch nodes to route, label, schedule, or distribute posts to specific audience buckets or founder accounts.

The value of `segment` must strictly be one of these **four exact string literals**:

1. `"SaaS (B2B)"`
2. `"SaaS (D2C)"`
3. `"Deep Tech"`
4. `"AI-native / Consumer Tech"`

> [!WARNING]
> Do not use alternate variations (such as `"B2B SaaS"`, `"Consumer"`, or `"DeepTech"`). Any deviations will fail n8n conditional routing filters.

---

## 4. Configuration & Webhook Delivery

Webhook endpoints must **never be hardcoded** in scripts or codebase files.

### Configuration Methods:
1. **Environment Variable (Recommended for Production):**
   Set `PUBLISH_WEBHOOK_URL`:
   ```bash
   export PUBLISH_WEBHOOK_URL="https://n8n.yourdomain.com/webhook/linkedin-ai-posts"
   ```
2. **Config File (`resources/publish_config.json`):**
   ```json
   {
     "webhook_url": "https://n8n.yourdomain.com/webhook/linkedin-ai-posts",
     "timeout_seconds": 15,
     "retry_attempts": 3,
     "local_output_dir": "output"
   }
   ```

### HTTP Delivery Spec:
* **Method:** `POST`
* **Headers:**
  * `Content-Type: application/json`
  * `User-Agent: AutonomousContentRepurposer/1.0`
* **Body:** Serialized JSON payload matching Section 2.

---

## 5. Local Backup & Resilience Protocol

Network timeouts, webhook rate limits, or downstream downtime must never cause data loss:

1. **Unconditional Local Persistence:**
   Before any HTTP network request is attempted, the payload is written directly to the repository root directory `output/`:
   * **Single segment mode:**
     ```
     output/YYYY-MM-DD_<segment_slug>.json
     ```
     *Example:* `output/2026-09-06_saas_b2b.json`
   * **Daily batch mode:**
     ```
     output/YYYY-MM-DD_all_segments.json
     ```
     *Example:* `output/2026-09-06_all_segments.json`

2. **Graceful Degradation:**
   If the webhook call fails (HTTP 4xx, 5xx, or network timeout), the execution logs a clear warning but succeeds in persisting the backup. Operators can replay failed deliveries directly from the `output/` directory.

---

## 6. Execution Reference

Use `scripts/publish_post.py` to test or execute publication:

```bash
# Run test or programmatic delivery:
python .agent/skills/store-and-publish/scripts/publish_post.py
```

When called within `.agent/workflows/daily-ai-brief.md`, the pipeline invokes `store_and_publish_post` with the outputs from preceding skills for each of the day's selected founder stories.

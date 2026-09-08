# Architecture & System Design

The **Autonomous AI Content Repurposer Agent** transforms trending daily AI shifts and developments into authentic, publish-ready LinkedIn posts tailored to founders across 4 distinct niches: **Deep Tech**, **SaaS (B2B)**, **SaaS (D2C)**, and **AI-native / Consumer Tech**.

---

## 1. End-to-End Pipeline Workflow

```mermaid
flowchart TD
    A[Start: Daily Trigger] --> B{Daily Cache Exists?}
    B -- Yes & not --force-refresh --> C[Load Cached Payload]
    C --> D[Step 5: Publish to Make Webhook]
    B -- No / --force-refresh --> E[Step 1: Fetch Trending News]
    
    E -->|Algolia API & Google RSS| F[Filter Noise & Deduplicate Fingerprints]
    F --> G[Step 2: Extract Insights & Check Freshness]
    G --> H[Step 3: Select Post Pattern & Blueprint]
    H --> I[Step 4: Generate Narrative via OpenRouter]
    I --> J[Harden & Clean Post / Strip Reasoning]
    J --> K[Save to data/daily_cache/YYYY-MM-DD.json]
    K --> D
    D --> L[Local Backup & Webhook Delivery]
```

---

## 2. The 5 Pipeline Steps

### Step 1: Source (`fetch-trending-ai-news`)
* **Sources:** Hacker News (Algolia Search API) and Google News RSS.
* **Deterministic Filtering:** Removes evergreen tutorials, listicles, corporate fluff, and legal controversies.
* **Story-Identity Deduplication:** Computes a normalized keyword-stemmed title fingerprint for every candidate and compares it against the 14-day history in `data/used_stories_log.json`. Catches cross-outlet duplicates (e.g., Benzinga vs. IndexBox covering the same acquisition) using Jaccard similarity ($\ge 0.50$).

### Step 2: Extract (`extract-insights`)
* **Core Logic:** Pulls article text, verifies published date freshness ($< 48$ hours), and distills factual signal vs. noise.
* **Anti-Hallucination Mandate:** The model is constrained to extract *only* verified facts, metrics, and architecture points present in the source article text.

### Step 3: Pattern Check (`apply-post-pattern`)
* **Curated Frameworks:** Matches event types (acquisitions, product launches, benchmark milestones, regulatory shifts) and target founder segments to high-converting post blueprints (e.g. *Contrarian claim*, *Vulnerability/pain confession*, *The Roadmap & ROI teardown*).

### Step 4: Narrative Crafting (`shape-narrative`)
* **Copywriting Standards:** Produces complete, publish-ready LinkedIn posts without placeholders or outlines.
* **Hook Optimization:** Formats opening hooks to command attention before the mobile "see more" fold.
* **Zero-Reasoning Guardrail:** Request payloads include `"reasoning": {"effort": "none"}` to suppress thinking-token consumption at the API level.
* **Defensive Output Sanitization:** `clean_generated_post()` strips XML-style `<think>` tags, plain-text reasoning blocks (`Here's a thinking process:...`), intro fluff, and trailing segment tags.

### Step 5: Store & Publish (`store-and-publish`)
* **Local Persistence:** Writes full run backups to `output/{date}_all_segments.json`.
* **Webhook Delivery:** Dispatches a structured batch JSON payload to an n8n or Make webhook endpoint.
* **Zero-Story Fallback:** If zero stories qualify on a given day, an honest `no_eligible_stories` status notification is sent to Make to confirm pipeline health without spamming empty drafts.

---

## 3. Model Routing Strategy (OpenRouter $0 Cost Free Tier)

All LLM completions route through OpenRouter's OpenAI-compatible endpoint with automatic retry, exponential backoff on HTTP 429s, daily usage logging (`data/openrouter_usage.json`), and dynamic fallback across free models:

```mermaid
graph LR
    P[Primary Model: google/gemma-4-31b-it:free] --> F1[Fallback 1: nvidia/nemotron-3-super-120b-a12b:free]
    F1 --> F2[Fallback 2: nvidia/nemotron-3.5-lightning:free]
    F2 --> F3[Fallback 3: google/gemma-4-26b-a4b-it:free]
    F3 --> F4[Fallback 4: openrouter/free]
```

---

## 4. Day-Level Caching System

To avoid burning daily free-tier rate limits when re-running or debugging on the same day:
1. At the start of `run_pipeline()`, the orchestrator checks `data/daily_cache/{YYYY-MM-DD}.json`.
2. If found, it immediately skips Steps 1–4, touches zero LLM APIs, leaves `used_stories_log.json` unmodified, and re-dispatches the cached payload directly to Step 5.
3. The cache can be explicitly bypassed whenever fresh generation is desired via the `--force-refresh` CLI flag.

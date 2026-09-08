# Autonomous AI Content Repurposer Agent

An autonomous AI agent that helps founders maintain a consistent LinkedIn presence. Every day, it scans trending AI news across Hacker News and Google News, filtering out noise, digests, and off-topic stories to find the one that actually fits each founder audience. 

It pulls the real facts and angle straight from the source article, runs them through a library of proven founder post structures, and drafts an original, publish-ready LinkedIn post in a voice matched to that segment. 

No generic AI tone, no buzzwords. The finished posts land in your inbox every morning, ready to review and post, with the entire pipeline running on free-tier infrastructure and zero manual input required to generate them. Runs autonomously every 24 hours.

---

## How It Works

1. **Source (`fetch-trending-ai-news`):** Scans Hacker News (Algolia API) and Google News RSS daily. Pre-filters evergreen noise and digests, resolves real publisher URLs, and computes title fingerprints to deduplicate recurring stories.
2. **Extract (`extract-insights`):** Verifies publication freshness (< 48 hours) and distills factual signal vs. noise directly from the source page under strict anti-hallucination constraints.
3. **Pattern Check (`apply-post-pattern`):** Evaluates story event types (product launches, benchmark breakthroughs, acquisitions) against curated high-performing LinkedIn structures (*Contrarian claim*, *Vulnerability confession*, *Roadmap teardown*).
4. **Shape Narrative (`shape-narrative`):** Crafts 100% complete, publish-ready LinkedIn posts with strong opening hooks, authentic founder voice modulation, and automatic thinking-trace stripping.
5. **Publish & Store (`store-and-publish`):** Backs up batch payloads locally and delivers structured JSON to your Make/n8n webhook for automated email delivery.

---

## Key Features

* **Targeted Founder Niches:** Generates dedicated posts tailored to 4 distinct segments:
  * **Deep Tech** (Compute, semiconductors, data center infrastructure, physical scaling)
  * **SaaS (B2B)** (Enterprise RAG, agentic workflows, unit economics, procurement)
  * **SaaS (D2C)** (Consumer AI UX, latency budgets, multi-cloud inference portability)
  * **AI-native / Consumer Tech** (Autonomous agents, multimodality, liability & containment)
* **5-Step Autonomous Pipeline:**
  1. `fetch-trending-ai-news`: Daily news curation via Hacker News Algolia & Google News RSS.
  2. `extract-insights`: Date-freshness verification and factual extraction under strict anti-hallucination constraints.
  3. `apply-post-pattern`: Blueprint matching with proven hooks (*Contrarian claim*, *Vulnerability confession*, *Roadmap teardown*).
  4. `shape-narrative`: Publish-ready LinkedIn post generation with razor-sharp opening hooks.
  5. `store-and-publish`: Local JSON persistence and delivery to Make/n8n webhooks.
* **Story-Identity Deduplication:** Normalizes titles into stemmed keyword fingerprints and applies Jaccard similarity ($\ge 0.50$) against a 14-day history log (`data/used_stories_log.json`). Prevents the same real-world event covered by multiple outlets across different days from repeating.
* **Zero-Reasoning Guardrails:** Suppresses model reasoning overhead (`"effort": "none"`) at the API level, backed by regex cleaners stripping `<think>` tags and scratchpad traces.
* **Day-Level Caching:** Automatically caches each day's payload in `data/daily_cache/{YYYY-MM-DD}.json` so multiple executions on the same day re-publish instantly without consuming API rate limits.
* **Zero-Story Honest Fallback:** If zero stories qualify on quiet news days, dispatches a `no_eligible_stories` status notification instead of empty posts or broken payloads.

---

## Project Structure

```
├── .github/workflows/
│   └── daily_brief.yml          # Automated daily GitHub Actions workflow (05:00 UTC)
├── .agent/skills/               # Modular skill implementations
│   ├── common/                  # Unified OpenRouter client with exponential backoff
│   ├── fetch-trending-ai-news/  # Step 1: News discovery & fingerprint deduplication
│   ├── extract-insights/        # Step 2: Article parsing & date verification
│   ├── apply-post-pattern/      # Step 3: Structural pattern & hook blueprint matching
│   ├── shape-narrative/         # Step 4: Authentic LinkedIn post generation
│   └── store-and-publish/       # Step 5: Webhook delivery & backup archiving
├── data/
│   ├── used_stories_log.json    # 14-day persistent story history (tracked in git)
│   └── daily_cache/             # Local same-day execution cache (gitignored)
├── docs/
│   └── ARCHITECTURE.md          # In-depth system design & data flow documentation
├── examples/
│   └── sample_daily_batch.json  # Complete 4-segment sample output from production
├── tests/
│   ├── test_fingerprint_dedupe.py  # Tests for title fingerprinting & similarity scoring
│   ├── test_reasoning_cleaner.py   # Tests for <think> tag & reasoning trace stripping
│   └── test_daily_caching.py       # Tests for day-level caching & --force-refresh
├── agents.md                    # Core agent persona & pipeline specification
├── requirements.txt             # Python dependencies
├── run_daily_brief.py           # Pipeline entrypoint CLI
└── LICENSE                      # MIT License
```

---

## Getting Started

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/adhesh23/AI-content-repurposing-agent.git
cd AI-content-repurposing-agent
pip install -r requirements.txt
```

### 2. Configure Environment Secrets
Create a `.env` file at the project root (automatically excluded by `.gitignore`):
```env
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key
MAKE_WEBHOOK_URL=https://hook.us2.make.com/your-webhook-id
```

*(Optional) Configure model overrides per skill:*
```env
OPENROUTER_MODEL_SHAPE=nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_MODEL_EXTRACT=google/gemma-4-31b-it:free
```

---

## Running the Pipeline

### Full Execution
Executes the full pipeline and sends generated posts to your configured webhook:
```bash
python run_daily_brief.py
```

### Dry-Run Mode
Generates full posts and prints them to stdout without sending remote webhook requests:
```bash
python run_daily_brief.py --dry-run
```

### Force Refresh
Bypasses the same-day cache (`data/daily_cache/`) and forces a brand new run:
```bash
python run_daily_brief.py --force-refresh
```

### Specific Target Date
Runs the pipeline for an explicit calendar date:
```bash
python run_daily_brief.py --date 2026-09-08
```

---

## Running Tests

Run the full automated test suite:
```bash
pytest tests/ -v
```

---

## Automated Scheduling

A GitHub Actions workflow is pre-configured in [`.github/workflows/daily_brief.yml`](.github/workflows/daily_brief.yml):
* **Schedule:** Daily at **05:00 UTC** (10:30 AM IST).
* **Secrets Required:** Add `OPENROUTER_API_KEY` and `MAKE_WEBHOOK_URL` in your repository's **Settings > Secrets and variables > Actions**.

---

## License

This project is licensed under the [MIT License](LICENSE).

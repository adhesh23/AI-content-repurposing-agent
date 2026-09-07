# Autonomous AI Content Repurposer Agent (`agents.md`)

## 1. Overview & Purpose
The **Content Repurposer Agent** is an autonomous AI agent engineered to maintain and grow personal brand presence for founders on LinkedIn. It identifies trending AI breakthroughs and shifts each day and repurposes them into original, highly engaging, publish-ready LinkedIn posts tailored to the AI and startup ecosystem.

---

## 2. Target Audience
* **Primary Audience:** Early-stage and startup founders active on LinkedIn within the AI, tech, and startup niches.
* **Reader Profile:** Tech operators, software engineers, VCs/investors, fellow founders, and early adopters interested in practical applications, founder perspectives, and strategic takeaways rather than pure academic jargon.

---

## 3. Core Architecture & Pipeline Flow

The agent executes a 5-step modular pipeline:

```
[1. Source]
  └── fetch-trending-ai-news: Source 3-4 trending AI news items daily
          │
[2. Extract]
  └── extract-insights: Distill core developments, signal-vs-noise & key observations
          │
[3. Pattern Check]
  └── apply-post-pattern: Match insights against curated, high-performing post structures & hooks
          │
[4. Narrative]
  └── shape-narrative: Draft complete, publish-ready LinkedIn posts (Claude Sonnet 4.6)
          │
[5. Iteration & Publishing]
  ├── Individual post regeneration on demand (isolated re-run)
  └── store-and-publish: Store in repository and prepare for scheduled distribution
```

### Detailed Flow:
1. **Source (`fetch-trending-ai-news`)**: Gathers 3–4 absolutely trending AI news items daily from credible, high-signal sources.
2. **Extract (`extract-insights`)**: Extracts the central thesis, notable breakthroughs, founder takeaways, and real-world implications from each news item.
3. **Pattern Check (`apply-post-pattern`)**: Consults an internal library of proven, high-performing LinkedIn post structures and hooks specialized for the AI/startup founder niche. *(Note: Built upon curated evergreen structural patterns rather than noisy live-scraped vanity metrics — see `shape-narrative`'s `SKILL.md`).*
4. **Narrative (`shape-narrative`)**: Blends news takeaways and structural blueprints to generate full, ready-to-publish posts.
5. **Iteration**: Supports isolated, single-post regeneration without re-executing earlier pipeline stages or affecting other generated posts.

---

## 4. Skills Specification

| Skill Name | Purpose | Model Recommendation | Rationale |
| :--- | :--- | :--- | :--- |
| `fetch-trending-ai-news` | Curates 3–4 high-impact, trending AI stories of the day | **Gemini 3 Flash** or **Gemini 3.1 Pro** | Fast retrieval and high-throughput web scraping/search; does not require complex creative reasoning. |
| `extract-insights` | Synthesizes key takeaways, founder angle, and technical context | **Gemini 3.1 Pro** | Strong analytical summarization and signal-to-noise differentiation. |
| `apply-post-pattern` | Selects optimal framework (contrarian take, breakdown, teardown, lesson) and hook structure | **Gemini 3.1 Pro** | Pattern matching and strategic alignment with audience psychology. |
| `shape-narrative` | Writes final, authentic, publish-ready LinkedIn posts with high-converting hooks | **Claude Sonnet 4.6** | Critical tier: Highest creative fidelity, precise instruction-following, nuanced voice modulation, and superior hook craftsmanship. |
| `store-and-publish` | Persists generated posts, metadata, and handles distribution/drafting | **Gemini 3 Flash** or **Gemini 3.1 Pro** | Deterministic I/O, file storage, and API/queue delivery. |

---

## 5. Model Routing Strategy

* **Tier 1 (High Reasoning & Creative Fidelity):**
  * **Skill:** `shape-narrative`
  * **Model:** **Claude Sonnet 4.6**
  * **Constraint:** Output quality, tone nuance, natural rhythm, and hook potency take precedence over speed or token costs.

* **Tier 2 (Analytical & Analytical Synthesis):**
  * **Skills:** `extract-insights`, `apply-post-pattern`
  * **Model:** **Gemini 3.1 Pro** (Default)
  * **Constraint:** High contextual reasoning and accurate synthesis of technical AI details into actionable founder insights.

* **Tier 3 (Operational & Retrieval):**
  * **Skills:** `fetch-trending-ai-news`, `store-and-publish`
  * **Model:** **Gemini 3 Flash** (or Gemini 3.1 Pro)
  * **Constraint:** Optimized for rapid latency, cost-efficiency, and straightforward data handling.

---

## 6. Voice, Tone & Content Guidelines

* **Tone:** Warm, confident, insightful — never arrogant, cynical, or cocky.
* **Perspective:** Writes from the authentic standpoint of a hands-on startup founder building in or leveraging AI.
* **Authenticity:** Relatable and conversational. Strictly avoid corporate buzzwords, excessive corporate speak ("thrilled to announce", "game changer", "delve"), and synthetic AI markers.
* **Perspective Balance:** Balances optimism about technological frontiers with pragmatic founder realities (costs, unit economics, developer experience, UX, adoption friction).

---

## 7. Formatting & Post Construction Rules

* **Complete & Publish-Ready:** Output must always be a 100% complete, copy-paste-ready post. Never provide bullet outlines, summaries, or drafts with placeholder brackets.
* **The Hook is King:** The opening line (hook) is the single most critical element of the post. It must command attention in the LinkedIn feed before the "see more" cutoff:
  * Make it punchy, intriguing, or counter-intuitive.
  * Avoid clickbait questions; favor strong declarative statements or intriguing observations.
* **Whitespace & Readability:**
  * Utilize short paragraphs (1–3 sentences max) and deliberate single-line spacing.
  * Optimize readability for mobile feed scrolling.
  * Avoid hashtag clutter (limit to 0–3 relevant contextual tags at the bottom, or omit entirely).
* **Clear Takeaway or Discussion Anchor:** Every post must conclude with a sharp conclusion, actionable founder recommendation, or thought-provoking discussion prompt.

---

## 8. Expected Daily Output
* **Cadence:** Daily execution.
* **Volume:** Exactly **3 to 4** distinct, fully written LinkedIn posts per run (one dedicated post per curated news item).
* **Metadata Included:** Original news source link, selected structural pattern, and target angle.

---

## 9. Workflow References & Commands
* **Primary Pipeline Sequence:** Defined in `.agent/workflows/daily-ai-brief.md`.
* **Individual Post Regeneration:** Individual posts can be re-run by specifying the post index or topic ID directly to `shape-narrative` without re-scraping news or interrupting the rest of the batch.

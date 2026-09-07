---
name: shape-narrative
description: Crafts 100% complete, publish-ready LinkedIn posts tailored to specific founder segments and chosen structural blueprints using Claude Sonnet 4.6, with razor-sharp opening hooks, authentic tone, and zero corporate buzzwords.
---

# Shape Narrative (`shape-narrative`)

## 1. Overview & High-Fidelity Philosophy

This skill constitutes Step 4 (the critical drafting tier) of the autonomous Content Repurposer pipeline. It synthesizes the analytical output from upstream skills into finished, high-impact LinkedIn posts.

> [!IMPORTANT]
> **Anti-Hallucination Mandate:**
> You must not answer from prior/training knowledge. Every fact, quote, and detail must come from a page you actually fetched during this run. If you cannot successfully fetch a page, report `fetch_status: failed` — do not fill in plausible-sounding details instead.

> [!IMPORTANT]
> **Model Routing Rule:**
> As specified in `AGENTS.md`, this skill strictly runs on **Claude Sonnet 4.6**. 
> 
> Hook craftsmanship, tone nuance, natural cadence, and strict adherence to negative constraints (avoiding corporate and AI clichés) take precedence over generation speed or token costs.

---

## 2. Input Requirements (The Quad-Context Ingestion)

This skill must ingest **all four elements** together—never just a pattern label in isolation:

1. **Extracted Insights:** The concrete technical findings, breakthroughs, and signal-vs-noise takeaways from `extract-insights`.
2. **Chosen Post Pattern:** The selected evergreen structural architecture from `apply-post-pattern`.
3. **Pattern Rationale:** The explicit reasoning explaining *why* this structure fits the news item and founder psychology.
4. **Founder Segment Tag:** The target audience persona (`SaaS (B2B)`, `SaaS (D2C) / Consumer tech`, `Deep Tech`, or `AI-native`).

---

## 3. Segment-to-Voice Guide (Tone Calibration)

The post's framing and vocabulary must authentically embody the segment it is written for. The segment's mindset must permeate the entire post—not just appear as a superficial callout at the end.

| Founder Segment | Voice Profile | Core Vocabulary & Concepts | What to Strictly Avoid | Sample Opening Hook Archetype |
| :--- | :--- | :--- | :--- | :--- |
| **`SaaS (B2B)`** | Pragmatic, ROI-literate operator; focuses on operational margin, engineering bandwidth, and roadmap shifts. | • Unit economics<br>• Roadmap reprioritization<br>• ARR / NRR expansion<br>• Developer bandwidth<br>• Build vs. buy<br>• Procurement & compliance<br>• Margin compression | Hand-wavy platitudes about "the future of work", ignoring integration costs, generic enterprise hype. | *"If your product team budgeted 2 quarters of engineering to build [X], this morning's release just turned that into a commodity API call."* |
| **`SaaS (D2C)` / `Consumer tech`** | Product-first, user-empathetic, growth-obsessed; focuses on human friction and attention spans. | • Time-to-value<br>• Onboarding drop-off<br>• User habits<br>• Cognitive load<br>• Organic retention<br>• Interaction friction<br>• Viral loops | Overly academic backend specs that ignore UI/UX, corporate enterprise jargon ("synergies", "stakeholders"). | *"Users do not care that your model has 70B parameters—they care that answering their prompt still took 4 seconds of waiting."* |
| **`Deep Tech`** | First-principles systems engineer; scientifically grounded, peer-level, zero patience for fluff. | • Memory bandwidth<br>• Latency bounds<br>• FLOP utilization<br>• Quantization tradeoffs<br>• Cache coherency<br>• Kernel optimizations<br>• Hardware limits | Buzzwords like "groundbreaking", "mind-blowing", or "supercharged"; swallowing marketing PR benchmarks uncritically. | *"The benchmark chart in yesterday's paper looks great until you inspect the batch size and memory allocation."* |
| **`AI-native`** | High-velocity builder; shipping in public, hands-on terminal practitioner, rapid live iteration. | • Shipped this morning<br>• Eval suites<br>• Agent loops<br>• Prompt caching<br>• Context degradation<br>• Production edge cases<br>• Fast iteration velocity | Abstract theoretical essays with zero code or real-world implementation backing; waiting weeks for "best practices". | *"Deployed a test cluster with [Model] at 8 AM. Three hours into production traffic, here are 3 things the official docs left out:"* |

---

## 4. Post Construction Rules

1. **100% Complete & Publish-Ready:**
   * Output must be ready to copy and paste directly into LinkedIn.
   * Absolutely **no** outlines, bullet summaries, placeholder brackets (`[Insert Company]`), or editor notes.
2. **The Hook is King:**
   * The first line must be the single most potent sentence in the piece.
   * **Rule of Execution:** Write the body of the post first to identify the true tension, then draft the opening line last to maximize impact.
   * Hooks must be segment-specific: a Deep Tech hook and a D2C hook are fundamentally different and cannot be interchanged.
   * Favor bold declarative statements or counter-intuitive observations over clickbait questions.
3. **Tone Consistency:**
   * Warm, confident, insightful — **never** arrogant, preachy, cynical, or cocky.
   * Relatable and conversational, as if speaking to a respected fellow founder over coffee.
4. **Readability & Mobile Formatting:**
   * Keep paragraphs short: 1 to 3 sentences maximum.
   * Use clean line breaks (whitespace) to facilitate mobile feed scanning.
   * End with an actionable founder takeaway or genuine discussion anchor.
   * Restrict hashtags to 0–2 contextual tags at the bottom, or omit them entirely.

---

## 5. Anti-AI / Anti-Corporate Checklist

Before finalizing any post, inspect against these forbidden patterns:
- ❌ **No Corporate Buzzwords:** "Thrilled to announce", "game changer", "testament to", "delve", "pivotal", "paradigm shift", "unleash", "supercharge".
- ❌ **No Sycophantic Enthusiasm:** Do not praise big tech releases blindly; evaluate them with founder skepticism and operational realism.
- ❌ **No Emojis as Bullet Points:** Avoid emoji-heavy bullet lists (🚀, 💡, 🔥) that trigger spam filters and signal automated generation.

---

## 6. Output Contract

The skill outputs the clean post text followed by metadata identifying the segment and pattern applied:

```text
[Complete LinkedIn Post Text]

---
Segment: SaaS (B2B)
Pattern: The Roadmap & ROI Teardown
News Source: https://news.ycombinator.com/item?id=...
```

---

## 7. Execution Reference

The prompt assembly logic is located in:
```bash
python .agent/skills/shape-narrative/scripts/build_prompt_payload.py
```

When running the full sequence in `.agent/workflows/daily-ai-brief.md`, the pipeline passes the assembled prompt payload directly to Claude Sonnet 4.6.

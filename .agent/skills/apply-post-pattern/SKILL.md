---
name: apply-post-pattern
description: Matches extracted AI news insights and founder segment tags to curated LinkedIn post structures and hooks, tailored to specific founder engagement psychology without hallucinated engagement metrics.
---

# Apply Post Pattern (`apply-post-pattern`)

## 1. Overview & Core Philosophy

This skill represents Step 3 of the autonomous Content Repurposer pipeline. It sits between `extract-insights` (analytical distillation) and `shape-narrative` (post drafting).

Its responsibility is to choose the most compelling architectural structure for a LinkedIn post by analyzing two inputs simultaneously:
1. **The Core Insight:** The technical advancement, economic shift, or friction point extracted from the news item.
2. **The Founder Segment Tag:** The target audience persona (e.g., `Deep Tech`, `SaaS (B2B)`, `SaaS (D2C)`, `AI-native / Consumer Tech`).

### Architectural Constraint: No Fabricated Engagement Metrics
> [!IMPORTANT]
> **Zero Vanity Metrics or Hallucinated Stats:**
> Under no circumstances does this skill claim, estimate, or simulate live engagement data (e.g., "this format gets 4.2x impressions", "view count: 48,000", or "trending 22% higher today"). 
> 
> LinkedIn algorithm vanity numbers are noisy, short-lived, and prone to hallucination. Instead, patterns are selected based on **evergreen narrative architectures** and **audience psychology** proven to generate meaningful discussion among technical peers and buyers.

---

## 2. Founder Segment Framing Reference

The table below defines the baseline psychological profile and framing preferences for each founder segment.

> [!NOTE]
> **Starting Assumptions:** These associations are strategic baselines, not rigid dogmas. They should be observed and calibrated based on real audience resonance over time.

| Segment Tag | Core Engagement Framing | Tone & Angle | High-Converting Hook Archetypes |
| :--- | :--- | :--- | :--- |
| **`SaaS (B2B)`** | **ROI & Efficiency Framing**<br>• *"Here's what this means for your roadmap"*<br>• Unit economics, margins, build-vs-buy decisions | Pragmatic, margin-conscious, focused on enterprise adoption friction, security, and developer headcount costs. | • *"Most enterprise roadmaps for Q3 are already obsolete because of [X]..."*<br>• *"If your cost-per-query on [Task] is over $0.02, you have an architecture problem, not a model problem..."* |
| **`SaaS (D2C)` / `Consumer Tech`** | **Growth & Attention Framing**<br>• *"Here's what this means for your users"*<br>• User habits, onboarding friction, retention, viral loops | Empathetic to customer friction, product-led, focused on delightful interactions and human attention. | • *"Users don't care about your multi-agent architecture; they care that [Friction Point] took 4 seconds..."*<br>• *"The apps winning consumer attention right now are doing the exact opposite of what the hype cycle suggests..."* |
| **`Deep Tech`** | **Technical Credibility & First-Principles**<br>• Rigorous deconstruction of mechanisms<br>• Zero patience for marketing hype or buzzwords | High credibility, precise, engineering peer-level, respecting physics, compute, memory, and algorithmic tradeoffs. | • *"Ignore the benchmark chart in yesterday's announcement. Here is the actual bottleneck under the hood..."*<br>• *"Why [Approach A] is mathematically bounded by memory bandwidth, not parameter count..."* |
| **`AI-native` / `AI-native / Consumer Tech`** | **Fast-Take & Live Builder Velocity**<br>• *"Already building around this today"*<br>• Immediate experimentation and speed-of-shipping | High velocity, builder log, bias toward shipping in public, hands-on stack integration lessons. | • *"Shipped a test cluster using [New Release] this morning. 3 immediate takeaways from the build logs:"*<br>• *"Stop waiting for the ecosystem to stabilize. If you aren't deploying [Feature], your moat is already shrinking..."* |

---

## 3. Structural Specification & Priority Order

Based on real high-performing post analysis, the **Hook** and the **CTA / Close** drive performance and algorithmic feed retention. The middle narrative is flexible and derived directly from the facts and surprising angle.

### P0 — Hook (First 1–2 lines, must land before "see more" cutoff ~210 characters)
Driven by **`event_type`** (not the segment):

| Hook Archetype | Best For Event Types | Description & Mechanism | Example |
| :--- | :--- | :--- | :--- |
| **`subvert-the-expected`** | `funding_round` | Names the expected reaction, then explicitly refuses it. | *"We just closed a $12M oversubscribed seed round. The obvious thing to do today is post a thank-you note. Instead..."* |
| **`contrarian-claim`** | `product_launch`, `strategic_pivot`, `research_breakthrough`, `acquisition` | Directly challenges common belief, hype, or consensus. | *"If you're banking your entire product launch on a 1 million view viral moment, you've already lost."* |
| **`vulnerability-pain-confession`** | `product_launch` | Leads with honest difficulty or operational struggle rather than synthetic triumph. | *"This was my fourth product launch. It doesn't get easier."* |
| **`reframe`** | `strategic_pivot`, `research_breakthrough` | Constructed around a sharp "not X, it's Y" paradigm shift. | *"The pivot isn't the detour. It's the point."* |
| **`stakes-opener`** | `acquisition`, `partnership`, `strategic_pivot` | Bold declarative claim paired immediately with an operator credibility marker. | *"Pivoting shamelessly is a rare founder advantage. I've been doing it for 6 years."* |

### P0 — CTA / Close (Last 1–2 lines)
* **`declarative-stakes-close` (Default):** High-conviction stance or prediction. Reads as a genuine opinion piece without desperate engagement-bait.
  * *Example:* *"Choose hard. You'll get a better result."* or *"Everyone else will keep trying to scale outdated systems in a market that already moved on."*
* **`engagement-bait-question` (Strict Exception):** Explicitly invites comments; reserved strictly for genuinely open-ended industry debates without clear consensus.
  * *Example:* *"Curious—what's the hardest pivot you've had to make?"*

### P1 — Narrative Middle (Flexible Bridging)
The body bridges the hook to the close without rigid templating, selected from:
* **`bulleted_takeaways`:** 2–3 crisp, high-signal takeaway bullets (ideal when 3+ concrete facts or metrics exist).
* **`contrast_breakdown`:** Sharp wrong-way vs. right-way or expectation vs. production reality contrast.
* **`prose_reflection`:** 1–3 tight paragraphs of operator reflection.

---

## 4. Input & Output Contract

### Input:
The skill expects a single news item context with its extracted insights and assigned segment tag:
```json
{
  "segment_tag": "SaaS (B2B)",
  "extracted_insight": {
    "title": "vLLM introduces unified KV-cache memory manager",
    "core_thesis": "Memory fragmentation in self-hosted LLMs drops by 40%, cutting GPU cloud costs for high-throughput inference.",
    "founder_takeaway": "Founders can delay upgrading GPU tiers by refactoring inference memory pools."
  }
}
```

### Output:
The skill produces a structured blueprint containing the chosen pattern, segment, and rationale:
```json
{
  "segment": "SaaS (B2B)",
  "pattern_name": "The Roadmap & ROI Teardown",
  "pattern_id": "roadmap_roi_teardown",
  "tone_angle": "Pragmatic, margin-conscious, strategic roadmap prioritization.",
  "hook_archetype": "Declarative shift in cost, unit economics, or architecture that forces a product roadmap decision.",
  "blueprint_structure": [
    "Hook: A direct observation about how this shift changes enterprise cost or workflow realities.",
    "The Economic Reality: Concrete breakdown of unit economics, margins, or engineer-hours impacted.",
    "Roadmap Implication: What B2B founders should build, buy, or stop building immediately.",
    "Founder Takeaway / Discussion: A closing question to tech leaders about their quarterly priorities."
  ],
  "rationale": "Selected 'The Roadmap & ROI Teardown' for SaaS (B2B) because SaaS (B2B) audiences resonate most with ROI / efficiency framing and 'here's what this means for your roadmap' angles. The key insight ('Memory fragmentation in self-hosted LLMs drops by 40%...') directly addresses infrastructure cost savings."
}
```

---

## 5. Execution Reference

The pattern selector logic can be triggered programmatically:
```bash
python .agent/skills/apply-post-pattern/scripts/select_pattern.py
```

Downstream, `shape-narrative` consumes this output to draft the complete, ready-to-publish post.

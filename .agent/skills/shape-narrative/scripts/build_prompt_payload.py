#!/usr/bin/env python3
"""
Shape Narrative Prompt Builder
Constructs the LLM prompt payload for Claude Sonnet 4.6 to generate publish-ready LinkedIn posts.
Injects the 4 required inputs:
  1. Extracted insights
  2. Chosen post pattern
  3. Pattern rationale
  4. Founder segment tag & voice guidelines
"""

import json
import os
import sys
from typing import Dict, Any

VOICE_GUIDE_PATH = os.path.join(os.path.dirname(__file__), "..", "resources", "segment_voice_guide.json")

def load_voice_guide() -> Dict[str, Any]:
    with open(VOICE_GUIDE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def build_prompt_payload(
    insight: Dict[str, Any],
    pattern_data: Dict[str, Any],
    segment_tag: str
) -> str:
    voice_guide = load_voice_guide()
    
    # Match voice profile
    segment_profile = voice_guide.get(segment_tag)
    if not segment_profile:
        for k in voice_guide:
            if k.lower() in segment_tag.lower() or segment_tag.lower() in k.lower():
                segment_profile = voice_guide[k]
                break
                
    if not segment_profile:
        segment_profile = voice_guide["SaaS (B2B)"]

    system_instructions = f"""You are an expert ghostwriter and startup founder writing an original, complete, ready-to-publish LinkedIn post.

=== MANDATORY RULES ===
1. PUBLISH-READY FULL TEXT ONLY:
   Output exactly one 100% complete post. Do NOT write an outline, notes, or bullet points summarizing what you would write. Do NOT include placeholder brackets like '[Insert your company]'.

2. FOUNDER SEGMENT VOICING ({segment_tag}):
   You are writing specifically for and from the perspective of a {segment_tag} founder.
   - Persona Voice: {segment_profile['voice_profile']}
   - Framing Style: {segment_profile['framing_style']}
   - Organic Vocabulary to weave in: {', '.join(segment_profile['core_vocabulary'])}
   - Strictly Avoid: {', '.join(segment_profile['anti_patterns'])}
   The vocabulary and framing must be naturally integrated throughout the text, NOT tacked on as a shallow comment at the end.

3. TONE & ATTITUDE:
   Warm, confident, insightful — NEVER arrogant, cynical, preachy, or cocky.
   Avoid corporate buzzwords ("thrilled to share", "game-changer", "delve", "testament to", "unleash").

4. THE HOOK IS KING (CRAFTED WITH INTENT):
   The opening line is the single most critical sentence. It must command attention in the mobile LinkedIn feed before the 'see more' cutoff.
   - Draft the body first, then craft the hook to capture the core tension.
   - It must fit {segment_tag} psychology specifically (Sample archetype: "{segment_profile['sample_hook_style']}").
   - It must be a strong declarative observation, NOT cheap clickbait.

5. FORMATTING & READABILITY:
   - Short paragraphs (1-3 sentences max).
   - Clean whitespace between paragraphs for mobile feed readability.
   - Conclude with a sharp founder takeaway or genuine discussion prompt.
   - Keep hashtags to 0-2 contextual tags at the very bottom, or omit.

=== INPUT DATA ===
• Founder Segment: {segment_tag}
• News Story: {insight.get('title', '')}
• Core Insight & Observations: {json.dumps(insight, indent=2)}
• Selected Structural Pattern: {pattern_data.get('pattern_name', '')}
• Pattern Rationale: {pattern_data.get('rationale', '')}
• Blueprint Structure:
{chr(10).join(['  - ' + s for s in pattern_data.get('blueprint_structure', [])])}

Draft the complete LinkedIn post now. Return the raw post text followed by a tag marking its segment.
"""
    return system_instructions

if __name__ == "__main__":
    sample_insight = {
        "title": "DeepSeek introduces Multi-head Latent Attention (MLA) architecture",
        "core_thesis": "Compresses KV cache by 93% with zero loss in retrieval fidelity, drastically lowering RAM requirements for 128k context inference.",
        "founder_takeaway": "Self-hosting large context models is now viable on commodity GPU nodes without multi-million dollar cloud commitments."
    }
    sample_pattern = {
        "pattern_name": "The First-Principles Technical Deconstruction",
        "rationale": "Selected for Deep Tech because this audience demands rigorous hardware and memory deconstructions over marketing claims.",
        "blueprint_structure": [
            "Hook: Zero-hype technical statement cutting through marketing noise.",
            "Under-the-Hood Truth: Deep dive into the architectural, algorithmic, or hardware bottleneck.",
            "The First-Principles Lesson: What this reveals about physics, latency, memory, or compute limits.",
            "Founder Perspective: How genuine deep-tech builders should architect their stack."
        ]
    }
    sample_segment = "Deep Tech"
    
    prompt = build_prompt_payload(sample_insight, sample_pattern, sample_segment)
    print("--- GENERATED PROMPT PAYLOAD ---")
    print(prompt[:600] + "...\n[Truncated for display]")

#!/usr/bin/env python3
"""
Select Post Pattern Script
Matches extracted news insights, event types, and founder segment tags to curated LinkedIn post structures.
Reprioritizes post structure into:
- P0: Hook (driven by event_type, <210 chars)
- P0: Close (declarative/stakes opinion close by default; question only for open-ended topics)
- P1: Flexible Middle (bulleted_takeaways, contrast_breakdown, prose_reflection)
Enforces zero hallucinated engagement metrics.
"""

import json
import os
import sys
from typing import Dict, Any, List, Optional

PATTERNS_PATH = os.path.join(os.path.dirname(__file__), "..", "resources", "patterns.json")

# Event-to-hook affinity mapping
EVENT_HOOK_MAP = {
    "funding_round": "subvert-the-expected",
    "product_launch": "contrarian-claim",
    "strategic_pivot": "reframe",
    "partnership": "stakes-opener",
    "acquisition": "stakes-opener",
    "research_breakthrough": "reframe"
}

# Segment framing associations
SEGMENT_FRAMINGS = {
    "SaaS (B2B)": {
        "focus": "ROI / efficiency framing and 'here's what this means for your roadmap' angles",
        "tone": "Pragmatic, margin-conscious, focused on enterprise adoption friction, security, and developer headcount costs."
    },
    "SaaS (D2C)": {
        "focus": "Growth / attention framing and 'here's what this means for your users' angles",
        "tone": "User-centric, high empathy for customer friction, retention, and viral loops."
    },
    "Consumer Tech": {
        "focus": "Growth / attention framing and 'here's what this means for your users' angles",
        "tone": "Fast-paced, product-led, focused on delight, habit formation, and UX breakthroughs."
    },
    "Deep Tech": {
        "focus": "Technical credibility and first-principles framing, strictly avoiding hype words",
        "tone": "Grounded, precise, peer-level engineering depth, addressing fundamental physics, compute, or memory tradeoffs."
    },
    "AI-native / Consumer Tech": {
        "focus": "Fast-take, 'already building around this' framing with live execution velocity",
        "tone": "High velocity, bias toward shipping in public, practical implementation and stack iteration."
    },
    "AI-native": {
        "focus": "Fast-take, 'already building around this' framing with live execution velocity",
        "tone": "High velocity, hands-on, focused on agentic workflows and prompt/stack iteration."
    }
}

def load_patterns_spec() -> Dict[str, Any]:
    with open(PATTERNS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def select_post_blueprint(insight: Dict[str, Any], event_type: str, segment_tag: str) -> Dict[str, Any]:
    spec = load_patterns_spec()
    hook_map = {h["id"]: h for h in spec.get("hook_types", [])}
    close_map = {c["id"]: c for c in spec.get("close_types", [])}
    
    # 1. Select Hook (P0) based on event_type and insight nuance
    chosen_hook_id = EVENT_HOOK_MAP.get(event_type, "contrarian-claim")
    
    # Contextual adjustments for hook
    insight_text = (
        str(insight.get("title", "")) + " " +
        str(insight.get("key_facts", "")) + " " +
        str(insight.get("surprising_angle", "")) + " " +
        str(insight.get("core_thesis", ""))
    ).lower()
    
    if event_type == "product_launch":
        if any(w in insight_text for w in ["friction", "hard", "struggle", "pain", "months", "bottleneck"]):
            chosen_hook_id = "vulnerability-pain-confession"
        else:
            chosen_hook_id = "contrarian-claim"
    elif event_type == "acquisition":
        if any(w in insight_text for w in ["monopoly", "control", "switzerland", "neutral"]):
            chosen_hook_id = "stakes-opener"
        else:
            chosen_hook_id = "contrarian-claim"
            
    chosen_hook = hook_map.get(chosen_hook_id, spec["hook_types"][0])
    
    # 2. Select Close (P0) - Default to declarative/stakes opinion close
    if any(w in insight_text for w in ["unclear", "debate", "open question", "who wins"]):
        chosen_close_id = "engagement-bait-question"
    else:
        chosen_close_id = "declarative-stakes-close"
    chosen_close = close_map.get(chosen_close_id, spec["close_types"][0])
    
    # 3. Select Middle Format (P1)
    if "key_facts" in insight and isinstance(insight["key_facts"], list) and len(insight["key_facts"]) >= 3:
        middle_format = "bulleted_takeaways"
    elif "vs" in insight_text or "instead of" in insight_text or "not" in insight_text:
        middle_format = "contrast_breakdown"
    else:
        middle_format = "prose_reflection"
        
    # Find matching segment framing
    matched_key = None
    for key in SEGMENT_FRAMINGS:
        if key.lower() in segment_tag.lower() or segment_tag.lower() in key.lower():
            matched_key = key
            break
            
    framing = SEGMENT_FRAMINGS.get(matched_key, {
        "focus": "Pragmatic founder perspective balancing technical innovation with product reality",
        "tone": "Insightful, grounded, founder-to-founder."
    })
    
    angle_str = str(insight.get("surprising_angle") or "")[:110]
    rationale = (
        f"Selected hook '{chosen_hook['name']}' ({chosen_hook_id}) because the event type is '{event_type}', "
        f"and the surprising angle focuses on: {angle_str}... "
        f"Paired with '{chosen_close['name']}' to reinforce an authentic, high-conviction opinion stance without synthetic engagement bait, "
        f"tailored to {segment_tag}'s emphasis on {framing['focus']}."
    )
    
    return {
        "segment": segment_tag,
        "event_type": event_type,
        "pattern_name": f"{chosen_hook['name']} + {chosen_close['name']}",
        "hook_type": chosen_hook["id"],
        "hook_name": chosen_hook["name"],
        "hook_description": chosen_hook["description"],
        "hook_char_limit": chosen_hook["char_limit"],
        "close_type": chosen_close["id"],
        "close_name": chosen_close["name"],
        "middle_format": middle_format,
        "segment_tone": framing["tone"],
        "rationale": rationale
    }

def select_pattern(
    insight: Optional[Dict[str, Any]] = None,
    segment_tag: Optional[str] = None,
    event_type: str = "product_launch",
    **kwargs
) -> Dict[str, Any]:
    # Support both argument names (segment/segment_tag, insight/extracted_insights)
    actual_insight = insight or kwargs.get("extracted_insights") or {}
    actual_segment = segment_tag or kwargs.get("segment") or "Deep Tech"
    actual_event = event_type or kwargs.get("event_type") or "product_launch"
    return select_post_blueprint(actual_insight, actual_event, actual_segment)

if __name__ == "__main__":
    sample_insight = {
        "title": "SEOPulse Announced the Launch of Enterprise AI Visibility Platform",
        "key_facts": ["Tracks brand citations in ChatGPT and Perplexity", "50,000 prompt permutations"],
        "surprising_angle": "B2B buyers now do technical evaluation inside LLMs, making Generative Engine Optimization a critical GTM pipeline metric."
    }
    sample_event = "product_launch"
    sample_segment = "SaaS (B2B)"
    
    result = select_post_blueprint(sample_insight, sample_event, sample_segment)
    print(json.dumps(result, indent=2))


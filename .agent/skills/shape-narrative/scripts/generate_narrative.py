#!/usr/bin/env python3
"""
Generate Narrative Script — Step 4 of Content Repurposer Pipeline
Uses OpenRouter free tier models to write 100% complete, publish-ready LinkedIn posts.
Integrates build_prompt_payload with openrouter_client.
"""

import json
import os
import re
import sys
from typing import Dict, Any, Optional

# Add common and sibling scripts to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMON_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "common"))
if COMMON_DIR not in sys.path:
    sys.path.insert(0, COMMON_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from openrouter_client import call_openrouter, resolve_model_for_skill
from build_prompt_payload import build_prompt_payload

def clean_generated_post(raw_text: str) -> str:
    """
    Cleans up any conversational filler, markdown quote fences,
    or extraneous wrapper tags that LLMs sometimes output.
    Ensures pure copy-paste ready LinkedIn post text.
    """
    text = raw_text.strip()
    
    # Strip markdown code blocks if the model wrapped the post in ```
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
        elif lines[0].startswith("```"):
            text = "\n".join(lines[1:]).strip()

    # Strip intro prefixes like "Here is the LinkedIn post:" or "Here is the draft:"
    intro_patterns = [
        r"^Here is the (complete |publish-ready )?LinkedIn post:?\s*",
        r"^Here's the (complete |publish-ready )?LinkedIn post:?\s*",
        r"^Here is your post:?\s*",
        r"^Draft:?\s*"
    ]
    for p in intro_patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE).strip()

    # Remove trailing metadata block if included by the model
    # (e.g. "--- \nSegment: ..." or trailing "[Deep Tech]")
    meta_split = re.split(r'\n---\s*\n(?:Segment|Founder Segment|Pattern):', text, maxsplit=1, flags=re.IGNORECASE)
    if len(meta_split) > 1:
        text = meta_split[0].strip()

    # Strip trailing bracketed segment tag like [DeepTech] or [SaaS (B2B)]
    text = re.sub(r'\n\s*\[[A-Za-z0-9\s\(\)/_-]+\]\s*$', '', text).strip()

    return text

def generate_narrative(
    insight: Dict[str, Any],
    pattern_data: Dict[str, Any],
    segment_tag: str,
    model: Optional[str] = None,
    temperature: float = 0.7
) -> Dict[str, Any]:
    """
    Generates a full LinkedIn post for the given insight, pattern, and founder segment.
    
    Returns:
        Dict with:
          - post_text: Clean, publish-ready LinkedIn post
          - hook: Extracted opening line
          - model_used: Name of model used
          - segment: Normalized segment
    """
    prompt = build_prompt_payload(insight, pattern_data, segment_tag)
    
    messages = [
        {"role": "user", "content": prompt}
    ]
    
    result = call_openrouter(
        messages=messages,
        model=model,
        skill_name="shape-narrative",
        temperature=temperature,
        max_tokens=1500
    )
    
    cleaned_post = clean_generated_post(result["text"])
    
    # Extract hook (first non-empty line)
    lines = [l.strip() for l in cleaned_post.splitlines() if l.strip()]
    hook = lines[0] if lines else ""
    
    return {
        "post_text": cleaned_post,
        "hook": hook,
        "model_used": result["model"],
        "segment": segment_tag,
        "usage": result.get("usage", {})
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate narrative LinkedIn post via OpenRouter")
    parser.add_argument("--segment", default="Deep Tech", help="Founder segment")
    parser.add_argument("--model", default=None, help="OpenRouter model override")
    args = parser.parse_args()

    sample_insight = {
        "title": "LG Uplus Unveils Modular AI Data Center Model to Cut Construction Time",
        "key_facts": [
            "LG Uplus unveiled Power Cube, a standardized modular AI data center model.",
            "Cuts facility construction time from standard 2-3 years down to 10-12 months (over 50% faster).",
            "Modular architecture supports scaling up to 100MW with containerized liquid cooling."
        ],
        "surprising_angle": "Physical civil engineering and 3-year building construction latency is being turned into a prefabricated modular hardware appliance."
    }
    sample_pattern = {
        "pattern_name": "Vulnerability/pain confession + Declarative/stakes close",
        "rationale": "Selected for Deep Tech to focus on the unglamorous physical engineering bottlenecks.",
        "blueprint_structure": [
            "Hook: Confess an unglamorous operational pain or misjudged assumption.",
            "The Hidden Barrier: Unpack the real engineering bottleneck.",
            "The Shift: Introduce the technical breakthrough.",
            "Stakes Close: Strong declarative assertion on future winners."
        ]
    }

    try:
        res = generate_narrative(sample_insight, sample_pattern, args.segment, model=args.model)
        print("=== GENERATED POST ===")
        print(res["post_text"])
        print("\n=== HOOK ===")
        print(res["hook"])
        print(f"\nModel: {res['model_used']}")
    except Exception as e:
        print(f"Error: {e}")

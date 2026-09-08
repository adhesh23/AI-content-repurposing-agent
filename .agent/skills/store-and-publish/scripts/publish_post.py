#!/usr/bin/env python3
"""
Store and Publish Script — Dual Mode (Single Segment + Daily Batch)
Supports:
1. 'single_segment' mode: Builds individual post payload, saves {date}_{segment}.json, POSTs immediately.
2. 'daily_batch' mode: Combines all 4 segments into a single payload, saves {date}_all_segments.json, sends ONE webhook POST.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "resources", "publish_config.json")

VALID_SEGMENTS = [
    "SaaS (B2B)",
    "SaaS (D2C)",
    "Deep Tech",
    "AI-native / Consumer Tech"
]

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "webhook_url": os.getenv("MAKE_WEBHOOK_URL") or os.getenv("PUBLISH_WEBHOOK_URL", ""),
        "timeout_seconds": 15,
        "local_output_dir": "output"
    }

def normalize_segment(segment: str) -> str:
    """Validates and maps segment string to one of the 4 strict schema values."""
    cleaned = segment.strip()
    if cleaned in VALID_SEGMENTS:
        return cleaned
        
    s_lower = cleaned.lower()
    if "b2b" in s_lower:
        return "SaaS (B2B)"
    elif "d2c" in s_lower:
        return "SaaS (D2C)"
    elif "deep" in s_lower:
        return "Deep Tech"
    elif "native" in s_lower or "consumer" in s_lower:
        return "AI-native / Consumer Tech"
        
    raise ValueError(f"Invalid segment '{segment}'. Must be one of: {VALID_SEGMENTS}")

def extract_hook_from_text(post_text: str) -> str:
    """Extracts the first non-empty line of the post as the hook."""
    lines = [line.strip() for line in post_text.splitlines() if line.strip()]
    return lines[0] if lines else ""

def build_post_item(
    post_text: str,
    segment: str,
    source_title: str,
    source_url: str,
    pattern_used: str,
    hook: Optional[str] = None,
    post_date: Optional[str] = None
) -> Dict[str, Any]:
    norm_segment = normalize_segment(segment)
    if not post_date:
        post_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not hook:
        hook = extract_hook_from_text(post_text)

    return {
        "date": post_date,
        "segment": norm_segment,
        "source_title": source_title.strip(),
        "source_url": source_url.strip(),
        "pattern_used": pattern_used.strip(),
        "post_text": post_text.strip(),
        "hook": hook.strip()
    }

def build_single_payload(
    post_text: str,
    segment: str,
    source_title: str,
    source_url: str,
    pattern_used: str,
    hook: Optional[str] = None,
    post_date: Optional[str] = None
) -> Dict[str, Any]:
    """Constructs schema for single_segment mode."""
    return build_post_item(
        post_text=post_text,
        segment=segment,
        source_title=source_title,
        source_url=source_url,
        pattern_used=pattern_used,
        hook=hook,
        post_date=post_date
    )

def build_batch_payload(
    posts: List[Dict[str, Any]],
    post_date: Optional[str] = None
) -> Dict[str, Any]:
    """Constructs schema for daily_batch mode."""
    if not post_date:
        post_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    formatted_posts = []
    for item in posts:
        norm_segment = normalize_segment(item.get("segment", ""))
        post_text = item.get("post_text", "").strip()
        hook = item.get("hook") or extract_hook_from_text(post_text)
        
        post_item = {
            "segment": norm_segment,
            "hook": hook.strip(),
            "post_text": post_text,
            "source_title": item.get("source_title", "").strip(),
            "source_url": item.get("source_url", "").strip(),
            "pattern_used": item.get("pattern_used", "").strip()
        }
        formatted_posts.append(post_item)

    return {
        "date": post_date,
        "posts": formatted_posts
    }

def save_local_backup(payload: Dict[str, Any], output_dir: str = "output", is_batch: bool = False) -> str:
    """Saves payload to local output directory as guaranteed backup."""
    if not os.path.isabs(output_dir):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        target_dir = os.path.join(repo_root, output_dir)
    else:
        target_dir = output_dir

    os.makedirs(target_dir, exist_ok=True)
    date_str = payload.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    if is_batch or "posts" in payload:
        filename = f"{date_str}_all_segments.json"
    else:
        slug_segment = re.sub(r"[^a-zA-Z0-9]+", "_", payload["segment"].lower()).strip("_")
        filename = f"{date_str}_{slug_segment}.json"

    filepath = os.path.join(target_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return filepath

def send_webhook(payload: Dict[str, Any], webhook_url: str, timeout: int = 15) -> Dict[str, Any]:
    """POST payload to webhook URL with application/json header."""
    if not webhook_url or webhook_url.startswith("https://n8n.yourdomain.com") or "yourdomain.com" in webhook_url:
        return {
            "status": "skipped",
            "message": "Webhook URL is unconfigured or set to placeholder. Payload saved locally only."
        }

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AutonomousContentRepurposer/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            return {
                "status": "success",
                "http_status": status_code,
                "response": body
            }
    except urllib.error.HTTPError as e:
        return {
            "status": "failed",
            "http_status": e.code,
            "error": f"HTTP Error: {e.reason}"
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

def store_and_publish_post(
    post_text: str,
    segment: str,
    source_title: str,
    source_url: str,
    pattern_used: str,
    hook: Optional[str] = None,
    post_date: Optional[str] = None
) -> Dict[str, Any]:
    """Single-segment publishing: builds individual payload, writes {date}_{segment}.json, POSTs once."""
    config = load_config()
    webhook_url = os.getenv("MAKE_WEBHOOK_URL") or os.getenv("PUBLISH_WEBHOOK_URL", config.get("webhook_url", ""))
    timeout = config.get("timeout_seconds", 15)
    output_dir = config.get("local_output_dir", "output")

    payload = build_single_payload(
        post_text=post_text,
        segment=segment,
        source_title=source_title,
        source_url=source_url,
        pattern_used=pattern_used,
        hook=hook,
        post_date=post_date
    )

    backup_path = save_local_backup(payload, output_dir, is_batch=False)
    webhook_result = send_webhook(payload, webhook_url, timeout=timeout)

    return {
        "mode": "single_segment",
        "payload": payload,
        "local_backup_path": backup_path,
        "webhook_result": webhook_result
    }

def store_and_publish_batch(
    posts: List[Dict[str, Any]],
    post_date: Optional[str] = None
) -> Dict[str, Any]:
    """Daily-batch publishing: combines all segments, writes {date}_all_segments.json, sends ONE webhook POST."""
    config = load_config()
    webhook_url = os.getenv("MAKE_WEBHOOK_URL") or os.getenv("PUBLISH_WEBHOOK_URL", config.get("webhook_url", ""))
    timeout = config.get("timeout_seconds", 15)
    output_dir = config.get("local_output_dir", "output")

    payload = build_batch_payload(posts=posts, post_date=post_date)
    backup_path = save_local_backup(payload, output_dir, is_batch=True)
    webhook_result = send_webhook(payload, webhook_url, timeout=timeout)

    return {
        "mode": "daily_batch",
        "payload": payload,
        "local_backup_path": backup_path,
        "webhook_result": webhook_result
    }

def store_and_publish_empty_run(
    post_date: Optional[str] = None,
    segments_checked: int = 4,
    message: str = "No fresh, eligible AI news qualified in any segment today."
) -> Dict[str, Any]:
    """Fallback when no segment produced a qualifying story: sends fallback notification to webhook."""
    config = load_config()
    webhook_url = os.getenv("MAKE_WEBHOOK_URL") or os.getenv("PUBLISH_WEBHOOK_URL", config.get("webhook_url", ""))
    timeout = config.get("timeout_seconds", 15)
    output_dir = config.get("local_output_dir", "output")
    
    if not post_date:
        post_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
    payload = {
        "status": "no_eligible_stories",
        "date": post_date,
        "segments_checked": segments_checked,
        "message": message
    }
    
    backup_path = save_local_backup(payload, output_dir, is_batch=True)
    webhook_result = send_webhook(payload, webhook_url, timeout=timeout)
    
    return {
        "mode": "no_eligible_stories",
        "payload": payload,
        "local_backup_path": backup_path,
        "webhook_result": webhook_result
    }

def store_and_publish(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    mode: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Unified dispatcher supporting automatic inference or explicit mode parameter."""
    # Infer mode if not explicitly provided
    if mode is None:
        if isinstance(data, list):
            mode = "daily_batch"
        elif isinstance(data, dict) and "posts" in data:
            mode = "daily_batch"
        else:
            mode = "single_segment"

    if mode == "daily_batch":
        posts = data if isinstance(data, list) else data.get("posts", [])
        return store_and_publish_batch(posts=posts, post_date=kwargs.get("post_date", None))
    elif mode == "single_segment":
        if isinstance(data, dict):
            return store_and_publish_post(
                post_text=data.get("post_text", ""),
                segment=data.get("segment", ""),
                source_title=data.get("source_title", ""),
                source_url=data.get("source_url", ""),
                pattern_used=data.get("pattern_used", ""),
                hook=data.get("hook", None),
                post_date=data.get("date", kwargs.get("post_date", None))
            )
        else:
            raise ValueError("single_segment mode expects a single post dictionary.")
    else:
        raise ValueError(f"Unknown mode '{mode}'. Must be 'single_segment' or 'daily_batch'.")

if __name__ == "__main__":
    sample_text = (
        "If your team is budgeting two quarters of engineering to build a custom RAG cache, stop.\n\n"
        "Yesterday's unified memory release dropped self-hosted LLM cache fragmentation by 40%.\n\n"
        "That's a direct 30% reduction on your monthly cloud GPU bill.\n\n"
        "Are you planning to build caching in-house, or take the open-source win?"
    )
    single_res = store_and_publish_post(
        post_text=sample_text,
        segment="SaaS (B2B)",
        source_title="vLLM introduces unified KV-cache memory manager",
        source_url="https://news.ycombinator.com/item?id=123456",
        pattern_used="The Roadmap & ROI Teardown"
    )
    print("--- Single Segment Run ---")
    print(json.dumps(single_res, indent=2))

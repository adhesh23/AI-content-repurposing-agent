#!/usr/bin/env python3
"""
Daily AI Brief Orchestrator Pipeline
Executes the full 5-step Content Repurposer pipeline:
  Step 1: fetch-trending-ai-news
  Step 2: extract-insights
  Step 3: apply-post-pattern
  Step 4: shape-narrative (OpenRouter free tier)
  Step 5: store-and-publish
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add skills to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".agent", "skills")
sys.path.insert(0, os.path.join(SKILLS_DIR, "common"))
sys.path.insert(0, os.path.join(SKILLS_DIR, "fetch-trending-ai-news", "scripts"))
sys.path.insert(0, os.path.join(SKILLS_DIR, "extract-insights", "scripts"))
sys.path.insert(0, os.path.join(SKILLS_DIR, "apply-post-pattern", "scripts"))
sys.path.insert(0, os.path.join(SKILLS_DIR, "shape-narrative", "scripts"))
sys.path.insert(0, os.path.join(SKILLS_DIR, "store-and-publish", "scripts"))

from fetch_news import run_daily_fetch, log_used_stories
from extract_insights import extract_insights
from select_pattern import select_pattern
from generate_narrative import generate_narrative
from publish_post import store_and_publish_batch, store_and_publish_empty_run, publish_cached_payload, build_batch_payload

def run_pipeline(dry_run: bool = False, date_str: str = None, use_mock_stories: str = None, force_refresh: bool = False):
    print("=" * 60)
    print("AI CONTENT REPURPOSER PIPELINE — OPENROUTER FREE TIER")
    print("=" * 60)

    today_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_dir = os.path.join(PROJECT_ROOT, "data", "daily_cache")
    cache_file = os.path.join(cache_dir, f"{today_date}.json")

    # Day-Level Cache Check
    if os.path.exists(cache_file) and not force_refresh:
        print(f"[Cache Hit] Found existing daily cache for {today_date}: {cache_file}")
        print("[Cache Hit] Skipping Steps 1-4 (no re-fetching, no LLM calls, used_stories_log untouched).")
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_payload = json.load(f)
        except Exception as e:
            print(f"[Cache Warning] Failed to read cache file ({e}). Re-running full pipeline...")
            cached_payload = None

        if cached_payload:
            # Skip straight to Step 5 (publish to Make webhook)
            if cached_payload.get("status") == "no_eligible_stories":
                print("\n[Step 5] Re-sending cached 'no_eligible_stories' notification to webhook...")
                if dry_run:
                    print("[Dry Run] Skipping remote webhook delivery for cached zero-story payload.")
                else:
                    pub_res = publish_cached_payload(cached_payload)
                    print(f"Mode: {pub_res.get('mode')}")
                    print(f"Webhook Result: {pub_res.get('webhook_result', {}).get('status')}")
                    print(f"Backup Saved: {pub_res.get('local_backup_path')}")
            else:
                posts = cached_payload.get("posts", [])
                print(f"\n[Step 5] Re-sending cached batch of {len(posts)} posts to webhook...")
                if dry_run:
                    print("[Dry Run] Skipping remote webhook delivery. Cached posts:")
                    for p in posts:
                        print(f"\n[{p.get('segment')}] Hook: {p.get('hook')}")
                else:
                    pub_res = publish_cached_payload(cached_payload)
                    print(f"Mode: {pub_res.get('mode')}")
                    print(f"Webhook Result: {pub_res.get('webhook_result', {}).get('status')}")
                    print(f"Backup Saved: {pub_res.get('local_backup_path')}")

            print("\n" + "=" * 60)
            print("PIPELINE EXECUTION COMPLETED (FROM DAILY CACHE)")
            print("=" * 60)
            return

    if force_refresh:
        print(f"[Cache] --force-refresh specified: bypassing daily cache for {today_date}.")

    # 1. FETCH TRENDING STORIES
    if use_mock_stories and os.path.exists(use_mock_stories):
        print(f"[Step 1] Loading pre-fetched stories from: {use_mock_stories}")
        with open(use_mock_stories, "r", encoding="utf-8") as f:
            fetch_result = json.load(f)
    else:
        print("[Step 1] Fetching trending stories from HN Algolia & Google News RSS...")
        fetch_result = run_daily_fetch(current_date=date_str)

    stories = fetch_result.get("stories", [])
    if not stories:
        print("[Notice] No qualifying stories retrieved across any segment today.")
        payload = {
            "status": "no_eligible_stories",
            "date": today_date,
            "segments_checked": 4,
            "message": "No fresh, eligible AI news qualified in any segment today."
        }
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"[Cache] Saved daily payload to cache: {cache_file}")

        if dry_run:
            print("[Dry Run] Skipping remote webhook delivery for zero stories.")
        else:
            print("[Step 5] Sending 'no_eligible_stories' notification to webhook...")
            pub_res = store_and_publish_empty_run(post_date=today_date, segments_checked=4)
            print(f"Webhook Result: {pub_res.get('webhook_result', {}).get('status')}")
            print(f"Backup Saved: {pub_res.get('local_backup_path')}")
        print("\n" + "=" * 60)
        print("PIPELINE EXECUTION COMPLETED (ZERO STORIES QUALIFIED)")
        print("=" * 60)
        return

    final_posts: List[Dict[str, Any]] = []

    for story_item in stories:
        seg_name = story_item.get("segment_name")
        candidates = story_item.get("candidates", [])
        winning_candidate = story_item.get("story") or (candidates[0] if candidates else None)
        if not winning_candidate:
            print(f"Skipping {seg_name}: No winning candidate found.")
            continue
            
        title = winning_candidate.get("title", "")
        url = winning_candidate.get("url", "")
        event_type = winning_candidate.get("event_type", "product_launch")
        reported_date = winning_candidate.get("published_at", today_date)

        print(f"\n--- Processing: [{seg_name}] ---")
        print(f"Title: {title}")
        print(f"URL: {url}")
        print(f"Event Type: {event_type}")

        # 2. EXTRACT INSIGHTS
        print("[Step 2] Extracting facts & checking date freshness...")
        insight = extract_insights(
            url=url,
            segment=seg_name,
            reported_date=reported_date,
            use_llm=True
        )
        insight["title"] = title
        print(f"Freshness: {insight.get('freshness_flag')} | Facts count: {len(insight.get('key_facts', []))}")

        # 3. APPLY POST PATTERN
        print("[Step 3] Selecting optimal structural pattern & hook...")
        pattern_data = select_pattern(
            segment=seg_name,
            event_type=event_type,
            extracted_insights=insight
        )
        print(f"Pattern Selected: {pattern_data.get('pattern_name')}")

        # 4. SHAPE NARRATIVE (OPENROUTER)
        print("[Step 4] Generating narrative post via OpenRouter...")
        gen_result = generate_narrative(
            insight=insight,
            pattern_data=pattern_data,
            segment_tag=seg_name
        )
        post_text = gen_result.get("post_text", "")
        hook = gen_result.get("hook", "")
        model_used = gen_result.get("model_used", "")
        print(f"Model used: {model_used}")
        print(f"Generated Hook: {hook[:80]}...")

        post_item = {
            "date": today_date,
            "segment": seg_name,
            "source_title": title,
            "source_url": url,
            "pattern_used": pattern_data.get("pattern_name", ""),
            "post_text": post_text,
            "hook": hook
        }
        final_posts.append(post_item)

    # 5. STORE AND PUBLISH
    print(f"\n[Step 5] Publishing batch of {len(final_posts)} posts...")
    if len(final_posts) == 0:
        print("[Notice] Zero posts were generated from candidate stories today.")
        payload = {
            "status": "no_eligible_stories",
            "date": today_date,
            "segments_checked": 4,
            "message": "No fresh, eligible AI news qualified in any segment today."
        }
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"[Cache] Saved daily payload to cache: {cache_file}")

        if dry_run:
            print("[Dry Run] Skipping remote webhook delivery for zero posts.")
        else:
            print("Sending 'no_eligible_stories' notification to webhook...")
            pub_res = store_and_publish_empty_run(post_date=today_date, segments_checked=4)
            print(f"Mode: {pub_res.get('mode')}")
            print(f"Webhook Result: {pub_res.get('webhook_result', {}).get('status')}")
            print(f"Backup Saved: {pub_res.get('local_backup_path')}")
    else:
        payload = build_batch_payload(posts=final_posts, post_date=today_date)
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"[Cache] Saved daily payload to cache: {cache_file}")

        if dry_run:
            print("[Dry Run] Skipping remote webhook delivery. Posts generated:")
            for p in final_posts:
                print(f"\n[{p['segment']}] Hook: {p['hook']}")
        else:
            pub_res = store_and_publish_batch(final_posts, post_date=today_date)
            print(f"Mode: {pub_res.get('mode')}")
            print(f"Webhook Result: {pub_res.get('webhook_result', {}).get('status')}")
            print(f"Backup Saved: {pub_res.get('local_backup_path')}")

    print("\n" + "=" * 60)
    print("PIPELINE EXECUTION COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run daily AI content repurposer pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Generate posts without sending webhook")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--mock-stories", default=None, help="Path to JSON file with pre-fetched stories")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass daily cache and re-run entire pipeline fresh")
    args = parser.parse_args()

    run_pipeline(
        dry_run=args.dry_run,
        date_str=args.date,
        use_mock_stories=args.mock_stories,
        force_refresh=args.force_refresh
    )

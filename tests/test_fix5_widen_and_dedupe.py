import os
import sys
import pytest

# Ensure skill scripts are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FETCH_SKILL_DIR = os.path.join(PROJECT_ROOT, ".agent", "skills", "fetch-trending-ai-news", "scripts")
if FETCH_SKILL_DIR not in sys.path:
    sys.path.insert(0, FETCH_SKILL_DIR)

from fetch_news import (
    classify_event_type,
    compute_title_fingerprint,
    fingerprint_similarity,
    evaluate_segment_candidates,
    ELIGIBLE_EVENT_TYPES,
    SIMILARITY_THRESHOLD
)

def test_fix5_expanded_partnership():
    """Verify vendor selection and integration deals qualify as partnership."""
    # Vendor selection
    t1 = "Palantir selects Nebius as sovereign AI infrastructure provider - Data Center Dynamics"
    assert classify_event_type(t1, "") == "partnership"
    
    # Integration deal
    t2 = "Taiwan Mobile moves into enterprise AI integration with Systex - digitimes"
    assert classify_event_type(t2, "") == "partnership"
    
    # Provider adoption
    t3 = "Acme Corp adopts Gemini Enterprise as its primary AI platform"
    assert classify_event_type(t3, "") == "partnership"

def test_fix5_expanded_product_launch():
    """Verify feature additions and capability releases qualify as product_launch."""
    # Feature addition (today's D2C candidate)
    t1 = "Target adds new AI features to consumer app - Chain Store Age"
    assert classify_event_type(t1, "") == "product_launch"
    
    # Hardware / architecture capability expansion
    t2 = "Arm Expands AI Infrastructure for Agentic Era with AGI CPU and Neoverse CSS N4 - HPCwire"
    assert classify_event_type(t2, "") == "product_launch"
    
    # API / module launch
    t3 = "Frigade Launches Assist API to Give Enterprise AI Agents Product Knowledge - citybiz"
    assert classify_event_type(t3, "") == "product_launch"

def test_fix5_confirmed_strategic_pivot():
    """Verify explicit corporate pivots qualify as strategic_pivot."""
    t1 = "Paytm Turns Its Payments Engine Into An Enterprise AI Agent Business - Startup Fortune"
    assert classify_event_type(t1, "") == "strategic_pivot"

def test_fix5_strictly_excluded_categories():
    """Verify stock movements, forecasts, surveys, op-eds, webinars remain ineligible."""
    # Stock movements
    assert classify_event_type("AI infrastructure stocks rally on deal announcements from Qualcomm, Corning - CNBC", "") == "market_or_stock_movement"
    assert classify_event_type("Qualcomm Shares Climb on Amazon AI Infrastructure Deal - Investopedia", "") == "market_or_stock_movement"
    assert classify_event_type("Is NetScout Systems (NTCT) Undervalued Following Its Enterprise AI Data Platform Expansion? - simplywall.st", "") == "market_or_stock_movement"
    
    # Market size forecasts & macro spending
    assert classify_event_type("Global AI infrastructure spending could top $31T, PwC estimates - Semafor", "") == "market_forecast"
    assert classify_event_type("Enterprise AI Gateway Market Projected to Hit $11.32 Billion by 2035 | SNS Insider - GlobeNewswire", "") == "market_forecast"
    assert classify_event_type("Chinese Inflation Revives as Oil Spike, AI Boom Feed Into Prices - bloomberg.com", "") == "market_forecast"
    
    # Surveys, webinars, op-eds
    assert classify_event_type("Survey: AI has reached the consumer inflection point - Stacker", "") == "survey_or_webinar"
    assert classify_event_type("Oracle Integration Product Update Webcast September 17th 2026: Foundation for Enterprise AI Agents - Oracle Blogs", "") == "survey_or_webinar"

def test_fix5_dedupe_remains_absolute():
    """Verify Fix 4 story-identity dedupe is 100% preserved and catches Gaia duplicate."""
    cand_title = "Saudi Enterprise AI Startup Gaia Raises $1.5 Million Pre-Seed - CairoScene"
    hist_title = "Gaia raises $1.5M pre-seed led by SEEDRA Ventures for Saudi enterprise AI platform - FWDStart"
    
    # Classifies as valid funding round
    assert classify_event_type(cand_title, "") == "funding_round"
    
    # But dedupe similarity >= 0.50 threshold catches it
    fp_cand = compute_title_fingerprint(cand_title)
    fp_hist = compute_title_fingerprint(hist_title)
    sim = fingerprint_similarity(fp_cand, fp_hist)
    
    assert sim >= SIMILARITY_THRESHOLD, f"Expected dedupe match, got {sim:.3f}"
    assert sim >= 0.50

def test_fix5_freshness_fallback_extension():
    """Verify that if standard candidates are absent, 72h candidate is selected with freshness_window_extended=True."""
    segment = {
        "segment_id": "deep_tech",
        "name": "Deep Tech",
        "target_profile": "Founders building foundation models, AI infrastructure, custom architectures.",
        "hn_queries": [],
        "google_news_queries": []
    }
    
    incoming_candidate = {
        "source": "google_news_rss",
        "title": "Mistral Launches Open Foundation Model v3 with Low Latency Kernels",
        "url": "https://example.com/mistral-v3",
        "url_resolved": True,
        "published_at": "2026-09-06T12:00:00Z",
        "hours_old": 55.0,
        "snippet": "Mistral introduces open foundation model with vllm and gpu cluster support."
    }
    
    winner, scored, filtered_out, counts, fallback_used, dup_check, reroutes = evaluate_segment_candidates(
        segment=segment,
        since_timestamp=0,
        recent_used_urls=set(),
        history_window_days=14,
        incoming_rerouted_candidates=[incoming_candidate],
        recent_history_entries=[]
    )
    
    assert winner is not None, "Expected winner via 72h freshness extension"
    assert winner["freshness_window_extended"] is True
    assert winner["story"]["title"] == incoming_candidate["title"]
    assert winner["story"]["hours_old"] == 55.0

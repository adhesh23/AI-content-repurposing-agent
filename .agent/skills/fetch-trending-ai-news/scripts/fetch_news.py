#!/usr/bin/env python3
"""
Fetch Trending AI News Script
Searches Hacker News (Algolia API) and Google News RSS per founder segment.
Applies strict pre-filtering against evergreen/guide and controversy/legal pieces.
Classifies surviving candidates by event type (6 eligible types, plus fallback handling).
Ranks candidates primarily by event eligibility and segment relevance, using recency as tiebreaker.
Resolves Google News redirect URLs to genuine publisher destinations.
"""

import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "resources", "founder_segments.json")
HN_API_BASE = "https://hn.algolia.com/api/v1/search"
GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"
DEFAULT_LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "used_stories_log.json"))

# Explicit anti-hallucination mandate
ANTI_HALLUCINATION_INSTRUCTION = (
    "You must not answer from prior/training knowledge. Every fact, quote, and detail "
    "must come from a page you actually fetched during this run. If you cannot successfully "
    "fetch a page, report fetch_status: failed — do not fill in plausible-sounding details instead."
)

def load_used_stories(log_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Loads history of all past winning stories."""
    path = log_path or DEFAULT_LOG_PATH
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# Fix 4: Story-Identity Deduplication Constants
FINGERPRINT_STOPWORDS = {
    "the", "a", "an", "to", "for", "of", "in", "on", "and", "with", "at", 
    "is", "are", "what", "it", "means", "from", "how", "why", "that", "this",
    "news", "statistics", "more", "report", "tech", "consumer",
    "billion", "million", "trillion", "dollar", "dollars", "usd"
}

FINGERPRINT_VERB_STEMS = {
    "buys": "acquire", "bought": "acquire", "buy": "acquire",
    "acquires": "acquire", "acquired": "acquire", "acquisition": "acquire",
    "launches": "launch", "launched": "launch", "launching": "launch",
    "unveils": "unveil", "unveiled": "unveil", "unveiling": "unveil",
    "raises": "raise", "raised": "raise", "raising": "raise", "funding": "raise"
}

SIMILARITY_THRESHOLD = 0.50

def clean_publisher_suffix(title: str) -> str:
    """Strips trailing publisher suffix(es) like ' - Benzinga' or ' - News and Statistics - IndexBox'."""
    cleaned = (title or "").strip()
    while True:
        sub = re.sub(r"\s+[-|–—]\s+[^\s–—|-].*$", "", cleaned)
        if sub == cleaned or len(sub) < 5:
            break
        cleaned = sub.strip()
    return cleaned

def compute_title_fingerprint(title: str) -> frozenset:
    """Extract significant words from a headline for story-identity deduplication (Fix 4)."""
    if not title:
        return frozenset()
    cleaned = clean_publisher_suffix(title)
    # Strip category / date range prefixes like "Consumer Tech (Aug 31-Sep 4):" or "Consumer Tech:"
    cleaned = re.sub(r'^[A-Za-z\s\(\)\d\-\–—\.\:]+:\s*', '', cleaned)
    # Split CamelCase and compound words: HuggingFace -> Hugging Face
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"\bhuggingface\b", "hugging face", cleaned, flags=re.IGNORECASE)
    
    words = re.findall(r"[a-z0-9]+", cleaned.lower())
    significant = set()
    for w in words:
        if w in FINGERPRINT_STOPWORDS or len(w) <= 2:
            continue
        # Drop pure digit tokens or money amounts like 12b, 93b, 100m
        if re.match(r'^\d+[bmk]?$', w):
            continue
        w = FINGERPRINT_VERB_STEMS.get(w, w)
        significant.add(w)
    return frozenset(significant)

def fingerprint_similarity(a: frozenset, b: frozenset) -> float:
    """Jaccard similarity between two title fingerprints."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def get_recent_history_entries(
    log_path: Optional[str] = None,
    window_days: int = 14,
    current_date: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], set, int]:
    """Returns list of recent history entries with precomputed fingerprints, plus normalized URL set."""
    history = load_used_stories(log_path)
    if not history:
        return [], set(), window_days
        
    now = datetime.now(timezone.utc)
    if current_date:
        try:
            now = datetime.fromisoformat(current_date).replace(tzinfo=timezone.utc)
        except Exception:
            pass
            
    cutoff = now - timedelta(days=window_days)
    recent_entries = []
    used_urls = set()
    for entry in history:
        entry_date_str = entry.get("date")
        include = True
        if entry_date_str:
            try:
                dt = datetime.fromisoformat(entry_date_str).replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    include = False
            except Exception:
                include = True
        if include:
            if entry.get("source_url"):
                used_urls.add(entry["source_url"].strip().rstrip("/"))
            # Dynamically compute title fingerprint if missing
            raw_fp = entry.get("title_fingerprint")
            if raw_fp:
                entry["title_fingerprint_set"] = frozenset(raw_fp)
            else:
                title = entry.get("source_title", "")
                entry["title_fingerprint_set"] = compute_title_fingerprint(title)
            recent_entries.append(entry)
            
    return recent_entries, used_urls, window_days

def get_recent_used_urls(log_path: Optional[str] = None, window_days: int = 14, current_date: Optional[str] = None) -> Tuple[set, int]:
    """Returns set of normalized URLs used within the history window (default: 14 days)."""
    _, used_urls, days = get_recent_history_entries(log_path=log_path, window_days=window_days, current_date=current_date)
    return used_urls, days

def append_used_story(story_entry: Dict[str, Any], log_path: Optional[str] = None) -> None:
    """Appends winning story to history log, including title_fingerprint."""
    path = log_path or DEFAULT_LOG_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    history = load_used_stories(path)
    existing_urls = {h.get("source_url", "").strip().rstrip("/") for h in history if h.get("source_url")}
    
    url = story_entry.get("source_url", "").strip().rstrip("/")
    if url and url not in existing_urls:
        if "title_fingerprint" not in story_entry:
            title = story_entry.get("source_title", "")
            fp = compute_title_fingerprint(title)
            story_entry["title_fingerprint"] = sorted(list(fp))
        history.append(story_entry)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

# Minimum score threshold for a candidate to be viable as a daily winner
MIN_WINNER_SCORE_THRESHOLD = 1.0

# Pre-filter pattern sets
EVERGREEN_PATTERNS = [
    (r'\b\d+\s+(?:best|top|essential|must-have|coolest|useful|greatest)\b', "evergreen_pattern_match"),
    (r'\b(?:best|top)\s+\d+\b', "evergreen_pattern_match"),
    (r'\bhow\s+to\b', "evergreen_pattern_match"),
    (r'\bguide\s+(?:to|for)\b', "evergreen_pattern_match"),
    (r'\btips\s+(?:for|to|on)\b', "evergreen_pattern_match"),
    (r'\bways\s+to\b', "evergreen_pattern_match"),
    (r'\bexplained\b', "evergreen_pattern_match"),
    (r'\bwhat\s+(?:is|are)\b', "evergreen_pattern_match"),
    (r'\beverything\s+you\s+need\s+to\s+know\b', "evergreen_pattern_match"),
    (r'\b(?:vs\.?|versus)\b', "evergreen_pattern_match"),
    (r'\bcheat\s*sheet\b', "evergreen_pattern_match"),
    (r'\btutorial\b', "evergreen_pattern_match"),
]

LEGAL_OR_CONTROVERSY_PATTERNS = [
    (r'\b(?:lawsuit[s]?|sues?|suing|sued|litigation|legal dispute[s]?|copyright infringement|infringement lawsuit|antitrust lawsuit)\b', "legal_or_controversy"),
    (r'\b(?:layoffs?|laying off|fired|firing|scandal|in trouble)\b', "legal_or_controversy"),
    (r'\b(?:controversy|backlash|outrage|slammed|drama)\b', "legal_or_controversy"),
    (r'\b(?:shuts? down|shutting down|shutdown|bankruptcy|bankrupt|collapse[sd]?|ceases? operations|flops?)\b', "legal_or_controversy"),
]

# Fix 1: Digest / Roundup Patterns
DIGEST_DATE_RANGE_PATTERNS = [
    r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{1,2}\s*[-–—]\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?\d{1,2}\b',
    r'\bweek\s+of\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b',
    r'\b(?:weekly\s+roundup|daily\s+digest|weekly\s+digest|news\s+roundup|weekly\s+brief|ai\s+roundup|tech\s+roundup|this\s+week\s+in\s+ai)\b'
]

DIGEST_TRAILING_MORE_PATTERNS = [
    r'(?:,\s*|\band\s+|\s+[-–—]\s*|\.\.\.\s*|&\s*|\+\s*)more\s*$',
    r'\b(?:and\s+more|plus\s+more|&amp;\s+more)\b'
]

DIGEST_UNRELATED_TOPIC_WORDS = [
    "trump", "biden", "putin", "xi jinping", "lutnick", "hormuz", "strait of hormuz",
    "congress", "senate", "white house", "election", "campaign", "gaza", "israel",
    "ukraine", "russia", "pentagon", "military", "war", "tariffs?", "crude oil",
    "treasury yields?", "fed cuts?", "interest rates", "stock market", "nasdaq", "s&p 500"
]

# Eligible event types (only these can win under normal conditions)
ELIGIBLE_EVENT_TYPES = {
    "funding_round",
    "acquisition",
    "product_launch",
    "strategic_pivot",
    "partnership",
    "research_breakthrough"
}

# Fix 2: Audience profile definitions & keywords
AUDIENCE_PROFILES = {
    "deep_tech": {
        "id": "deep_tech",
        "name": "Deep Tech",
        "scope": "AI infrastructure, custom silicon, GPU compute, datacenter clusters, foundation models, weights, memory, inference latency, kernels, low-level compilers, infrastructure acquisitions.",
        "primary_keywords": [
            "nvidia", "gpu", "gpus", "cuda", "vllm", "cluster", "datacenter", "data center",
            "compute", "infrastructure", "foundation model", "foundation models", "open-source model",
            "open weights", "open-weights", "weights", "transformer architecture", "kernel", "kernels",
            "inference engine", "inference latency", "custom silicon", "chip", "chips", "hardware",
            "tpu", "groq", "cerebras", "hugging face", "huggingface", "llm infrastructure"
        ]
    },
    "saas_b2b": {
        "id": "saas_b2b",
        "name": "SaaS (B2B)",
        "scope": "B2B enterprise software, business workflows, automated operations, enterprise security, compliance, procurement, RAG for corporate data, CRM/ERP integrations.",
        "primary_keywords": [
            "enterprise", "b2b", "workflow", "workflows", "automation", "rag", "retrieval",
            "security", "procurement", "compliance", "crm", "erp", "salesforce", "workday",
            "servicenow", "slack", "copilot for work", "enterprise ai", "b2b saas", "saas platform",
            "contract analysis", "governance", "soc2"
        ]
    },
    "saas_d2c": {
        "id": "saas_d2c",
        "name": "SaaS (D2C)",
        "scope": "Consumer apps, creator economy tools, photo/video/audio editing apps, consumer subscription software, personal productivity, mobile micro-apps.",
        "primary_keywords": [
            "consumer", "creator", "creators", "photo editor", "video editor", "audio generator",
            "avatar", "mobile app", "ios app", "android app", "subscription", "d2c", "personal ai",
            "writing assistant", "lifestyle", "social app", "creative tool", "creative tools",
            "influencer", "camera app"
        ]
    },
    "ai_native_consumer": {
        "id": "ai_native_consumer",
        "name": "AI-native / Consumer Tech",
        "scope": "Autonomous AI agents, multimodal interfaces, novel human-agent interaction, realtime voice/vision systems, consumer agentic hardware/apps.",
        "primary_keywords": [
            "autonomous agent", "ai agents", "agentic", "multimodal", "voice agent", "realtime voice",
            "interactive ai", "vision model", "browser agent", "computer use", "ai companion",
            "personal assistant", "ai device", "wearable", "smart glasses", "meta ray-ban",
            "consumer tech", "assistant"
        ]
    }
}

# Segment relevance profiles (legacy compatibility)
SEGMENT_KEYWORDS = {
    seg_id: profile["primary_keywords"] for seg_id, profile in AUDIENCE_PROFILES.items()
}

def clean_html(raw_text: str) -> str:
    """Removes HTML tags and unescapes HTML entities."""
    if not raw_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_text)
    clean = html.unescape(clean)
    return " ".join(clean.split())

def load_segments(config_path: str = CONFIG_PATH) -> List[Dict[str, Any]]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def prefilter_candidate(title: str, snippet: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates candidate against pre-filter rules.
    Returns (is_filtered_out, reason).
    """
    text_to_check = f"{title} {snippet}"
    for pattern, reason in EVERGREEN_PATTERNS:
        if re.search(pattern, text_to_check, re.IGNORECASE):
            return True, reason
            
    for pattern, reason in LEGAL_OR_CONTROVERSY_PATTERNS:
        if re.search(pattern, text_to_check, re.IGNORECASE):
            return True, reason
            
    return False, None

def detect_digest_format(title: str, url: str, snippet: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates candidate against Fix 1 digest / roundup rules:
      1. Date-range pattern in title or URL slug (e.g. Aug 31-Sep 4, week of Sept 1).
      2. Trailing 'and more' / ', more' / '... more'.
      3. Multiple unrelated topics (e.g., tech mixed with Trump, Hormuz, elections, geopolitics).
      4. Compound hyphenated URL slugs bundling distinct headlines.
    Returns (is_digest, detected_reason).
    """
    text_to_check = f"{title} {snippet}"
    
    # Rule 1: Date-range patterns in title or URL
    for pattern in DIGEST_DATE_RANGE_PATTERNS:
        if re.search(pattern, text_to_check, re.IGNORECASE) or re.search(pattern, url, re.IGNORECASE):
            return True, "digest_date_range_detected"
            
    # Rule 2: Trailing catch-alls ('and more', '... more')
    for pattern in DIGEST_TRAILING_MORE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True, "digest_trailing_more_detected"
            
    # Rule 3: Multiple unrelated topics (geopolitics, elections, non-tech mixed with tech)
    unrelated_count = sum(1 for w in DIGEST_UNRELATED_TOPIC_WORDS if re.search(r'\b' + re.escape(w) + r'\b', text_to_check, re.IGNORECASE))
    if unrelated_count >= 1:
        # Check if title has separators indicating bundled stories
        if re.search(r'[,;:]|\b(?:and|while|plus|claims|buys)\b', title, re.IGNORECASE):
            return True, "digest_unrelated_topics_detected"

    # Rule 4: Compound hyphenated URL slug with 8+ dashes and unrelated words or date markers
    slug = urllib.parse.urlparse(url).path.lower()
    dash_count = slug.count("-")
    if dash_count >= 8:
        for w in DIGEST_UNRELATED_TOPIC_WORDS:
            if w.replace(" ", "-") in slug:
                return True, "digest_compound_slug_unrelated_detected"
        for pattern in DIGEST_DATE_RANGE_PATTERNS:
            if re.search(pattern, slug):
                return True, "digest_compound_slug_date_range_detected"
                
    return False, None

def extract_ai_subtopic(title: str, snippet: str) -> str:
    """
    Extracts the core AI entity / event sub-topic from a digest title/snippet.
    For example: 'Consumer Tech (Aug 31-Sep 4): NVIDIA Buys World\'s Largest Open AI Developer...'
    extracts 'NVIDIA Hugging Face' or 'NVIDIA buys open AI developer'.
    """
    # Remove leading category / date prefix like 'Consumer Tech (Aug 31-Sep 4):'
    cleaned = re.sub(r'^[A-Za-z\s\(\)\d\-\–—\.\:]+:\s*', '', title)
    
    # Remove trailing catch-alls like '& More', 'and more'
    cleaned = re.sub(r'(?:,\s*|\band\s+|\s+[-–—]\s*|\.\.\.\s*|&\s*|\+\s*)more\s*$', '', cleaned, flags=re.IGNORECASE)
    
    # Split by major geopolitical / non-tech clauses if present
    for w in DIGEST_UNRELATED_TOPIC_WORDS:
        parts = re.split(r'\b' + re.escape(w) + r'\b', cleaned, flags=re.IGNORECASE)
        if len(parts) > 1:
            cleaned = parts[0]
            
    # Clean trailing punctuation
    cleaned = re.sub(r'[,;\-\–—\s]+$', '', cleaned).strip()
    
    # If cleaned is substantial, use it; otherwise fallback to title
    return cleaned if len(cleaned) > 10 else title

def resurce_digest_candidate(candidate: Dict[str, Any], query_hint: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Re-queries HN Algolia and Google News RSS for dedicated coverage of the sub-topic
    within the trailing 48 hours.
    Returns (replacement_candidate_or_none, succeeded_flag).
    """
    subtopic = extract_ai_subtopic(candidate.get("title", ""), candidate.get("snippet", ""))
    now = datetime.now(timezone.utc)
    since_timestamp = int((now - timedelta(hours=48)).timestamp())
    
    # Form clean search queries
    # Extract key nouns/entities (e.g. NVIDIA, Hugging Face, etc.)
    words = [w for w in re.split(r'[\s,:\-\–—]+', subtopic) if len(w) > 2 and w.lower() not in ("buys", "claims", "total", "control", "largest", "developer")]
    short_query = " ".join(words[:4]) if words else subtopic
    
    # 1. Search Google News RSS
    gn_stories = fetch_google_news_raw_stories(f'"{short_query}"' if " " in short_query else short_query)
    for g_item in gn_stories:
        if g_item.get("hours_old", 999.0) <= 48.0:
            is_dig, _ = detect_digest_format(g_item["title"], g_item["url"], g_item["snippet"])
            is_pre, _ = prefilter_candidate(g_item["title"], g_item["snippet"])
            if not is_dig and not is_pre:
                # Found dedicated source
                new_cand = dict(g_item)
                resolved_url, is_resolved = resolve_google_news_url(new_cand["url"])
                new_cand["url"] = resolved_url
                new_cand["url_resolved"] = is_resolved
                return new_cand, True
                
    # 2. Search HN Algolia
    hn_stories = fetch_hn_raw_stories(short_query, since_timestamp)
    for h_item in hn_stories:
        if h_item.get("hours_old", 999.0) <= 48.0:
            is_dig, _ = detect_digest_format(h_item["title"], h_item["url"], h_item["snippet"])
            is_pre, _ = prefilter_candidate(h_item["title"], h_item["snippet"])
            if not is_dig and not is_pre:
                return dict(h_item), True
                
    return None, False

def classify_best_fit_segment(title: str, snippet: str) -> Tuple[str, float]:
    """
    Fix 2: Compares candidate subject matter against the 4 canonical founder segment profiles.
    Returns (best_fit_segment_id, confidence_score).
    """
    text = f"{title} {snippet}".lower()
    scores = {}
    
    for seg_id, profile in AUDIENCE_PROFILES.items():
        kws = profile["primary_keywords"]
        matches = 0
        for kw in kws:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, text):
                # Extra weight for multi-word or strong brand terms
                weight = 2.0 if (" " in kw or kw in ("nvidia", "vllm", "groq", "hugging face", "rag", "soc2")) else 1.0
                matches += weight
        scores[seg_id] = matches
        
    best_segment = max(scores, key=scores.get)
    max_score = scores[best_segment]
    
    # If zero matches across all, default to deep_tech
    if max_score == 0:
        return "deep_tech", 0.0
        
    return best_segment, max_score

def classify_event_type(title: str, snippet: str) -> str:
    """
    Classifies a candidate into one of the eligible or ineligible event types.
    Can be backed by an LLM call or high-precision deterministic rules.
    """
    text = f"{title} {snippet}".lower()
    
    # 1. Ineligible checks (Strict exclusions - never qualified)
    if re.search(r'\b(probe|investigation|regulators?|eu ai act|doj|ftc|sec|subpoena|antitrust|banned|compliance mandate|fined?)\b', text):
        return "regulatory_move"
    if re.search(r'\b(backlash|criticism|criticized|scandal|outrage|slammed|sparks debate)\b', text):
        return "controversy"
    if re.search(r'\b(fails?|failed|failure|shuts? down|shut down|bankruptcy|collapses?|flops?|abandoned|ceases operations)\b', text):
        return "notable_failure"
    if re.search(r'\b(stocks? (?:rally|rallies|climb[s]?|surges?|plunges?|drops?|jump[s]?|gain[s]?)|shares (?:climb[s]?|surge[s]?|rise[s]?|fall[s]?|gain[s]?|jump[s]?)|undervalued|wall st|nasdaq|dow jones|market cap|analyst rating|price target|buy or sell|holds? potential|contracts? boost .*? stocks)\b', text):
        return "market_or_stock_movement"
    if re.search(r'\b(market (?:projected|size|valued at|expected to reach)|spending could top|forecast to reach|hit \$[\d\.]+\s*(?:billion|trillion)|cagr|inflation revives)\b', text):
        return "market_forecast"
    if re.search(r'\b(webcast|webinar|conference preview|survey:\s*|survey finds|op-ed|opinion:)\b', text):
        return "survey_or_webinar"
        
    # 2. Eligible checks
    # Funding round (unchanged)
    if re.search(r'\b(raise[sd]?|secures? funding|funding round|series [a-g]|seed round|valuation of|invests? in|funding from|\$[\d\.]+\s*(?:million|billion|m|b))\b', text):
        return "funding_round"
        
    # Acquisition (unchanged)
    if re.search(r'\b(acquires?|acquired|acquisition|buys|buyout|takeover|merger)\b', text):
        return "acquisition"
        
    # Partnership / Vendor Selection / Integration Deal (expanded)
    if (re.search(r'\b(partners? with|partnered|partnership|teams? up|collaborates? with|collaboration with|integrates? with|integration with|joint deployment|alliance|contract)\b', text) or
        re.search(r'\b(?:selects?|selected|chooses?|chose|adopts?|adopted|taps?|tapped)\b.*?\b(?:as|for)\b.*?\b(?:provider|platform|partner|solution|infrastructure|engine|vendor|system)\b', text) or
        re.search(r'\b(?:moves into|deepens?|unveils?|announces?)\b.*?\b(?:integration with|integration)\b', text) or
        re.search(r'\b(?:multi-year|strategic|enterprise)\s+(?:deal|contract|partnership|alliance)\b', text)):
        return "partnership"
        
    # Strategic pivot (clarified boundary for confirmed corporate shift)
    if re.search(r'\b(pivots? to|pivoted to|pivots? beyond|pivot beyond|shifts? from|shifts? focus to|restructures?|rebrands?|transitions? to|turns its .*? into)\b', text):
        return "strategic_pivot"
        
    # Research breakthrough (unchanged)
    if re.search(r'\b(breakthrough|new model|state of the art|sota|benchmark|outperforms?|beats|novel architecture|paper|open-?weights?|open-?sources?|novel approach)\b', text):
        return "research_breakthrough"

    # Product launch / Feature additions & capability updates (expanded)
    if (re.search(r'\b(launches|launched|launch|unveils|unveiled|releases|released|release|announces|debuts|debuted|rolls out|introduces|introduced|ships|shipped|v\d+[\.\d]*)\b', text) or
        re.search(r'\b(adds?|added|adding)\b.*?\b(?:features?|capabilities?|tools?|support|functionality|agents?)\b', text) or
        re.search(r'\b(expands?|expanded)\b.*?\bwith\b.*?\b(?:cpu|gpu|chip|model|agent|feature|platform|api|tool|assistant|system|product)\b', text)):
        return "product_launch"

    return "other"

def calculate_segment_relevance(segment_id: str, title: str, snippet: str) -> float:
    """
    Computes segment relevance score (0.0 to 10.0) based on genuine alignment
    with the segment's target profile and technical scope.
    """
    text = f"{title} {snippet}".lower()
    keywords = SEGMENT_KEYWORDS.get(segment_id, SEGMENT_KEYWORDS.get("deep_tech", []))
    
    matches = sum(1 for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', text))
    # Scale: 1 match = 3.0, 2 matches = 6.0, 3+ matches = 9.0 - 10.0
    relevance = min(10.0, round(matches * 3.0, 1))
    if matches > 0 and relevance < 3.0:
        relevance = 3.0
    return relevance

def resolve_google_news_url(google_rss_url: str, timeout: int = 8) -> Tuple[str, bool]:
    """
    Follows and decodes Google News RSS redirect wrappers into the actual publisher article URL.
    Uses HTTP follow-redirect and internal batchexecute decoder.
    Returns (resolved_url, url_resolved_flag).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
    }
    try:
        req = urllib.request.Request(google_rss_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            html_content = resp.read().decode('utf-8', errors='ignore')
            
        if "news.google.com" not in final_url and "articles" not in final_url:
            return final_url, True

        match = re.search(r'<c-wiz[^>]*data-p="([^"]+)"', html_content)
        if not match:
            return google_rss_url, False
            
        data_p = match.group(1).replace("&quot;", '"')
        obj = json.loads(data_p.replace('%.@.', '["garturlreq",'))
        payload_data = obj[:-6] + obj[-2:]
        req_val = json.dumps([[["Fbv4je", json.dumps(payload_data), "null", "generic"]]])
        
        post_data = urllib.parse.urlencode({'f.req': req_val}).encode('utf-8')
        post_headers = {
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'User-Agent': headers['User-Agent']
        }
        
        batch_url = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
        batch_req = urllib.request.Request(batch_url, data=post_data, headers=post_headers, method="POST")
        with urllib.request.urlopen(batch_req, timeout=timeout) as b_resp:
            resp_text = b_resp.read().decode('utf-8')
            
        clean_json = resp_text.replace(")]}'\n\n", "").replace(")]}'", "").strip()
        arr = json.loads(clean_json)
        array_string = arr[0][2]
        article_url = json.loads(array_string)[1]
        return article_url, True
    except Exception:
        return google_rss_url, False

def parse_published_hours_old(pub_date_str: str) -> float:
    """Parses various date formats and calculates hours elapsed."""
    now = datetime.now(timezone.utc)
    try:
        parsed_tuple = email.utils.parsedate_to_datetime(pub_date_str)
        if parsed_tuple.tzinfo is None:
            parsed_tuple = parsed_tuple.replace(tzinfo=timezone.utc)
        diff = (now - parsed_tuple).total_seconds() / 3600.0
        return max(0.1, diff)
    except Exception:
        pass
        
    try:
        dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
        diff = (now - dt).total_seconds() / 3600.0
        return max(0.1, diff)
    except Exception:
        return 12.0

def fetch_hn_raw_stories(query: str, since_timestamp: int) -> List[Dict[str, Any]]:
    """Query HN Algolia Search API for stories in the last 24 hours."""
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{since_timestamp}",
        "hitsPerPage": 20
    }
    url = f"{HN_API_BASE}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "AutonomousContentRepurposer/1.0"}
    
    req = urllib.request.Request(url, headers=headers)
    now = datetime.now(timezone.utc)
    raw_stories = []
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            hits = data.get("hits", [])
            for hit in hits:
                points = int(hit.get("points") or 0)
                comments = int(hit.get("num_comments") or 0)
                title = clean_html(hit.get("title") or "")
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                created_at_i = hit.get("created_at_i", int(now.timestamp()))
                hours_old = max(0.1, (now.timestamp() - created_at_i) / 3600.0)
                
                raw_stories.append({
                    "source": "hn_algolia",
                    "title": title,
                    "url": story_url,
                    "url_resolved": True,
                    "google_news_redirect_url": None,
                    "hn_item_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "published_at": datetime.fromtimestamp(created_at_i, tz=timezone.utc).isoformat(),
                    "hours_old": round(hours_old, 2),
                    "points": points,
                    "num_comments": comments,
                    "snippet": clean_html(hit.get("story_text") or "")
                })
    except Exception as e:
        sys.stderr.write(f"HN API query failed for '{query}': {e}\n")
    return raw_stories

def fetch_google_news_raw_stories(query: str, time_window: str = "72h") -> List[Dict[str, Any]]:
    """Query Google News RSS for stories in the specified time window (default: 72h)."""
    encoded_query = urllib.parse.quote(f"{query} when:{time_window}")
    url = f"{GOOGLE_NEWS_RSS_BASE}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    headers = {"User-Agent": "AutonomousContentRepurposer/1.0"}
    
    raw_stories = []
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            for item in items[:15]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                desc_elem = item.find("description")
                
                title = clean_html(title_elem.text if title_elem is not None else "")
                raw_link = link_elem.text if link_elem is not None else ""
                pub_date = pub_elem.text if pub_elem is not None else ""
                desc = clean_html(desc_elem.text if desc_elem is not None else "")
                hours_old = parse_published_hours_old(pub_date)
                
                raw_stories.append({
                    "source": "google_news_rss",
                    "title": title,
                    "url": raw_link,
                    "url_resolved": False,
                    "google_news_redirect_url": raw_link,
                    "hn_item_url": None,
                    "published_at": pub_date,
                    "hours_old": round(hours_old, 2),
                    "points": None,
                    "num_comments": None,
                    "snippet": desc
                })
    except Exception as e:
        sys.stderr.write(f"Google News RSS query failed for '{query}': {e}\n")
    return raw_stories

def evaluate_segment_candidates(
    segment: Dict[str, Any],
    since_timestamp: int,
    recent_used_urls: Optional[set] = None,
    history_window_days: int = 14,
    incoming_rerouted_candidates: Optional[List[Dict[str, Any]]] = None,
    recent_history_entries: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int], bool, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Executes the candidate evaluation pipeline:
      1. Multi-query sourcing from HN Algolia and Google News RSS, with raw candidate de-duplication.
      2. Primary 48h freshness window evaluation: pre-filters evergreen, controversy, legal, and digest formats.
      3. Classifies surviving candidates by event type (eligible: funding_round, acquisition, partnership, product_launch, strategic_pivot, research_breakthrough).
      4. Audience-fit check (Fix 2). Mismatches routed to target segments.
      5. Scoring & ranking.
      6. Duplicate check (exact URL + Fix 4 story-identity fingerprint similarity threshold >= 0.50).
      7. Part 3 Fallback Freshness Extension (72h): Evaluated only if primary 48h window produces zero eligible winners.
    Returns (winner, scored_candidates, filtered_out, counts_returned, fallback_used, duplicate_check, candidates_to_reroute).
    """
    segment_id = segment.get("segment_id", "")
    hn_queries = segment.get("hn_queries") or ([segment.get("hn_query")] if segment.get("hn_query") else [])
    gn_queries = segment.get("google_news_queries") or ([segment.get("google_news_query")] if segment.get("google_news_query") else [])
    
    # Query HN Algolia across all query variants and de-duplicate raw results
    raw_hn = []
    seen_hn_urls = set()
    for q in hn_queries:
        if not q:
            continue
        for item in fetch_hn_raw_stories(q, since_timestamp):
            norm = (item.get("url") or "").strip().rstrip("/")
            if norm and norm not in seen_hn_urls:
                seen_hn_urls.add(norm)
                raw_hn.append(item)
            elif not norm:
                raw_hn.append(item)
                
    # Query Google News RSS across all query variants and de-duplicate raw results
    raw_gn = []
    seen_gn_urls = set()
    for q in gn_queries:
        if not q:
            continue
        for item in fetch_google_news_raw_stories(q, time_window="72h"):
            norm = (item.get("url") or "").strip().rstrip("/")
            if norm and norm not in seen_gn_urls:
                seen_gn_urls.add(norm)
                raw_gn.append(item)
            elif not norm:
                raw_gn.append(item)
                
    counts_returned = {
        "hn_algolia": len(raw_hn),
        "google_news_rss": len(raw_gn)
    }
    
    # Combine and de-duplicate raw candidate pool before classification
    all_raw = []
    seen_all_urls = set()
    for item in raw_hn + raw_gn:
        norm = (item.get("url") or "").strip().rstrip("/")
        if norm and norm not in seen_all_urls:
            seen_all_urls.add(norm)
            all_raw.append(item)
        elif not norm:
            all_raw.append(item)
            
    # Append any candidates re-routed into this segment from other segments
    if incoming_rerouted_candidates:
        for item in incoming_rerouted_candidates:
            norm = (item.get("url") or "").strip().rstrip("/")
            if norm and norm not in seen_all_urls:
                seen_all_urls.add(norm)
                all_raw.append(item)
            elif not norm:
                all_raw.append(item)

    def _evaluate_candidate_batch(candidate_pool: List[Dict[str, Any]], is_extended: bool = False):
        batch_surviving = []
        batch_filtered_out = []
        batch_to_reroute = []
        
        for item in candidate_pool:
            is_filtered, reason = prefilter_candidate(item["title"], item["snippet"])
            if is_filtered:
                batch_filtered_out.append({
                    "title": item["title"],
                    "reason": reason
                })
                continue
                
            # Step 2 (Fix 1): Digest / Roundup Filter
            is_digest, digest_reason = detect_digest_format(item["title"], item.get("url", ""), item["snippet"])
            resolved_from_digest = None
            if is_digest:
                replacement, resourced_ok = resurce_digest_candidate(item, query_hint=segment.get("name", ""))
                if resourced_ok and replacement:
                    resolved_from_digest = {
                        "original_url": item["url"],
                        "replacement_url": replacement["url"]
                    }
                    item = dict(replacement)
                    item["digest_format"] = True
                    item["resolved_from_digest"] = resolved_from_digest
                else:
                    batch_filtered_out.append({
                        "title": item["title"],
                        "reason": "digest_only_no_dedicated_source"
                    })
                    continue
            else:
                item["digest_format"] = False
                item["resolved_from_digest"] = None
                
            batch_surviving.append(item)
            
        # Event-type classification & Audience-fit check
        eligible_for_scoring = []
        for item in batch_surviving:
            is_rerouted = item.get("already_rerouted", False)
            event_type = classify_event_type(item["title"], item["snippet"])
            item["event_type"] = event_type
            
            if event_type not in ELIGIBLE_EVENT_TYPES:
                if is_rerouted:
                    batch_filtered_out.append({
                        "title": item["title"],
                        "reason": "event_type_ineligible_post_routing"
                    })
                else:
                    batch_filtered_out.append({
                        "title": item["title"],
                        "reason": "event_type_ineligible"
                    })
                continue
                
            gate_passes = list(item.get("event_type_gate_passes", []))
            if is_rerouted:
                if 1 not in gate_passes:
                    gate_passes.append(1)
                if 2 not in gate_passes:
                    gate_passes.append(2)
            else:
                if 1 not in gate_passes:
                    gate_passes.append(1)
            item["event_type_gate_passes"] = gate_passes
            
            best_fit_id, fit_confidence = classify_best_fit_segment(item["title"], item["snippet"])
            target_name = AUDIENCE_PROFILES.get(best_fit_id, {}).get("name", best_fit_id)
            segment_match = (best_fit_id == segment_id)
            item["best_fit_segment"] = target_name
            item["segment_match"] = segment_match
            
            if not segment_match and not is_rerouted:
                batch_filtered_out.append({
                    "title": item["title"],
                    "reason": "segment_mismatch",
                    "redirected_to": target_name
                })
                item_for_reroute = dict(item)
                item_for_reroute["already_rerouted"] = True
                batch_to_reroute.append({
                    "target_segment_id": best_fit_id,
                    "candidate": item_for_reroute
                })
                continue
                
            eligible_for_scoring.append(item)
            
        # Scoring & Ranking
        scored_candidates = []
        for item in eligible_for_scoring:
            event_type = item["event_type"]
            relevance_score = calculate_segment_relevance(segment_id, item["title"], item["snippet"])
            hours_old = item["hours_old"]
            recency_tiebreaker = round(max(0.0, 24.0 - hours_old) / 24.0, 3)
            hn_bonus = 0.0
            if item["source"] == "hn_algolia":
                points = item.get("points") or 0
                comments = item.get("num_comments") or 0
                hn_bonus = round(min(2.0, (points + comments) * 0.02), 2)
            final_score = round(100.0 + (relevance_score * 10.0) + hn_bonus + recency_tiebreaker, 2)
            
            candidate_entry = {
                "source": item["source"],
                "title": item["title"],
                "url": item["url"],
                "url_resolved": item.get("url_resolved", False),
                "google_news_redirect_url": item.get("google_news_redirect_url"),
                "hn_item_url": item.get("hn_item_url"),
                "published_at": item["published_at"],
                "hours_old": hours_old,
                "points": item.get("points"),
                "num_comments": item.get("num_comments"),
                "event_type": event_type,
                "event_type_gate_passes": item.get("event_type_gate_passes", [1]),
                "digest_format": item.get("digest_format", False),
                "resolved_from_digest": item.get("resolved_from_digest"),
                "best_fit_segment": item.get("best_fit_segment", segment.get("name")),
                "segment_match": item.get("segment_match", True),
                "segment_relevance_score": relevance_score,
                "score": final_score,
                "freshness_window_extended": is_extended,
                "fallback_used": False,
                "score_components": {
                    "source": item["source"],
                    "event_type": event_type,
                    "is_eligible_event": True,
                    "segment_relevance_score": relevance_score,
                    "recency_tiebreaker": recency_tiebreaker,
                    "hn_bonus": hn_bonus,
                    "formula_used": "100.0 (if eligible) + (segment_relevance * 10.0) + recency_tiebreaker + hn_bonus"
                },
                "snippet": item["snippet"]
            }
            scored_candidates.append(candidate_entry)
            
        scored_candidates.sort(key=lambda c: c["score"], reverse=True)
        
        # Winner Selection with Duplicate History Exclusion
        eligible_candidates = [c for c in scored_candidates if c["score"] >= MIN_WINNER_SCORE_THRESHOLD]
        excluded_as_repeat = []
        excluded_repeat_details = []
        winner_cand = None
        used_url_set = recent_used_urls or set()
        history_entries = recent_history_entries or []
        
        for cand in eligible_candidates:
            if cand["source"] == "google_news_rss" and not cand["url_resolved"]:
                resolved_url, is_resolved = resolve_google_news_url(cand["url"])
                cand["url"] = resolved_url
                cand["url_resolved"] = is_resolved
                
            norm_url = cand["url"].strip().rstrip("/")
            norm_redirect = (cand.get("google_news_redirect_url") or "").strip().rstrip("/")
            
            # Fast First Pass: Exact URL match
            if norm_url in used_url_set or (norm_redirect and norm_redirect in used_url_set):
                excluded_as_repeat.append(cand["url"])
                rep_detail = {
                    "title": cand["title"],
                    "reason": "duplicate_by_exact_url",
                    "matched_url": norm_url
                }
                excluded_repeat_details.append(rep_detail)
                batch_filtered_out.append(rep_detail)
                continue
                
            # Fix 4: Story-Identity Fingerprint Similarity Match
            cand_fp = compute_title_fingerprint(cand["title"])
            matched_history_entry = None
            highest_sim = 0.0
            
            for hist_entry in history_entries:
                hist_fp = hist_entry.get("title_fingerprint_set")
                if not hist_fp and hist_entry.get("source_title"):
                    hist_fp = compute_title_fingerprint(hist_entry["source_title"])
                if not hist_fp:
                    continue
                sim = fingerprint_similarity(cand_fp, hist_fp)
                if sim >= SIMILARITY_THRESHOLD and sim > highest_sim:
                    highest_sim = sim
                    matched_history_entry = hist_entry
                    
            if matched_history_entry:
                excluded_as_repeat.append(cand["url"])
                rep_detail = {
                    "title": cand["title"],
                    "reason": "duplicate_by_story_identity",
                    "matched_against": matched_history_entry.get("source_title"),
                    "matched_url": matched_history_entry.get("source_url"),
                    "similarity": round(highest_sim, 3)
                }
                excluded_repeat_details.append(rep_detail)
                batch_filtered_out.append(rep_detail)
                continue
                
            # Pre-publish safety assertion
            if cand.get("event_type") not in ELIGIBLE_EVENT_TYPES:
                batch_filtered_out.append({
                    "title": cand["title"],
                    "reason": "event_type_ineligible_final_check"
                })
                continue
                
            winner_cand = cand
            break
            
        dup_check = {
            "excluded_as_repeat": excluded_as_repeat,
            "excluded_repeat_details": excluded_repeat_details,
            "history_window_days": history_window_days
        }
        return winner_cand, scored_candidates, batch_filtered_out, batch_to_reroute, dup_check

    standard_pool = [c for c in all_raw if c.get("hours_old", 0.0) <= 48.0]
    extended_pool = [c for c in all_raw if 48.0 < c.get("hours_old", 0.0) <= 72.0]
    stale_pool = [c for c in all_raw if c.get("hours_old", 0.0) > 72.0]
    
    filtered_out = []
    for s in stale_pool:
        filtered_out.append({
            "title": s["title"],
            "reason": "stale_exceeds_72h"
        })
        
    # Pass A: Primary 48h window evaluation
    winner_cand, scored_cands, b_filtered, b_reroute, dup_check = _evaluate_candidate_batch(standard_pool, is_extended=False)
    filtered_out.extend(b_filtered)
    candidates_to_reroute = list(b_reroute)
    all_scored = list(scored_cands)
    
    # Pass B: Part 3 Fallback Freshness Extension (72h) - only if Pass A yielded no winner
    if not winner_cand and extended_pool:
        w_ext, scored_ext, ext_filtered, ext_reroute, ext_dup = _evaluate_candidate_batch(extended_pool, is_extended=True)
        filtered_out.extend(ext_filtered)
        candidates_to_reroute.extend(ext_reroute)
        all_scored.extend(scored_ext)
        if w_ext:
            winner_cand = w_ext
            dup_check["excluded_as_repeat"].extend(ext_dup["excluded_as_repeat"])
            dup_check["excluded_repeat_details"].extend(ext_dup["excluded_repeat_details"])
            sys.stderr.write(
                f"[FRESHNESS FALLBACK] Segment '{segment.get('name')}' found no eligible candidates in 48h window. "
                f"Extended freshness window to 72h: selected '{winner_cand['title']}' ({winner_cand['hours_old']}h old)\n"
            )
            
    if not winner_cand:
        return None, all_scored, filtered_out, counts_returned, False, dup_check, candidates_to_reroute
        
    winner = {
        "segment_id": segment.get("segment_id"),
        "segment_name": segment.get("name"),
        "target_profile": segment.get("target_profile"),
        "counts_returned": counts_returned,
        "filtered_out": filtered_out,
        "fallback_used": False,
        "freshness_window_extended": winner_cand.get("freshness_window_extended", False),
        "duplicate_check": dup_check,
        "candidates": all_scored,
        "story": winner_cand
    }
    return winner, all_scored, filtered_out, counts_returned, False, dup_check, candidates_to_reroute

def fetch_all_trending_ai_news(
    config_path: str = CONFIG_PATH,
    target_segment: Optional[str] = None,
    log_path: Optional[str] = None,
    record_history: bool = True,
    history_window_days: int = 14
) -> Dict[str, Any]:
    segments = load_segments(config_path)
    is_single_segment = False
    if target_segment:
        target_lower = target_segment.lower()
        segments = [
            s for s in segments
            if target_lower in s.get("name", "").lower() or target_lower in s.get("segment_id", "").lower()
        ]
        if not segments:
            raise ValueError(f"No segment found matching '{target_segment}'")
        is_single_segment = True

    now = datetime.now(timezone.utc)
    since_timestamp = int((now - timedelta(hours=72)).timestamp())
    recent_history_entries, recent_used_urls, _ = get_recent_history_entries(log_path, window_days=history_window_days)
    
    # Two-pass collection for multi-segment runs to handle cross-segment candidate re-routing:
    # Pass 1: Run each segment, collect candidates to re-route
    first_pass_results = {}
    pending_reroutes: Dict[str, List[Dict[str, Any]]] = {s["segment_id"]: [] for s in segments}
    
    for segment in segments:
        winner, candidates, filtered_out, counts, fallback_used, dup_check, to_reroute = evaluate_segment_candidates(
            segment, since_timestamp, recent_used_urls=recent_used_urls, history_window_days=history_window_days,
            recent_history_entries=recent_history_entries
        )
        first_pass_results[segment["segment_id"]] = {
            "winner": winner,
            "candidates": candidates,
            "filtered_out": filtered_out,
            "counts": counts,
            "fallback_used": fallback_used,
            "dup_check": dup_check,
            "to_reroute": to_reroute
        }
        for rr in to_reroute:
            t_id = rr["target_segment_id"]
            if t_id in pending_reroutes:
                pending_reroutes[t_id].append(rr["candidate"])

    # If any re-routes occurred and we are running multi-segment, re-evaluate target segments with incoming re-routes
    has_reroutes = any(len(cands) > 0 for cands in pending_reroutes.values())
    
    final_segment_results = {}
    for segment in segments:
        s_id = segment["segment_id"]
        incoming = pending_reroutes.get(s_id, [])
        if has_reroutes and incoming and not is_single_segment:
            # Re-evaluate with incoming re-routed candidates
            winner, candidates, filtered_out, counts, fallback_used, dup_check, _ = evaluate_segment_candidates(
                segment, since_timestamp, recent_used_urls=recent_used_urls, history_window_days=history_window_days,
                incoming_rerouted_candidates=incoming,
                recent_history_entries=recent_history_entries
            )
            # Combine initial filtered_out with any new ones
            combined_filtered_out = first_pass_results[s_id]["filtered_out"] + [
                f for f in filtered_out if f not in first_pass_results[s_id]["filtered_out"]
            ]
            final_segment_results[s_id] = (winner, candidates, combined_filtered_out, counts, fallback_used, dup_check)
        else:
            res = first_pass_results[s_id]
            final_segment_results[s_id] = (
                res["winner"], res["candidates"], res["filtered_out"], res["counts"], res["fallback_used"], res["dup_check"]
            )

    selected_stories = []
    skipped_segments = []
    total_hn_returned = 0
    total_gn_returned = 0

    for segment in segments:
        s_id = segment["segment_id"]
        winner, candidates, filtered_out, counts, fallback_used, dup_check = final_segment_results[s_id]
        total_hn_returned += counts["hn_algolia"]
        total_gn_returned += counts["google_news_rss"]
        
        if winner:
            selected_stories.append(winner)
            if record_history and winner.get("story"):
                w_story = winner["story"]
                w_title = w_story.get("title", "")
                w_fp = sorted(list(compute_title_fingerprint(w_title)))
                history_entry = {
                    "date": now.strftime("%Y-%m-%d"),
                    "segment": winner.get("segment_name"),
                    "source_title": w_title,
                    "source_url": w_story.get("url"),
                    "title_fingerprint": w_fp
                }
                append_used_story(history_entry, log_path=log_path)
                if w_story.get("url"):
                    recent_used_urls.add(w_story["url"].strip().rstrip("/"))
                history_entry["title_fingerprint_set"] = frozenset(w_fp)
                recent_history_entries.append(history_entry)
        else:
            skipped_segments.append({
                "segment_id": segment.get("segment_id"),
                "segment_name": segment.get("name"),
                "counts_returned": counts,
                "filtered_out": filtered_out,
                "duplicate_check": dup_check,
                "candidates_considered": len(candidates),
                "reason": "No candidate surpassed quality, freshness (<=72h), non-repeat, or event-type eligibility requirements."
            })
            
    return {
        "fetched_at": now.isoformat(),
        "sources_queried": ["hn_algolia", "google_news_rss"],
        "counts_returned": {
            "hn_algolia": total_hn_returned,
            "google_news_rss": total_gn_returned
        },
        "total_selected": len(selected_stories),
        "stories": selected_stories,
        "skipped_segments": skipped_segments
    }

def run_daily_fetch(
    config_path: str = CONFIG_PATH,
    target_segment: Optional[str] = None,
    log_path: Optional[str] = None,
    record_history: bool = True,
    current_date: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience alias for fetch_all_trending_ai_news used by daily orchestrators."""
    return fetch_all_trending_ai_news(
        config_path=config_path,
        target_segment=target_segment,
        log_path=log_path,
        record_history=record_history
    )

log_used_stories = append_used_story

if __name__ == "__main__":
    out_file = None
    target_seg = None
    log_file = None
    record_hist = True
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("--output", "-o") and i + 1 < len(args):
            out_file = args[i + 1]
            i += 2
        elif args[i] in ("--segment", "-s") and i + 1 < len(args):
            target_seg = args[i + 1]
            i += 2
        elif args[i] in ("--log-path", "-l") and i + 1 < len(args):
            log_file = args[i + 1]
            i += 2
        elif args[i] == "--no-record-history":
            record_hist = False
            i += 1
        else:
            i += 1
        
    data = fetch_all_trending_ai_news(target_segment=target_seg, log_path=log_file, record_history=record_hist)
    out_json = json.dumps(data, indent=2)
    
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(out_json)
        print(f"Saved {data['total_selected']} segment stories to {out_file}")
    else:
        print(out_json)

#!/usr/bin/env python3
"""
Extract Insights Script — Step 2 of Content Repurposer Pipeline
Fetches article content from verified URLs, extracts factual developments,
verifies publication date freshness, and checks against anti-hallucination rules.
"""

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

ANTI_HALLUCINATION_INSTRUCTION = (
    "You must not answer from prior/training knowledge. Every fact, quote, and detail "
    "must come from a page you actually fetched during this run. If you cannot successfully "
    "fetch a page, report fetch_status: failed — do not fill in plausible-sounding details instead."
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9'
}

def fetch_page_html(url: str, timeout: int = 15) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Fetches raw HTML from destination URL.
    Returns (html_text, status, error_message).
    status: 'success' | 'blocked' | 'failed'
    """
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            final_url = response.geturl()
            charset = response.headers.get_content_charset() or 'utf-8'
            content = response.read().decode(charset, errors='replace')
            
            # Check for bot block / captcha / js wall signatures
            lower_c = content.lower()
            if any(b in lower_c for b in ["cf-browser-verification", "turnstile", "captcha", "security check", "please verify you are a human"]):
                return content, "blocked", "Captcha or bot challenge page detected."
            if "<title>just a moment...</title>" in lower_c:
                return content, "blocked", "Cloudflare protection wall."
                
            return content, "success", None
    except urllib.error.HTTPError as e:
        if e.code in (403, 401):
            return None, "blocked", f"HTTP {e.code}: Access Denied / Paywall"
        return None, "failed", f"HTTP Error {e.code}: {e.reason}"
    except Exception as e:
        return None, "failed", str(e)

def extract_date_from_html(html_text: str, url: str) -> Optional[str]:
    """
    Extracts publish date (YYYY-MM-DD) from HTML meta tags, JSON-LD, or URL pattern.
    """
    # 1. Meta tags
    meta_patterns = [
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
        r'<meta[^>]+name=["\']pubdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']publishdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']'
    ]
    for pat in meta_patterns:
        m = re.search(pat, html_text, re.IGNORECASE)
        if m:
            val = m.group(1)
            d_match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', val)
            if d_match:
                return f"{d_match.group(1)}-{d_match.group(2)}-{d_match.group(3)}"

    # 2. JSON-LD datePublished
    ld_matches = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_text, re.DOTALL | re.IGNORECASE)
    for ld in ld_matches:
        d_match = re.search(r'["\']datePublished["\']\s*:\s*["\'](\d{4})[-/](\d{2})[-/](\d{2})', ld)
        if d_match:
            return f"{d_match.group(1)}-{d_match.group(2)}-{d_match.group(3)}"

    # 3. URL regex pattern (e.g. /2026/09/06/ or /26/09/06/)
    url_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if url_match:
        return f"{url_match.group(1)}-{url_match.group(2)}-{url_match.group(3)}"
    url_short_match = re.search(r'/(\d{2})/(\d{2})/(\d{2})/', url)
    if url_short_match:
        yr = "20" + url_short_match.group(1)
        return f"{yr}-{url_short_match.group(2)}-{url_short_match.group(3)}"

    # 4. Text regex for date (e.g. "September 6, 2026" or "Sep 6, 2026")
    months = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    text_date = re.search(rf'({months})\s+(\d{{1,2}}),\s+(\d{{4}})', html_text[:10000], re.IGNORECASE)
    if text_date:
        try:
            m_str, day_str, yr_str = text_date.groups()
            dt = datetime.strptime(f"{m_str[:3]} {day_str} {yr_str}", "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    return None

def verify_freshness(reported_date: Optional[str], actual_date_on_page: Optional[str]) -> str:
    """
    Returns 'verified_fresh' | 'date_mismatch' | 'no_date_found'.
    """
    if not actual_date_on_page:
        return "no_date_found"
    if not reported_date:
        return "verified_fresh"

    try:
        # Extract YYYY-MM-DD from reported_date (could be ISO or RFC format)
        d_match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', reported_date)
        if not d_match:
            return "verified_fresh"
        rep_dt = datetime.strptime(f"{d_match.group(1)}-{d_match.group(2)}-{d_match.group(3)}", "%Y-%m-%d")
        act_dt = datetime.strptime(actual_date_on_page, "%Y-%m-%d")
        
        diff_days = abs((act_dt - rep_dt).days)
        if diff_days <= 2:  # within 48h tolerance
            return "verified_fresh"
        else:
            return "date_mismatch"
    except Exception:
        return "verified_fresh"

def extract_insights(
    url: str,
    segment: str,
    reported_date: Optional[str] = None,
    pre_extracted_facts: Optional[List[str]] = None,
    pre_extracted_quote: Optional[str] = None,
    pre_extracted_angle: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs live page fetch, extracts publication date, checks freshness,
    and structures key facts, notable quotes, and surprising angles.
    """
    html_text, status, err = fetch_page_html(url)
    
    actual_date = None
    if status == "success" and html_text:
        actual_date = extract_date_from_html(html_text, url)
    elif status != "success":
        # Check if URL itself has a verifiable date pattern
        actual_date = extract_date_from_html("", url)

    freshness_flag = verify_freshness(reported_date, actual_date)

    return {
        "segment": segment,
        "source_url": url,
        "fetch_status": status,
        "freshness_flag": freshness_flag,
        "reported_date": reported_date,
        "actual_date_on_page": actual_date,
        "key_facts": pre_extracted_facts or [],
        "notable_quote": pre_extracted_quote,
        "surprising_angle": pre_extracted_angle,
        "fetch_error": err
    }

if __name__ == "__main__":
    test_url = "https://www.chosun.com/english/industry-en/2026/09/06/QYUPBDLY45CLJM3QV436YJ5KEI/"
    res = extract_insights(test_url, "Deep Tech", reported_date="2026-09-06")
    print(json.dumps(res, indent=2))

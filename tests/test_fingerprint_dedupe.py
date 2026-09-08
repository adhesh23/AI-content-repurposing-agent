import os
import sys
import pytest

# Ensure skill scripts are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FETCH_SKILL_DIR = os.path.join(PROJECT_ROOT, ".agent", "skills", "fetch-trending-ai-news", "scripts")
if FETCH_SKILL_DIR not in sys.path:
    sys.path.insert(0, FETCH_SKILL_DIR)

from fetch_news import compute_title_fingerprint, fingerprint_similarity

def test_compute_title_fingerprint_stopwords_and_stemming():
    """Verify that stop words, punctuation, and currency amounts are stripped, and verbs are stemmed."""
    title = "Consumer Tech: NVIDIA Buys Hugging Face for $12.93B"
    fp = compute_title_fingerprint(title)
    
    # "buys" should stem to "acquire"
    assert "acquire" in fp
    assert "nvidia" in fp
    assert "hugging" in fp
    assert "face" in fp
    
    # Stopwords and noise should be excluded
    assert "for" not in fp
    assert "tech" not in fp
    assert "consumer" not in fp

def test_same_event_cross_outlet_high_similarity():
    """Verify that different articles covering the exact same event score >= 0.50 similarity."""
    title_benzinga = "Consumer Tech: NVIDIA Buys Hugging Face for $12.93B"
    title_indexbox = "Nvidia acquires Hugging Face for $12.93 billion - IndexBox"
    
    fp1 = compute_title_fingerprint(title_benzinga)
    fp2 = compute_title_fingerprint(title_indexbox)
    
    sim = fingerprint_similarity(fp1, fp2)
    # Both share nvidia, acquire, hugging, face -> Jaccard similarity is 1.0 (or > 0.8)
    assert sim >= 0.50, f"Expected high similarity for same event, got {sim:.2f}"

def test_unrelated_acquisitions_low_similarity():
    """Verify that two unrelated acquisition stories share low similarity (< 0.50)."""
    title_google = "Google Acquires Wiz for $32 Billion to Bolster Cloud Security"
    title_salesforce = "Salesforce Acquires Informatica for $8 Billion in Major Data Play"
    
    fp_google = compute_title_fingerprint(title_google)
    fp_salesforce = compute_title_fingerprint(title_salesforce)
    
    sim = fingerprint_similarity(fp_google, fp_salesforce)
    # They only share the verb 'acquire', so Jaccard similarity should be well below 0.50
    assert sim < 0.50, f"Expected low similarity for unrelated acquisitions, got {sim:.2f}"

def test_identical_titles_perfect_similarity():
    """Verify that identical titles produce a similarity score of 1.0."""
    title = "SEOPulse Announced the Launch of Enterprise AI Visibility Platform"
    fp1 = compute_title_fingerprint(title)
    fp2 = compute_title_fingerprint(title)
    
    assert fingerprint_similarity(fp1, fp2) == 1.0

def test_empty_titles_zero_similarity():
    """Verify that empty inputs gracefully evaluate to 0.0 similarity."""
    assert fingerprint_similarity([], ["test"]) == 0.0
    assert fingerprint_similarity([], []) == 0.0

import os
import sys
import json
import pytest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from run_daily_brief import run_pipeline

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Provides a temporary cache directory for isolated test runs."""
    cache_dir = tmp_path / "data" / "daily_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir)

def test_cache_file_created_on_run(tmp_path, monkeypatch):
    """Verify that a successful pipeline run creates the daily cache JSON file."""
    test_date = "2026-09-08"
    cache_dir = os.path.join(PROJECT_ROOT, "data", "daily_cache")
    cache_file = os.path.join(cache_dir, f"{test_date}.json")
    
    # Backup and clean cache file if present
    existing_content = None
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            existing_content = f.read()
        os.remove(cache_file)
        
    mock_stories = {
        "date": test_date,
        "stories": [
            {
                "segment_name": "Deep Tech",
                "story": {
                    "title": "Test AI Breakthrough",
                    "url": "https://example.com/ai-story",
                    "event_type": "product_launch",
                    "published_at": test_date
                }
            }
        ]
    }
    mock_file = str(tmp_path / "mock.json")
    with open(mock_file, "w", encoding="utf-8") as f:
        json.dump(mock_stories, f)
        
    try:
        with patch("run_daily_brief.extract_insights") as mock_extract, \
             patch("run_daily_brief.generate_narrative") as mock_narrative:
            
            mock_extract.return_value = {"title": "Test AI", "key_facts": ["Fact 1"], "freshness_flag": "fresh"}
            mock_narrative.return_value = {
                "post_text": "Sample hook.\n\nSample post body text.",
                "hook": "Sample hook.",
                "model_used": "test-model",
                "segment": "Deep Tech"
            }
            
            run_pipeline(dry_run=True, date_str=test_date, use_mock_stories=mock_file)
            
        assert os.path.exists(cache_file), "Cache file was not created!"
        with open(cache_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
            
        assert payload.get("date") == test_date
        assert len(payload.get("posts", [])) == 1
        assert payload["posts"][0]["hook"] == "Sample hook."
        
    finally:
        # Restore pre-existing cache file if there was one
        if existing_content is not None:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(existing_content)

def test_cache_hit_skips_processing_and_llm(tmp_path, capsys):
    """Verify that when a cache file exists, Steps 1-4 are skipped entirely."""
    test_date = "2026-09-08"
    cache_dir = os.path.join(PROJECT_ROOT, "data", "daily_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{test_date}.json")
    
    cached_payload = {
        "date": test_date,
        "posts": [
            {
                "segment": "SaaS (B2B)",
                "hook": "Cached hook line.",
                "post_text": "Cached hook line.\n\nCached body paragraph.",
                "source_title": "Cached Title",
                "source_url": "https://example.com/cached",
                "pattern_used": "Contrarian claim"
            }
        ]
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cached_payload, f, indent=2)
        
    # Run pipeline without mocks — if it tries to fetch or call OpenRouter, it would fail or do network work
    run_pipeline(dry_run=True, date_str=test_date)
    captured = capsys.readouterr().out
    
    assert "[Cache Hit]" in captured
    assert "Cached hook line." in captured
    assert "PIPELINE EXECUTION COMPLETED (FROM DAILY CACHE)" in captured

def test_force_refresh_bypasses_cache(tmp_path, capsys):
    """Verify that --force-refresh bypasses the existing cache file."""
    test_date = "2026-09-08"
    cache_dir = os.path.join(PROJECT_ROOT, "data", "daily_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{test_date}.json")
    
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"date": test_date, "posts": []}, f)
        
    mock_file = str(tmp_path / "mock.json")
    with open(mock_file, "w", encoding="utf-8") as f:
        json.dump({"date": test_date, "stories": []}, f)
        
    run_pipeline(dry_run=True, date_str=test_date, use_mock_stories=mock_file, force_refresh=True)
    captured = capsys.readouterr().out
    
    assert "--force-refresh specified: bypassing daily cache" in captured

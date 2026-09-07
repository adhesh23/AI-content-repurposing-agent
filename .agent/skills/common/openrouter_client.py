#!/usr/bin/env python3
"""
OpenRouter Client Utility — AI Content Repurposer
Provides unified access to OpenRouter's OpenAI-compatible completions endpoint:
https://openrouter.ai/api/v1/chat/completions

Features:
- Single API key (OPENROUTER_API_KEY)
- Automatic retry with exponential backoff on HTTP 429 rate limits (3 retries default)
- Daily usage counter tracking (stored in data/openrouter_usage.json)
- Per-skill model resolution via environment variables:
    OPENROUTER_MODEL_SHAPE
    OPENROUTER_MODEL_EXTRACT
    OPENROUTER_MODEL_FETCH
    OPENROUTER_MODEL_PATTERN
    OPENROUTER_MODEL_DEFAULT (default: google/gemma-4-31b-it:free)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_FREE_MODEL = "google/gemma-4-31b-it:free"
USAGE_LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "openrouter_usage.json"))

def _load_dotenv_if_present():
    """Lightweight .env loader that populates os.environ without third-party dependencies."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    env_file = os.path.join(project_root, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        # Only set if not already in os.environ
                        if k and not os.environ.get(k):
                            os.environ[k] = v.strip('"').strip("'")
        except Exception:
            pass

_load_dotenv_if_present()

MODEL_ENV_KEYS = {
    "shape": "OPENROUTER_MODEL_SHAPE",
    "shape-narrative": "OPENROUTER_MODEL_SHAPE",
    "extract": "OPENROUTER_MODEL_EXTRACT",
    "extract-insights": "OPENROUTER_MODEL_EXTRACT",
    "fetch": "OPENROUTER_MODEL_FETCH",
    "fetch-trending-ai-news": "OPENROUTER_MODEL_FETCH",
    "pattern": "OPENROUTER_MODEL_PATTERN",
    "apply-post-pattern": "OPENROUTER_MODEL_PATTERN",
}

def resolve_model_for_skill(skill_name: Optional[str] = None, fallback_model: Optional[str] = None) -> str:
    if skill_name:
        env_key = MODEL_ENV_KEYS.get(skill_name.lower().strip())
        if env_key and os.environ.get(env_key):
            return os.environ[env_key].strip()
            
    default_env = os.environ.get("OPENROUTER_MODEL_DEFAULT")
    if default_env and default_env.strip():
        return default_env.strip()
        
    if fallback_model and fallback_model.strip():
        return fallback_model.strip()
        
    return DEFAULT_FREE_MODEL

def track_usage(model: str, status: str = "success") -> None:
    try:
        os.makedirs(os.path.dirname(USAGE_LOG_PATH), exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        usage_data: Dict[str, Any] = {}
        
        if os.path.exists(USAGE_LOG_PATH):
            try:
                with open(USAGE_LOG_PATH, "r", encoding="utf-8") as f:
                    usage_data = json.load(f)
            except Exception:
                usage_data = {}
                
        if today not in usage_data:
            usage_data[today] = {
                "total_requests": 0,
                "successful_requests": 0,
                "rate_limited_count": 0,
                "models_used": {}
            }
            
        day_stats = usage_data[today]
        day_stats["total_requests"] = day_stats.get("total_requests", 0) + 1
        if status == "success":
            day_stats["successful_requests"] = day_stats.get("successful_requests", 0) + 1
        elif status == "rate_limited":
            day_stats["rate_limited_count"] = day_stats.get("rate_limited_count", 0) + 1
            
        models_dict = day_stats.setdefault("models_used", {})
        models_dict[model] = models_dict.get(model, 0) + 1
        
        with open(USAGE_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(usage_data, f, indent=2)
    except Exception:
        pass

def get_daily_usage_count(date_str: Optional[str] = None) -> int:
    target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not os.path.exists(USAGE_LOG_PATH):
        return 0
    try:
        with open(USAGE_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get(target_date, {}).get("total_requests", 0)
    except Exception:
        return 0

FALLBACK_FREE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "minimax/minimax-m2.7:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "openrouter/free"
]

def call_openrouter(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    skill_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    max_retries: int = 3,
    initial_backoff: float = 2.0
) -> Dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is missing. "
            "Please set OPENROUTER_API_KEY with your OpenRouter API key."
        )

    primary_model = model or resolve_model_for_skill(skill_name)
    models_to_try = [primary_model] + [m for m in FALLBACK_FREE_MODELS if m != primary_model]

    last_error = None
    for current_model in models_to_try:
        payload = {
            "model": current_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/adhesh23/AI-content-repurposing-agent",
            "X-Title": "AI Content Repurposer Agent",
            "User-Agent": "AIContentRepurposer/1.0"
        }

        attempt = 0
        while attempt <= max_retries:
            req = urllib.request.Request(OPENROUTER_ENDPOINT, data=data_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    resp_text = response.read().decode("utf-8", errors="replace")
                    resp_json = json.loads(resp_text)
                    
                    track_usage(current_model, status="success")
                    
                    choices = resp_json.get("choices", [])
                    if not choices:
                        err_msg = resp_json.get("error", {}).get("message", "")
                        raise ValueError(f"OpenRouter returned no choices: {err_msg or resp_text}")
                        
                    raw_content = choices[0].get("message", {}).get("content")
                    content = (raw_content or "").strip()
                    if not content and "error" in resp_json:
                        raise ValueError(f"OpenRouter empty content error: {resp_json}")
                        
                    return {
                        "text": content,
                        "model": resp_json.get("model", current_model),
                        "usage": resp_json.get("usage", {}),
                        "raw_response": resp_json
                    }
                    
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                if e.code == 429:
                    track_usage(current_model, status="rate_limited")
                    attempt += 1
                    if attempt > max_retries:
                        sys.stderr.write(f"[OpenRouter 429] Model {current_model} exhausted retries. Trying fallback model...\n")
                        last_error = RuntimeError(f"Rate limited on {current_model}: {err_body}")
                        break
                    backoff_time = initial_backoff * (2 ** (attempt - 1))
                    sys.stderr.write(
                        f"[OpenRouter Rate Limit] Received 429 on {current_model} (attempt {attempt}/{max_retries}). "
                        f"Backing off for {backoff_time:.1f}s before retry...\n"
                    )
                    time.sleep(backoff_time)
                    continue
                elif e.code in (404, 502, 503):
                    sys.stderr.write(f"[OpenRouter {e.code}] Model {current_model} returned {e.reason}. Trying next fallback model...\n")
                    last_error = RuntimeError(f"HTTP {e.code} on {current_model}: {err_body}")
                    break
                else:
                    track_usage(current_model, status=f"error_{e.code}")
                    last_error = RuntimeError(f"OpenRouter HTTP Error {e.code}: {e.reason}. Response: {err_body}")
                    break
            except Exception as e:
                sys.stderr.write(f"[OpenRouter Error] {e} on {current_model}. Trying next fallback model...\n")
                track_usage(current_model, status="failed")
                last_error = e
                break

    if last_error:
        raise last_error
    raise RuntimeError("Unexpected termination of model fallback loop in call_openrouter")

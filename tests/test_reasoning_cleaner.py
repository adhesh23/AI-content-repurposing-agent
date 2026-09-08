import os
import sys
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHAPE_SKILL_DIR = os.path.join(PROJECT_ROOT, ".agent", "skills", "shape-narrative", "scripts")
if SHAPE_SKILL_DIR not in sys.path:
    sys.path.insert(0, SHAPE_SKILL_DIR)

from generate_narrative import clean_generated_post

def test_clean_standard_post():
    """Verify that a clean post with no artifacts passes through intact."""
    raw = (
        "AI agents are scaling at an unprecedented pace.\n\n"
        "Founders need to treat them as untrusted execution environments.\n\n"
        "#AIAgents #CyberSecurity"
    )
    cleaned = clean_generated_post(raw)
    assert cleaned == raw

def test_strip_xml_think_tags():
    """Verify that <think>...</think> tags from reasoning models are removed."""
    raw = (
        "<think>\n"
        "1. Analyze audience: Deep Tech\n"
        "2. Formulate counter-intuitive hook\n"
        "</think>\n\n"
        "We spent months optimizing kernels when our real bottleneck was concrete.\n\n"
        "Civil construction latency is the new infrastructure barrier."
    )
    cleaned = clean_generated_post(raw)
    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    assert "Analyze audience" not in cleaned
    assert cleaned.startswith("We spent months optimizing kernels")

def test_strip_thinking_process_with_separator():
    """Verify that conversational thinking process blocks followed by separators are cleanly stripped."""
    raw = (
        "Here's a thinking process:\n\n"
        "1. **Analyze the Request:** Need a LinkedIn post on AI data centers.\n"
        "2. **Drafting:** Try approach A vs approach B.\n\n"
        "---\n\n"
        "The fastest route to 100MW isn't building faster; it's prefabricating.\n\n"
        "LG Uplus just turned 3-year civil construction into an appliance delivery cycle."
    )
    cleaned = clean_generated_post(raw)
    assert "thinking process" not in cleaned.lower()
    assert "Analyze the Request" not in cleaned
    assert cleaned.startswith("The fastest route to 100MW isn't building faster")

def test_strip_markdown_code_blocks():
    """Verify that markdown code fences (```) are removed."""
    raw = "```\nThis is a post inside a markdown block.\n\nSecond paragraph.\n```"
    cleaned = clean_generated_post(raw)
    assert not cleaned.startswith("```")
    assert not cleaned.endswith("```")
    assert "This is a post inside a markdown block." in cleaned

def test_strip_intro_prefixes():
    """Verify that conversational prefixes like 'Here is the LinkedIn post:' are stripped."""
    raw = "Here is the publish-ready LinkedIn post:\n\nMost founders get context engineering wrong."
    cleaned = clean_generated_post(raw)
    assert cleaned == "Most founders get context engineering wrong."

def test_pure_thinking_trace_raises_value_error():
    """Verify that a response consisting purely of a thinking trace without a post raises ValueError."""
    raw = (
        "Here's a thinking process:\n\n"
        "1. Analyze the request thoroughly\n"
        "2. Draft option 1\n"
        "3. Critique option 1\n"
        "4. Consider word limits"
    )
    with pytest.raises(ValueError, match="Model output contains only internal reasoning trace"):
        clean_generated_post(raw)

def test_empty_string_handling():
    """Verify that empty or None inputs return empty string safely."""
    assert clean_generated_post("") == ""
    assert clean_generated_post(None) == ""

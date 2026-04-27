
import pytest

from src.pipeline.rss_parser import strip_appeared_first_on, validate_and_deduplicate_feeds

def test_strip_appeared_first_on_removes_via_regex():
    
    summary = "Полезный текст статьи. The post Заголовок appeared first on Блог."
    result = strip_appeared_first_on(summary)
    assert "appeared first on" not in result
    assert "Полезный текст статьи" in result

def test_strip_appeared_first_on_removes_via_split():
    
    summary = "Текст статьи appeared first on Название блога."
    result = strip_appeared_first_on(summary)
    assert "appeared first on" not in result
    assert "Текст статьи" in result

def test_strip_appeared_first_on_clean_text_unchanged():
    
    summary = "Обычный текст без лишних фраз."
    result = strip_appeared_first_on(summary)
    assert result == summary

def test_strip_appeared_first_on_empty_string():
    
    assert strip_appeared_first_on("") == ""

def test_strip_appeared_first_on_none():
    
    assert strip_appeared_first_on(None) == ""

def test_validate_feeds_removes_empty_url():
    
    feeds = {"лента1": "https://example.com", "лента2": ""}
    result = validate_and_deduplicate_feeds(feeds)
    assert "лента2" not in result
    assert "лента1" in result

def test_validate_feeds_removes_empty_name():
    
    feeds = {"": "https://example.com", "лента1": "https://other.com"}
    result = validate_and_deduplicate_feeds(feeds)
    assert "" not in result
    assert "лента1" in result

def test_validate_feeds_strips_url_whitespace():
    
    feeds = {"лента1": "  https://example.com  "}
    result = validate_and_deduplicate_feeds(feeds)
    assert result["лента1"] == "https://example.com"

def test_validate_feeds_raises_on_non_dict():
    
    with pytest.raises(ValueError):
        validate_and_deduplicate_feeds(["https://example.com"])

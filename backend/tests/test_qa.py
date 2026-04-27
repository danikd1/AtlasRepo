
from unittest.mock import MagicMock, patch

import pytest

from src.qa.feed_qa import (
    FeedQAOptions,
    FeedQAResult,
    _build_prompt,
    _cosine_sim,
    _strip_leading_citations,
    answer_question_by_feeds,
)
from src.qa.retrieval import RetrievedChunk
from src.qa.rerank import rerank_chunks

def _make_chunk(text_payload="Текст чанка", link="https://example.com", title="Заголовок"):
    return RetrievedChunk(
        collection_id=1,
        link=link,
        chunk_index=0,
        title=title,
        summary="",
        source="example.com",
        published_at=None,
        text_payload=text_payload,
        embed_similarity_to_topic=None,
        distance=0.1,
    )

def test_cosine_sim_identical_vectors():
    
    assert abs(_cosine_sim([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-6

def test_cosine_sim_opposite_vectors():
    
    assert abs(_cosine_sim([1, 0], [-1, 0]) - (-1.0)) < 1e-6

def test_cosine_sim_zero_vector():
    
    assert _cosine_sim([0, 0], [1, 0]) == 0.0

def test_strip_leading_citations_removes_artifact():
    
    text = "[1], [2], [3]\nНормальный ответ про инфляцию."
    result = _strip_leading_citations(text)
    assert result == "Нормальный ответ про инфляцию."

def test_strip_leading_citations_keeps_inline():
    
    text = "Согласно [1] инфляция выросла до 9%."
    result = _strip_leading_citations(text)
    assert result == text

def test_strip_leading_citations_clean_text_unchanged():
    
    text = "Обычный ответ без ссылок на источники."
    result = _strip_leading_citations(text)
    assert result == text

def test_build_prompt_contains_query():
    
    msgs = _build_prompt("Что такое инфляция?", "контекст", language="ru")
    assert "Что такое инфляция?" in msgs[1]["content"]

def test_build_prompt_contains_context():
    
    msgs = _build_prompt("вопрос", "Важный контекст про экономику", language="ru")
    assert "Важный контекст про экономику" in msgs[1]["content"]

def test_build_prompt_russian_language():
    
    msgs = _build_prompt("вопрос", "контекст", language="ru")
    assert "русски" in msgs[1]["content"].lower() or "фрагмент" in msgs[1]["content"].lower()

def test_build_prompt_english_language():
    
    msgs = _build_prompt("question", "context", language="en")
    assert "English" in msgs[1]["content"] or "english" in msgs[1]["content"].lower()

def test_routes_to_inmemory_when_no_rag():
    
    with patch("src.qa.feed_qa.get_connection", return_value=MagicMock()),         patch("src.tools.db_state.get_global_rag_collection", return_value=None),         patch("src.qa.feed_qa._answer_via_inmemory") as mock_inmemory:
        mock_inmemory.return_value = FeedQAResult(answer="ответ", sources=[], article_count=0)
        answer_question_by_feeds("вопрос", feed_ids=[1], user_id=1)
        mock_inmemory.assert_called_once()

def test_routes_to_rag_when_ready():
    
    with patch("src.qa.feed_qa.get_connection", return_value=MagicMock()),         patch("src.tools.db_state.get_global_rag_collection", return_value={"id": 1}),         patch("src.tools.db_state.get_rag_coverage_for_feeds",
               return_value={"total": 42, "indexed": 42}),         patch("src.qa.feed_qa._answer_via_rag") as mock_rag:
        mock_rag.return_value = FeedQAResult(answer="ответ", sources=[], article_count=5)
        answer_question_by_feeds("вопрос", feed_ids=[1], user_id=1)
        mock_rag.assert_called_once()

def test_routes_to_bertopic_rag_when_collection_ready():
    
    with patch("src.qa.feed_qa.get_connection", return_value=MagicMock()),         patch("src.tools.db_state.get_global_rag_collection", return_value={"id": 1}),         patch("src.tools.db_state.get_rag_coverage_for_collection",
               return_value={"total": 10, "indexed": 10}),         patch("src.qa.feed_qa._answer_via_rag_bertopic") as mock_rag_bertopic:
        mock_rag_bertopic.return_value = FeedQAResult(answer="ответ", sources=[], article_count=5)
        answer_question_by_feeds("вопрос", feed_ids=[], collection_id=42, user_id=1)
        mock_rag_bertopic.assert_called_once()

def test_routes_to_bertopic_inmemory_when_not_ready():
    
    with patch("src.qa.feed_qa.get_connection", return_value=MagicMock()),         patch("src.tools.db_state.get_global_rag_collection", return_value={"id": 1}),         patch("src.tools.db_state.get_rag_coverage_for_collection",
               return_value={"total": 10, "indexed": 5}),         patch("src.qa.feed_qa._answer_via_bertopic") as mock_bertopic:
        mock_bertopic.return_value = FeedQAResult(answer="ответ", sources=[], article_count=3)
        answer_question_by_feeds("вопрос", feed_ids=[], collection_id=42, user_id=1)
        mock_bertopic.assert_called_once()

def test_bertopic_rag_empty_chunks_falls_back_to_inmemory():
    
    with patch("src.qa.feed_qa.get_connection", return_value=MagicMock()),         patch("src.tools.db_state.get_global_rag_collection", return_value={"id": 1}),         patch("src.tools.db_state.get_rag_coverage_for_collection",
               return_value={"total": 10, "indexed": 10}),         patch("src.qa.retrieval.embed_query", return_value=("model", [0.1] * 768)),         patch("src.qa.retrieval.retrieve_chunks_by_collection", return_value=[]),         patch("src.qa.feed_qa._answer_via_bertopic") as mock_bertopic:
        mock_bertopic.return_value = FeedQAResult(answer="ответ", sources=[], article_count=0)
        answer_question_by_feeds("вопрос", feed_ids=[], collection_id=42, user_id=1)
        mock_bertopic.assert_called_once()

def test_empty_articles_returns_graceful_message():
    
    with patch("src.qa.feed_qa.get_connection", return_value=MagicMock()),         patch("src.tools.db_state.get_global_rag_collection", return_value=None),         patch("src.qa.feed_qa.get_articles_by_feed_ids", return_value=[]):
        result = answer_question_by_feeds("вопрос", feed_ids=[1], user_id=1)
        assert result.article_count == 0
        assert len(result.answer) > 0

def test_rerank_empty_chunks_returns_empty():
    
    result = rerank_chunks("вопрос", [], top_k_rerank=10)
    assert result == []

def test_rerank_returns_top_k():
    
    chunks = [_make_chunk(f"текст {i}") for i in range(10)]
    mock_model = MagicMock()
    mock_model.predict.return_value = [float(i) for i in range(10)]
    result = rerank_chunks("вопрос", chunks, top_k_rerank=3, model=mock_model)
    assert len(result) == 3

def test_rerank_sorted_by_score_descending():
    
    chunks = [_make_chunk(f"текст {i}") for i in range(5)]
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.1, 0.9, 0.3, 0.7, 0.5]
    result = rerank_chunks("вопрос", chunks, top_k_rerank=5, model=mock_model)
    scores = [r.score for r in result]
    assert scores == sorted(scores, reverse=True)

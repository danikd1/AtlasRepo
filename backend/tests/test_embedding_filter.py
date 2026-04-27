
import numpy as np
import pandas as pd
import pytest
from sentence_transformers import SentenceTransformer

from src.pipeline.embedding_filter import (
    apply_embedding_filter,
    build_topic_embedding_from_descriptions,
    filter_articles_by_embedding,
    get_embedding_model,
)

class TestGetEmbeddingModel:
    

    def test_get_embedding_model_returns_model(self):
        
        model = get_embedding_model()
        assert isinstance(model, SentenceTransformer)

def test_get_embedding_model_custom_name(self):
        

        from config.config import EMBEDDING_MODEL_NAME
        model = get_embedding_model(EMBEDDING_MODEL_NAME)
        assert isinstance(model, SentenceTransformer)

class TestBuildTopicEmbeddingFromDescriptions:
    

    @pytest.fixture
    def model(self):
        
        return get_embedding_model()

@pytest.fixture
    def topic_descriptions(self):
        
        return [
            "Статьи про DevOps метрики и CI/CD пайплайны.",
            "Материалы про процессы доставки и стабильность релизов."
        ]

def test_build_topic_embedding_from_descriptions_shape(self, model, topic_descriptions):
        
        topic_embedding = build_topic_embedding_from_descriptions(topic_descriptions, model)

        assert isinstance(topic_embedding, np.ndarray)
        assert topic_embedding.ndim == 1
        assert topic_embedding.shape[0] > 0

def test_build_topic_embedding_from_descriptions_normalized(self, model, topic_descriptions):
        
        topic_embedding = build_topic_embedding_from_descriptions(topic_descriptions, model)

        norm = np.linalg.norm(topic_embedding)
        assert abs(norm - 1.0) < 1e-6

def test_build_topic_embedding_from_descriptions_empty_raises(self, model):
        
        with pytest.raises(ValueError):
            build_topic_embedding_from_descriptions([], model)

class TestApplyEmbeddingFilter:
    

    @pytest.fixture
    def model(self):
        
        return get_embedding_model()

@pytest.fixture
    def topic_embedding(self, model):
        
        topic_descriptions = [
            "Статьи про DevOps метрики и CI/CD пайплайны.",
            "Материалы про процессы доставки и стабильность релизов."
        ]
        return build_topic_embedding_from_descriptions(topic_descriptions, model)

@pytest.fixture
    def sample_df(self):
        
        return pd.DataFrame({
            "title": ["DevOps метрики и CI/CD", "Как приготовить борщ"],
            "summary": ["Статья о DORA метриках", "Рецепт вкусного супа"]
        })

def test_apply_embedding_filter_adds_columns(self, model, topic_embedding, sample_df):
        
        result = apply_embedding_filter(sample_df, topic_embedding, model)

        assert "embed_similarity" in result.columns
        assert "embed_ok" in result.columns
        assert len(result) == len(sample_df)

def test_apply_embedding_filter_empty_df(self, model, topic_embedding):
        
        empty_df = pd.DataFrame()
        result = apply_embedding_filter(empty_df, topic_embedding, model)

        assert result.empty

def test_apply_embedding_filter_missing_columns(self, model, topic_embedding):
        
        invalid_df = pd.DataFrame({"wrong_column": ["test"]})

        with pytest.raises(ValueError):
            apply_embedding_filter(invalid_df, topic_embedding, model)

def test_apply_embedding_filter_threshold(self, model, topic_embedding, sample_df):
        
        result = apply_embedding_filter(
            sample_df, topic_embedding, model, threshold=0.9
        )

        assert "embed_ok" in result.columns
        assert result["embed_similarity"].min() >= -1.0
        assert result["embed_similarity"].max() <= 1.0

class TestFilterArticlesByEmbedding:
    

    @pytest.fixture
    def model(self):
        
        return get_embedding_model()

@pytest.fixture
    def keywords_config(self):
        
        return {
            "strong": ["dora", "cicd", "devops"],
            "weak": ["agile", "kanban"]
        }

@pytest.fixture
    def topic_descriptions_per_node(self):
        
        descriptions = [
            "Статьи про DevOps метрики и CI/CD пайплайны.",
            "Материалы про процессы доставки и стабильность релизов."
        ]
        return [("A1", descriptions)]

@pytest.fixture
    def sample_df(self):
        
        return pd.DataFrame({
            "title": ["DevOps метрики и CI/CD", "Как приготовить борщ"],
            "summary": ["Статья о DORA метриках", "Рецепт вкусного супа"]
        })

def test_filter_articles_by_embedding_returns_tuple(self, model, keywords_config, topic_descriptions_per_node, sample_df):
        
        df_result, stats = filter_articles_by_embedding(
            sample_df, keywords_config, model, topic_descriptions_per_node=topic_descriptions_per_node
        )

        assert isinstance(df_result, pd.DataFrame)
        assert isinstance(stats, dict)

def test_filter_articles_by_embedding_stats(self, model, keywords_config, topic_descriptions_per_node, sample_df):
        
        df_result, stats = filter_articles_by_embedding(
            sample_df, keywords_config, model, topic_descriptions_per_node=topic_descriptions_per_node
        )

        assert "total_articles" in stats
        assert "passed" in stats
        assert "rejected" in stats
        assert "min_similarity" in stats
        assert "mean_similarity" in stats
        assert "max_similarity" in stats
        assert "time_elapsed_sec" in stats

        assert stats["total_articles"] == len(sample_df)
        assert stats["passed"] + stats["rejected"] == stats["total_articles"]

def test_filter_articles_by_embedding_empty_df(self, model, keywords_config, topic_descriptions_per_node):
        
        empty_df = pd.DataFrame()
        df_result, stats = filter_articles_by_embedding(
            empty_df, keywords_config, model, topic_descriptions_per_node=topic_descriptions_per_node
        )

        assert df_result.empty
        assert stats["total_articles"] == 0
        assert stats["passed"] == 0

def test_filter_articles_by_embedding_missing_columns(self, model, keywords_config, topic_descriptions_per_node):
        
        invalid_df = pd.DataFrame({"wrong_column": ["test"]})

        with pytest.raises(ValueError):
            filter_articles_by_embedding(
                invalid_df, keywords_config, model, topic_descriptions_per_node=topic_descriptions_per_node
            )

def test_filter_articles_by_embedding_empty_topic_descriptions_per_node_raises(self, model, keywords_config, sample_df):
        
        with pytest.raises(ValueError):
            filter_articles_by_embedding(
                sample_df, keywords_config, model, topic_descriptions_per_node=[]
            )



import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from config.config import (
    DEFAULT_EMBED_BATCH_SIZE,
    DEFAULT_EMBED_THRESHOLD,
    EMBEDDING_MODEL_NAME,
)

from ..tools.llm_utils import clean_text_for_llm

logger = logging.getLogger(__name__)

_embedding_model_cache: dict = {}

def get_embedding_model(model_name: str = EMBEDDING_MODEL_NAME) -> SentenceTransformer:
    
    if model_name in _embedding_model_cache:
        return _embedding_model_cache[model_name]
try:
        logger.info(f"Загрузка модели эмбеддингов: {model_name}")
        model = SentenceTransformer(model_name)
        logger.info("✅ Модель загружена")
        _embedding_model_cache[model_name] = model
        return model
except Exception as e:
        error_msg = f"Ошибка загрузки модели эмбеддингов '{model_name}': {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

def build_topic_embedding_from_descriptions(
    descriptions: List[str],
    model: SentenceTransformer,
) -> np.ndarray:
    
    proto_texts = [
        str(t).strip()
        for t in descriptions
        if isinstance(t, str) and t.strip()
    ]
    if not proto_texts:
        raise ValueError("descriptions не содержит ни одной непустой строки")
proto_embs = model.encode(proto_texts, normalize_embeddings=True)
    topic_embedding = proto_embs.mean(axis=0)
    topic_embedding /= np.linalg.norm(topic_embedding)
    return topic_embedding

def apply_embedding_filter(
    df_input: pd.DataFrame,
    topic_embedding: Union[np.ndarray, List[np.ndarray]],
    model: SentenceTransformer,
    text_column: str = "embed_text",
    threshold: float = DEFAULT_EMBED_THRESHOLD,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    show_progress_bar: bool = False
) -> pd.DataFrame:
    
    if df_input is None or df_input.empty:
        logger.warning("Пустой DataFrame на входе embedding-фильтра")
        return pd.DataFrame()

if "title" not in df_input.columns or "summary" not in df_input.columns:
        raise ValueError("DataFrame должен содержать колонки 'title' и 'summary'")

df_input = df_input.copy()

    if text_column not in df_input.columns:
        def _embed_text(row: pd.Series) -> str:
            title = row.get("title") or ""
            summary = row.get("summary") or ""
            combined = f"{title} {summary}"
            cleaned = clean_text_for_llm(combined, max_chars=None)
            return cleaned.lower()

df_input[text_column] = df_input.apply(_embed_text, axis=1)

texts = df_input[text_column].tolist()

    _max_preview = 400
    _num_samples = min(3, len(texts))
    print("\n--- Текст для эмбеддинга статей (образцы) ---")
    for i in range(_num_samples):
        preview = (texts[i] or "")[: _max_preview]
        if len(texts[i] or "") > _max_preview:
            preview += "..."
print(f"  Статья {i + 1}/{len(texts)}: {preview}")
if len(texts) > _num_samples:
        print(f"  ... всего статей: {len(texts)}")
print("---------------------------------------------\n")

    try:

        logger.info(f"Получение эмбеддингов для {len(texts)} статей...")
        article_embeds = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=True
        )

        if isinstance(topic_embedding, list):
            topic_matrix = np.stack(topic_embedding, axis=0)
            dots = np.dot(article_embeds, topic_matrix.T)
            sims = np.max(dots, axis=1)
else:
            sims = np.dot(article_embeds, topic_embedding)

df_input["embed_similarity"] = sims
        df_input["embed_ok"] = df_input["embed_similarity"] >= threshold

        logger.info(f"👉 Всего статей на входе: {len(df_input)}")
        logger.info(f"✅ Прошло эмбеддинг-фильтр: {int(df_input['embed_ok'].sum())}")
        logger.info(f"🔎 min/mean/max: {float(sims.min()):.3f} / {float(sims.mean()):.3f} / {float(sims.max()):.3f}")

        return df_input
except Exception as e:
        error_msg = f"Ошибка при генерации эмбеддингов статей: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

def filter_articles_by_embedding(
    df: pd.DataFrame,
    keywords_config: Dict[str, List[str]],
    model: SentenceTransformer,
    topic_descriptions_per_node: List[Tuple[str, List[str]]],
    threshold: float = DEFAULT_EMBED_THRESHOLD,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE
) -> Tuple[pd.DataFrame, Dict]:
    
    import time
    start_time = time.time()

    if df is None or df.empty:
        return pd.DataFrame(), {
            "total_articles": 0,
            "passed": 0,
            "rejected": 0,
            "min_similarity": 0.0,
            "mean_similarity": 0.0,
            "max_similarity": 0.0,
            "time_elapsed_sec": 0
        }

if "title" not in df.columns or "summary" not in df.columns:
        raise ValueError("DataFrame должен содержать колонки 'title' и 'summary'")

if not topic_descriptions_per_node:
        raise ValueError(
            "topic_descriptions_per_node не должен быть пустым: нужен хотя бы один узел с описаниями топика"
        )

node_id, descriptions = topic_descriptions_per_node[-1]

    print("\n--- Текст для эмбеддинга узла (topic) ---")
    print(f"  Узел: {node_id}")
    for idx, d in enumerate(descriptions, 1):
        print(f"  Описание {idx}: {(d or '').strip()}")
print("-----------------------------------------\n")
    logger.info("Построение topic embedding для самого специфичного узла: %s", node_id)
    topic_embedding = build_topic_embedding_from_descriptions(descriptions, model)

    df_filtered = apply_embedding_filter(
        df,
        topic_embedding,
        model=model,
        threshold=threshold,
        batch_size=batch_size
    )

    df_pass = df_filtered[df_filtered["embed_ok"] == True].copy()
    df_rejected = df_filtered[df_filtered["embed_ok"] == False].copy()

    end_time = time.time()
    elapsed = end_time - start_time

    stats = {
        "total_articles": len(df),
        "passed": len(df_pass),
        "rejected": len(df_rejected),
        "min_similarity": float(df_filtered["embed_similarity"].min()) if len(df_filtered) > 0 else 0.0,
        "mean_similarity": float(df_filtered["embed_similarity"].mean()) if len(df_filtered) > 0 else 0.0,
        "max_similarity": float(df_filtered["embed_similarity"].max()) if len(df_filtered) > 0 else 0.0,
        "time_elapsed_sec": elapsed
    }

    logger.info(f"Фильтрация завершена: {len(df_pass)}/{len(df)} статей прошло фильтр")

    return df_pass, stats

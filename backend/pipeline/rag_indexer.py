
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

def index_pending_articles(conn, batch_size: int = 50) -> dict:
    
    from src.tools.db_state import (
        get_or_create_global_rag_collection,
        get_articles_for_rag_indexing,
        mark_articles_rag_indexed,
        delete_rag_documents_by_links,
        upsert_rag_documents,
    )
    from src.tools.translation import strip_html
    from src.pipeline.chunking import chunk_text_recursive
    from src.pipeline.embedding_filter import get_embedding_model
    from config.config import RAG_CHUNK_MAX_TOKENS, RAG_CHUNK_OVERLAP_TOKENS, DEFAULT_EMBED_BATCH_SIZE

    indexed = 0
    chunks_created = 0
    failed = 0

    collection = get_or_create_global_rag_collection(conn)
    if collection is None:
        logger.error("RAG indexer: не удалось получить/создать глобальную коллекцию.")
        return {"indexed": 0, "chunks_created": 0, "failed": 0}

collection_id = collection["id"]
    articles = get_articles_for_rag_indexing(conn, limit=batch_size)

    if not articles:
        return {"indexed": 0, "chunks_created": 0, "failed": 0}

print(f"\n[rag-indexer] Индексируем {len(articles)} статей...", flush=True)

    model = get_embedding_model()

    tokenizer = None
    try:
        tokenizer = model.tokenizer
except AttributeError:
        pass
if tokenizer is None:
        try:
            tokenizer = model[0].tokenizer
except Exception:
            pass
if tokenizer is None:
        try:
            from transformers import AutoTokenizer
            from config.config import EMBEDDING_MODEL_NAME
            tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
except Exception as e:
            logger.warning("Токенайзер для чанкирования недоступен, используем приближение по символам: %s", e)

all_docs: list[dict] = []
    article_ids_ok: list[int] = []

    from src.pipeline.chunking import count_tokens

    for article in articles:
        article_id = article["id"]
        link = article["link"]
        title = (article.get("title") or "").strip()
        summary = (article.get("summary") or "").strip()
        source = (article.get("source") or "").strip()
        published_at = article.get("published_at")
        full_text = article.get("full_text") or ""
        summary = article.get("summary") or ""

        try:
            clean = strip_html(full_text) if full_text else ""
            if not clean.strip():

                clean = summary.strip()
if not clean.strip():

                failed += 1
                continue

title_tokens = count_tokens(title, tokenizer) + 2
            chunk_max = max(32, RAG_CHUNK_MAX_TOKENS - title_tokens)

            chunks = chunk_text_recursive(
                clean,
                tokenizer=tokenizer,
                max_tokens=chunk_max,
                overlap_tokens=RAG_CHUNK_OVERLAP_TOKENS,
            )
            if not chunks:
                chunks = [clean[:2048]]

for chunk_index, chunk_text in enumerate(chunks):

                text_payload = f"{title}\n\n{chunk_text}" if title and chunk_text else chunk_text or title or " "
                all_docs.append({
                    "link": link,
                    "chunk_index": chunk_index,
                    "title": title,
                    "summary": summary,
                    "source": source,
                    "published_at": published_at,
                    "text_payload": text_payload,
                    "_article_id": article_id,
                })
article_ids_ok.append(article_id)
except Exception as e:
            logger.warning("RAG indexer: ошибка при чанкировании article_id=%s: %s", article_id, e)
            failed += 1

if not all_docs:
        if article_ids_ok:
            mark_articles_rag_indexed(conn, article_ids_ok)
print(f"[rag-indexer] Нет чанков для индексации.", flush=True)
        return {"indexed": indexed, "chunks_created": chunks_created, "failed": failed}

if tokenizer is not None:
        for doc in all_docs:
            ids = tokenizer.encode(
                doc["text_payload"],
                add_special_tokens=False,
                truncation=True,
                max_length=RAG_CHUNK_MAX_TOKENS,
            )
            if len(ids) >= RAG_CHUNK_MAX_TOKENS:
                doc["text_payload"] = tokenizer.decode(ids, skip_special_tokens=True)

texts = [d["text_payload"] for d in all_docs]
    embeddings = model.encode(
        texts,
        batch_size=DEFAULT_EMBED_BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    for i, doc in enumerate(all_docs):
        doc["embedding"] = embeddings[i].tolist()

links_to_replace = list({d["link"] for d in all_docs})
    delete_rag_documents_by_links(conn, collection_id, links_to_replace)

    docs_for_upsert = [{k: v for k, v in d.items() if k != "_article_id"} for d in all_docs]

    count = upsert_rag_documents(
        conn,
        collection_id=collection_id,
        discipline=None,
        ga=None,
        activity=None,
        documents=docs_for_upsert,
    )
    chunks_created += count
    indexed += len(article_ids_ok)

    if article_ids_ok:
        mark_articles_rag_indexed(conn, article_ids_ok)

print(
        f"[rag-indexer] Готово: Проиндексировано статей: {indexed} | Чанков создано: {chunks_created} | Ошибок: {failed}",
        flush=True,
    )
    logger.info(
        "RAG worker: завершён. Проиндексировано: %d | Чанков: %d | Ошибок: %d",
        indexed, chunks_created, failed,
    )
    return {"indexed": indexed, "chunks_created": chunks_created, "failed": failed}

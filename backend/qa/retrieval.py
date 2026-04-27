
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg2

from config.config import (
    EMBEDDING_MODEL_NAME,
    POSTGRES_ENABLED,
    POSTGRES_TABLE_PROCESSED_ARTICLES,
    POSTGRES_TABLE_RAG_DOCUMENTS,
)
from src.pipeline.embedding_filter import get_embedding_model
from src.tools.db_state import get_connection

@dataclass
class RetrievedChunk:
    collection_id: int
    link: str
    chunk_index: int
    title: str
    summary: str
    source: str
    published_at: Optional[datetime]
    text_payload: str
    embed_similarity_to_topic: Optional[float]
    distance: float
    article_id: int = 0

def _embedding_to_vector_str(embedding: Sequence[float]) -> str:
    
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"

def embed_query(
    query: str,
    model: Optional[Any] = None,
) -> Tuple[Any, List[float]]:
    
    if model is None:
        model = get_embedding_model(EMBEDDING_MODEL_NAME)

emb = model.encode([query], normalize_embeddings=True)[0]
    return model, emb.tolist()

def retrieve_chunks(
    conn,
    query_embedding: Sequence[float],
    collection_id: int,
    top_k: int = 30,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[RetrievedChunk]:
    
    if conn is None or not POSTGRES_ENABLED:
        return []
if not query_embedding:
        return []

emb_str = _embedding_to_vector_str(query_embedding)

    conditions = ["collection_id = %s"]
    params: List[Any] = [collection_id]

    if date_from is not None:
        conditions.append("published_at >= %s")
        params.append(date_from)
if date_to is not None:
        conditions.append("published_at <= %s")
        params.append(date_to)

where_clause = " AND ".join(conditions)

    params_for_query = [emb_str] + params + [emb_str, top_k]

    sql = f"""
        SELECT
            collection_id,
            link,
            chunk_index,
            title,
            summary,
            source,
            published_at,
            text_payload,
            embed_similarity_to_topic,
            (embedding <-> %s::vector) AS distance
        FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
        WHERE {where_clause}
        ORDER BY embedding <-> %s::vector
        LIMIT %s;
    """

    chunks: List[RetrievedChunk] = []
    with conn.cursor() as cur:
        cur.execute(sql, params_for_query)
        rows = cur.fetchall()
        for row in rows:
            chunks.append(
                RetrievedChunk(
                    collection_id=row["collection_id"],
                    link=row["link"],
                    chunk_index=row["chunk_index"],
                    title=row.get("title") or "",
                    summary=row.get("summary") or "",
                    source=row.get("source") or "",
                    published_at=row.get("published_at"),
                    text_payload=row.get("text_payload") or "",
                    embed_similarity_to_topic=row.get("embed_similarity_to_topic"),
                    distance=float(row["distance"]) if row.get("distance") is not None else 0.0,
                )
            )
return chunks

def retrieve_chunks_by_feeds(
    conn,
    query_embedding: Sequence[float],
    collection_id: int,
    feed_ids: List[int],
    user_id: int,
    top_k: int = 40,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[RetrievedChunk]:
    
    if conn is None or not POSTGRES_ENABLED:
        return []
if not query_embedding or not feed_ids:
        return []

emb_str = _embedding_to_vector_str(query_embedding)

    conditions = ["rd.collection_id = %s", "pa.feed_id = ANY(%s)"]
    params: List[Any] = [collection_id, feed_ids]

    if date_from is not None:
        conditions.append("rd.published_at >= %s")
        params.append(date_from)
if date_to is not None:
        conditions.append("rd.published_at <= %s")
        params.append(date_to)

where_clause = " AND ".join(conditions)
    params_for_query = [emb_str] + [user_id] + params + [emb_str, top_k]

    sql = f"""
        SELECT
            rd.collection_id,
            rd.link,
            rd.chunk_index,
            rd.title,
            rd.summary,
            rd.source,
            rd.published_at,
            rd.text_payload,
            rd.embed_similarity_to_topic,
            (rd.embedding <-> %s::vector) AS distance,
            pa.id AS article_id
        FROM {POSTGRES_TABLE_RAG_DOCUMENTS} rd
        JOIN {POSTGRES_TABLE_PROCESSED_ARTICLES} pa ON pa.link = rd.link
        JOIN user_feeds uf ON uf.feed_id = pa.feed_id AND uf.user_id = %s
        WHERE {where_clause}
        ORDER BY rd.embedding <-> %s::vector
        LIMIT %s;
    """

    chunks: List[RetrievedChunk] = []
    with conn.cursor() as cur:
        cur.execute(sql, params_for_query)
        rows = cur.fetchall()
        for row in rows:
            chunks.append(
                RetrievedChunk(
                    collection_id=row["collection_id"],
                    link=row["link"],
                    chunk_index=row["chunk_index"],
                    title=row.get("title") or "",
                    summary=row.get("summary") or "",
                    source=row.get("source") or "",
                    published_at=row.get("published_at"),
                    text_payload=row.get("text_payload") or "",
                    embed_similarity_to_topic=row.get("embed_similarity_to_topic"),
                    distance=float(row["distance"]) if row.get("distance") is not None else 0.0,
                    article_id=int(row["article_id"]) if row.get("article_id") else 0,
                )
            )
return chunks

def retrieve_chunks_by_collection(
    conn,
    query_embedding: Sequence[float],
    rag_collection_id: int,
    bertopic_collection_id: int,
    top_k: int = 40,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[RetrievedChunk]:
    
    if conn is None or not POSTGRES_ENABLED or not query_embedding:
        return []

emb_str = _embedding_to_vector_str(query_embedding)
    conditions = ["rd.collection_id = %s"]
    params: List[Any] = [rag_collection_id]

    if date_from is not None:
        conditions.append("rd.published_at >= %s")
        params.append(date_from)
if date_to is not None:
        conditions.append("rd.published_at <= %s")
        params.append(date_to)

where_clause = " AND ".join(conditions)
    params_for_query = [emb_str, bertopic_collection_id] + params + [emb_str, top_k]

    sql = f"""
        SELECT
            rd.collection_id,
            rd.link,
            rd.chunk_index,
            rd.title,
            rd.summary,
            rd.source,
            rd.published_at,
            rd.text_payload,
            rd.embed_similarity_to_topic,
            (rd.embedding <-> %s::vector) AS distance,
            pa.id AS article_id
        FROM {POSTGRES_TABLE_RAG_DOCUMENTS} rd
        JOIN {POSTGRES_TABLE_PROCESSED_ARTICLES} pa ON pa.link = rd.link
        JOIN collections c ON c.id = %s
        JOIN bertopic_assignments ba ON ba.link = rd.link
            AND ba.topic_id = c.bertopic_topic_id
            AND ba.owner_id = c.owner_id
        WHERE {where_clause}
        ORDER BY rd.embedding <-> %s::vector
        LIMIT %s;
    """

    chunks: List[RetrievedChunk] = []
    with conn.cursor() as cur:
        cur.execute(sql, params_for_query)
        for row in cur.fetchall():
            chunks.append(
                RetrievedChunk(
                    collection_id=row["collection_id"],
                    link=row["link"],
                    chunk_index=row["chunk_index"],
                    title=row.get("title") or "",
                    summary=row.get("summary") or "",
                    source=row.get("source") or "",
                    published_at=row.get("published_at"),
                    text_payload=row.get("text_payload") or "",
                    embed_similarity_to_topic=row.get("embed_similarity_to_topic"),
                    distance=float(row["distance"]) if row.get("distance") is not None else 0.0,
                    article_id=int(row["article_id"]) if row.get("article_id") else 0,
                )
            )
return chunks

def print_retrieved_chunks(
    query: str,
    collection_id: int,
    top_k: int = 10,
    snippet_chars: int = 300,
) -> None:
    
    conn = get_connection()
    if conn is None:
        print("PostgreSQL отключён или недоступен (POSTGRES_ENABLED=False или нет подключения).")
        return

model, q_emb = embed_query(query)
    chunks = retrieve_chunks(conn, q_emb, collection_id=collection_id, top_k=top_k)

    print(f"Query: {query!r}, collection_id={collection_id}, top_k={top_k}")
    print(f"Found chunks: {len(chunks)}")
    print("-" * 80)
    for idx, ch in enumerate(chunks, 1):
        snippet = ch.text_payload.replace("\n", " ")[:snippet_chars]
        print(f"[{idx}] distance={ch.distance:.4f} link={ch.link} chunk_index={ch.chunk_index}")
        if ch.title:
            print(f"     title: {ch.title}")
if ch.published_at:
            print(f"     published_at: {ch.published_at}")
print(f"     snippet: {snippet}")
        print("-" * 80)

def _parse_args(argv: Sequence[str]) -> Optional[Tuple[str, int, int]]:
    
    if len(argv) < 3:
        return None
query = argv[1]
    try:
        collection_id = int(argv[2])
except ValueError:
        return None
top_k = 10
    if len(argv) >= 4:
        try:
            top_k = int(argv[3])
except ValueError:
            top_k = 10
return query, collection_id, top_k

if __name__ == "__main__":
    import sys

    parsed = _parse_args(sys.argv)
    if not parsed:
        print("Usage: python -m src.qa.retrieval \"your question\" <collection_id> [top_k]")
        sys.exit(1)
q, cid, k = parsed
    print_retrieved_chunks(q, cid, top_k=k)


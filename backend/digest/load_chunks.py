
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

from config.config import (
    POSTGRES_ENABLED,
    POSTGRES_TABLE_RAG_DOCUMENTS,
)
from src.tools.db_state import get_connection

def _embedding_from_row(row: Any) -> Optional[List[float]]:
    
    emb = row.get("embedding")
    if emb is None:
        return None
if isinstance(emb, (list, tuple)):
        return [float(x) for x in emb]
if isinstance(emb, str):

        s = emb.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
if not s:
            return None
return [float(x.strip()) for x in s.split(",")]
return None

@dataclass
class ChunkRow:
    
    id: int
    collection_id: int
    link: str
    chunk_index: int
    title: str
    summary: str
    source: str
    published_at: Optional[datetime]
    text_payload: str
    embed_similarity_to_topic: Optional[float]
    embedding: Optional[List[float]]

def load_chunks_for_collection(
    conn,
    collection_id: int,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> List[ChunkRow]:
    
    if conn is None or not POSTGRES_ENABLED:
        return []

conditions = ["collection_id = %s", "embedding IS NOT NULL"]
    params: List[Any] = [collection_id]
    if from_date is not None:
        conditions.append("published_at >= %s")
        params.append(from_date)
if to_date is not None:
        conditions.append("published_at <= %s")
        params.append(to_date)
where = " AND ".join(conditions)

    sql = f"""
        SELECT id, collection_id, link, chunk_index, title, summary, source,
               published_at, text_payload, embed_similarity_to_topic, embedding
        FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
        WHERE {where}
        ORDER BY link, chunk_index;
    """
    out: List[ChunkRow] = []
    with conn.cursor() as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            emb = _embedding_from_row(row)
            if emb is None:
                continue
out.append(
                ChunkRow(
                    id=row["id"],
                    collection_id=row["collection_id"],
                    link=row["link"] or "",
                    chunk_index=int(row["chunk_index"] or 0),
                    title=(row.get("title") or "").strip(),
                    summary=(row.get("summary") or "").strip(),
                    source=(row.get("source") or "").strip(),
                    published_at=row.get("published_at"),
                    text_payload=(row.get("text_payload") or "").strip(),
                    embed_similarity_to_topic=row.get("embed_similarity_to_topic"),
                    embedding=emb,
                )
            )
return out

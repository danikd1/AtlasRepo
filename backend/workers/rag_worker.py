
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

class _NoStatusFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /status" not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(_NoStatusFilter())

POLL_INTERVAL_SEC = int(os.environ.get("RAG_POLL_INTERVAL_SEC", 30))

_state: dict = {
    "running": False,
    "paused": False,
    "last_run_at": None,
    "last_result": None,
    "error": None,
}
_lock = threading.Lock()
_run_event = threading.Event()
_pause_event = threading.Event()
_pause_event.set()

def _do_indexing() -> None:
    from src.tools.db_state import get_connection
    from src.pipeline.rag_indexer import index_pending_articles

    _state["running"] = True
    _state["error"] = None
    logger.info("RAG worker: начинаем индексацию...")

    total_indexed = 0
    total_chunks = 0

    try:
        conn = get_connection()

        while True:

            _pause_event.wait(timeout=3600)
            if not _pause_event.is_set():

                logger.warning("RAG worker: пауза длилась >1 часа, снимаем автоматически.")
                _pause_event.set()
                _state["paused"] = False

result = index_pending_articles(conn)
            total_indexed += result["indexed"]
            total_chunks += result["chunks_created"]

            if result["indexed"] == 0:

                break

_state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_result"] = {"indexed": total_indexed, "chunks_created": total_chunks}
        logger.info("RAG worker: завершён. Проиндексировано: %d | Чанков: %d", total_indexed, total_chunks)

except Exception as e:
        logger.exception("RAG worker: ошибка: %s", e)
        _state["error"] = str(e)
finally:
        _state["running"] = False

        _pause_event.set()
        _state["paused"] = False

def _worker_loop() -> None:
    
    while True:
        _run_event.wait(timeout=POLL_INTERVAL_SEC)
        _run_event.clear()

        if not _lock.acquire(blocking=False):
            logger.info("RAG worker: уже запущен, пропускаем.")
            continue

try:
            _do_indexing()
finally:
            _lock.release()

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.tools.db_state import get_connection, ensure_tables
    conn = get_connection()
    ensure_tables(conn)
    logger.info("RAG worker: БД подключена.")

    t = threading.Thread(target=_worker_loop, daemon=True, name="rag-loop")
    t.start()
    logger.info("RAG worker: цикл запущен, интервал %d сек.", POLL_INTERVAL_SEC)
    yield

app = FastAPI(title="RAG Indexer Worker", lifespan=lifespan)

@app.get("/status")
def status():
    
    from src.tools.db_state import get_connection, get_rag_stats
    try:
        conn = get_connection()
        rag = get_rag_stats(conn)
except Exception:
        rag = {"indexed": None, "pending": None, "total_chunks": None}
return {**_state, **rag}

@app.post("/run")
def run():
    
    if _state["running"]:
        return {"started": False, "reason": "already running"}
_run_event.set()
    return {"started": True}

@app.post("/pause")
def pause():
    
    _pause_event.clear()
    _state["paused"] = True
    logger.info("RAG worker: поставлен на паузу.")
    return {"paused": True}

@app.post("/resume")
def resume():
    
    _pause_event.set()
    _state["paused"] = False
    logger.info("RAG worker: снят с паузы.")
    return {"paused": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

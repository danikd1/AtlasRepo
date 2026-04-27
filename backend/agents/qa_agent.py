

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from src.qa.answer import AnswerOptions, AnswerResult, answer_question

logger = logging.getLogger(__name__)

@dataclass
class QAState:
    user_query: str
    collection_id: int
    options: Optional[dict[str, Any]] = None
    answer_result: Optional[dict[str, Any]] = None
    status: str = "pending"
    error: Optional[str] = None

def _qa_node(state: dict[str, Any]) -> dict[str, Any]:
    
    try:
        user_query = state.get("user_query", "")
        collection_id = int(state.get("collection_id"))
except Exception as e:
        logger.exception("QA-агент: некорректный collection_id: %s", e)
        return {
            **state,
            "status": "error",
            "error": f"Некорректный collection_id: {e}",
            "answer_result": None,
        }

raw_options = state.get("options") or {}
    try:
        options = AnswerOptions(**raw_options)
except TypeError as e:
        logger.warning("QA-агент: не удалось распарсить options, используем дефолты: %s", e)
        options = AnswerOptions()

try:
        res: AnswerResult = answer_question(user_query, collection_id, options)

        answer_dict = {
            "answer": res.answer,
            "collection": res.collection,
            "fragments": [asdict(doc) for doc in res.fragments],
            "sources": res.sources,
        }
        new_state = {
            **state,
            "answer_result": answer_dict,
            "status": "ok",
            "error": None,
        }
        return new_state
except Exception as e:
        logger.exception("QA-агент: ошибка при вызове answer_question: %s", e)
        return {
            **state,
            "status": "error",
            "error": str(e),
            "answer_result": None,
        }

def _build_qa_graph():
    
    workflow = StateGraph(dict)
    workflow.add_node("qa", _qa_node)
    workflow.add_edge(START, "qa")
    workflow.add_edge("qa", END)
    return workflow.compile()

def run_qa_agent(
    user_query: str,
    collection_id: int,
    options: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    
    graph = _build_qa_graph()
    initial: dict[str, Any] = {
        "user_query": user_query,
        "collection_id": collection_id,
        "options": options or {},
        "answer_result": None,
        "status": "pending",
        "error": None,
    }
    result = graph.invoke(initial)
    return result

if __name__ == "__main__":
    
    import sys

    if len(sys.argv) < 3:
        print("Использование: python3 -m src.agents.qa_agent \"ваш вопрос\" <collection_id>", file=sys.stderr)
        sys.exit(1)
question = sys.argv[1]
    try:
        cid = int(sys.argv[2])
except ValueError:
        print("collection_id должен быть целым числом", file=sys.stderr)
        sys.exit(1)

out = run_qa_agent(question, cid)
    print("STATUS:", out.get("status"))
    if out.get("error"):
        print("ERROR:", out["error"])
result = out.get("answer_result") or {}
    print("\nANSWER:")
    print(result.get("answer", ""))
    print("\nSOURCES:")
    for i, d in enumerate(result.get("context_docs") or [], 1):
        print(f"[{i}] {d.get('title', '')} ({d.get('link', '')})")


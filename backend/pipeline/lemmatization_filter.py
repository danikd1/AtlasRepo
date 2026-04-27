
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pymorphy3 import MorphAnalyzer

from .taxonomy import get_keywords_config_for_selection, load_taxonomy

logger = logging.getLogger(__name__)

_morph_analyzer = None

def get_morph_analyzer() -> MorphAnalyzer:
    
    global _morph_analyzer
    if _morph_analyzer is None:
        try:
            _morph_analyzer = MorphAnalyzer()
except Exception as e:
            logger.error(f"Ошибка инициализации морфологического анализатора: {e}")
            raise
return _morph_analyzer

def tokenize(text: str) -> List[str]:
    
    if not text:
        return []
return re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text.lower())

def lemmatize_token(token: str) -> str:
    
    if not token:
        return token

try:
        morph = get_morph_analyzer()
        p = morph.parse(token)
        if not p:
            return token
return p[0].normal_form
except Exception as e:
        logger.debug(f"Ошибка лемматизации токена '{token}': {e}")
        return token

def lemmatize_text(text: str) -> str:
    
    if not text:
        return ""

tokens = tokenize(text)
    lemmas = [lemmatize_token(t) for t in tokens]
    return " ".join(lemmas)

def lemmatize_phrase(phrase: str) -> str:
    
    if not phrase:
        return ""

tokens = tokenize(phrase)
    lemmas = [lemmatize_token(t) for t in tokens]
    return " ".join(lemmas)

def prepare_strong_lemmas_for_bool_filter(
    strong_keywords: List[str],
    generic_single_lemmas: Optional[set] = None
) -> Tuple[List[str], List[str]]:
    
    if generic_single_lemmas is None:
        from config.config import GENERIC_SINGLE_LEMMAS
        generic_single_lemmas = GENERIC_SINGLE_LEMMAS

strong_lemmas = [lemmatize_phrase(k) for k in strong_keywords]

    strong_lemmas_for_bool = [
        lemma for lemma in strong_lemmas
        if not (len(lemma.split()) == 1 and lemma in generic_single_lemmas)
    ]

    return strong_lemmas, strong_lemmas_for_bool

def bool_filter_lemmas(
    title: str,
    summary: str,
    strong_lemmas_for_bool: List[str],
    blacklist_lemmas: Optional[List[str]] = None,
    use_blacklist: bool = False
) -> Tuple[bool, Dict[str, str]]:
    
    raw_text = (title or "") + " " + (summary or "")
    lem_text = lemmatize_text(raw_text)

    if use_blacklist and blacklist_lemmas:
        for bad_lemma in blacklist_lemmas:
            if bad_lemma and bad_lemma in lem_text:
                return False, {"reason": f"blacklist lemma matched: {bad_lemma}"}

for good_lemma in strong_lemmas_for_bool:
        if good_lemma and good_lemma in lem_text:
            return True, {"reason": f"strong lemma matched: {good_lemma}"}

return False, {"reason": "no strong lemmas found"}

def _apply_filter_to_row(
    row: pd.Series,
    strong_lemmas_for_bool: List[str],
    blacklist_lemmas: Optional[List[str]],
    use_blacklist: bool
) -> Tuple[bool, str]:
    
    try:
        title = row.get("title", "")
        summary = row.get("summary", "")

        result, reason_dict = bool_filter_lemmas(
            title,
            summary,
            strong_lemmas_for_bool,
            blacklist_lemmas,
            use_blacklist
        )
        return result, reason_dict["reason"]
except Exception as e:
        logger.warning(f"Ошибка обработки статьи: {e}")
        return False, f"error: {str(e)[:50]}"

def filter_articles_by_keywords(
    df: pd.DataFrame,
    keywords_config: Optional[Dict[str, List[str]]] = None,
    generic_single_lemmas: Optional[set] = None,
    use_blacklist: bool = False
) -> Tuple[pd.DataFrame, Dict]:
    
    start_time = time.time()

    if df is None or df.empty:
        return pd.DataFrame(), {
            "total_articles": 0,
            "passed": 0,
            "blacklisted": 0,
            "strong_matches": 0,
            "weak_matches": 0,
            "time_elapsed_sec": 0,
            "strong_lemmas_total": 0,
            "strong_lemmas_for_bool": 0,
            "errors": 0
        }

if "title" not in df.columns or "summary" not in df.columns:
        raise ValueError("DataFrame должен содержать колонки 'title' и 'summary'")

if keywords_config is None:
        from config.config import TAXONOMY_SELECTION
        taxonomy = load_taxonomy()
        keywords_config = get_keywords_config_for_selection(taxonomy, TAXONOMY_SELECTION)

strong_keywords = keywords_config.get("strong", [])
    weak_keywords = keywords_config.get("weak", [])
    blacklist_keywords = keywords_config.get("blacklist", [])

    logger.info("Лемматизация ключевых слов...")
    strong_lemmas, strong_lemmas_for_bool = prepare_strong_lemmas_for_bool_filter(
        strong_keywords,
        generic_single_lemmas
    )

    blacklist_lemmas = [lemmatize_phrase(k) for k in blacklist_keywords] if use_blacklist else []

    logger.info(f"Всего strong-лемм: {len(strong_lemmas)}, для фильтра: {len(strong_lemmas_for_bool)}")

    logger.info(f"Применение Boolean-фильтра к {len(df)} статьям...")
    df = df.copy()

    filter_results = df.apply(
        lambda row: _apply_filter_to_row(
            row,
            strong_lemmas_for_bool,
            blacklist_lemmas if use_blacklist else None,
            use_blacklist
        ),
        axis=1
    )

    df["bool_lemma_result"] = filter_results.apply(lambda x: x[0])
    df["bool_lemma_reason"] = filter_results.apply(lambda x: x[1])

    errors = len(df[df["bool_lemma_reason"].str.startswith("error:", na=False)])

    df_pass = df[df["bool_lemma_result"] == True].copy()

    end_time = time.time()
    elapsed = end_time - start_time

    total_articles = len(df)
    passed = len(df_pass)

    blacklisted = 0
    if use_blacklist and len(df) > 0:
        blacklisted = len(df[df["bool_lemma_reason"].str.contains("blacklist", na=False, case=False)])

stats = {
        "total_articles": total_articles,
        "passed": passed,
        "blacklisted": blacklisted,
        "strong_matches": passed,
        "weak_matches": 0,
        "time_elapsed_sec": elapsed,
        "strong_lemmas_total": len(strong_lemmas),
        "strong_lemmas_for_bool": len(strong_lemmas_for_bool),
        "errors": errors
    }

    logger.info(f"Фильтрация завершена: {passed}/{total_articles} статей прошло фильтр (ошибок: {errors})")

    return df_pass, stats

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    test_df = pd.DataFrame({
        "title": ["Тестирование и DevOps метрики"],
        "summary": ["Статья о метриках DORA и CI/CD"]
    })

    df_filtered, stats = filter_articles_by_keywords(test_df)
    print(f"Статистика: {stats}")
    print(f"Результат: {df_filtered}")

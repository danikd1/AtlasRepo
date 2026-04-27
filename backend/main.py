
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .pipeline.embedding_filter import filter_articles_by_embedding, get_embedding_model
from .pipeline.lemmatization_filter import filter_articles_by_keywords
from .pipeline.taxonomy import get_keywords_config_for_selection, get_topic_descriptions_per_node, load_taxonomy
from .tools.llm_utils import create_gigachat_client, format_summary_text, summarize_article

from .pipeline.rss_parser import collect_articles_for_window
from .tools.db_state import (
    get_connection,
    get_or_create_collection,
    load_articles_for_window,
    update_collection_last_refreshed,
)
from .tools.rate_limiter import RateLimiter
from .tools.text_extraction import add_full_text_column
from config.config import (
    DEFAULT_EMBED_THRESHOLD,
    EMBED_RELEVANT_THRESHOLD,
    DEFAULT_HOURS_BACK,
    DEFAULT_LIMIT_PER_FEED,
    DEFAULT_LLM_SLEEP,
    GENERIC_SINGLE_LEMMAS,
    get_feed_urls,
    TAXONOMY_SELECTION,
)

def _resolve_taxonomy_selection(override: Optional[dict] = None) -> dict:
    
    if override is not None:
        return {
            "discipline": override.get("discipline"),
            "ga": override.get("ga"),
            "activity": override.get("activity"),
        }
return TAXONOMY_SELECTION

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

GREEN = "\033[32m"
RESET = "\033[0m"

def collect_rss(
    hours_back: Optional[int] = None,
    limit_per_feed: Optional[int] = None,
    rss_feeds: Optional[dict] = None,
) -> dict:
    
    _hours_back = hours_back if hours_back is not None else DEFAULT_HOURS_BACK
    _limit = limit_per_feed if limit_per_feed is not None else DEFAULT_LIMIT_PER_FEED
    _feeds = rss_feeds if rss_feeds is not None else get_feed_urls()

    print("=" * 60)
    print("СБОР СТАТЕЙ ИЗ RSS-ЛЕНТ")
    print("=" * 60)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Лент: {len(_feeds)}, глубина: {_hours_back} ч, лимит на ленту: {_limit}")
    print()

    start = time.time()
    df_articles, stats = collect_articles_for_window(
        _hours_back,
        limit_per_feed=_limit,
        rss_feeds=_feeds,
    )
    elapsed = time.time() - start

    per_feed_new = stats.get("per_feed_new_count", {})
    for name in sorted(_feeds.keys()):
        count = per_feed_new.get(name, 0)
        prefix = f"{GREEN}" if count > 0 else ""
        suffix = f"{RESET}" if count > 0 else ""
        print(f"   {prefix}{name} — новых: {count}{suffix}")
print()
    print(f"Итого новых статей: {stats['unique_articles']}  |  время: {elapsed:.2f} сек")
    print("=" * 60)

    return stats

def run_pipeline(
    taxonomy_selection_override: Optional[dict] = None,
    collection_name: Optional[str] = None,
):
    
    selection = _resolve_taxonomy_selection(taxonomy_selection_override)
    pipeline_start = time.time()

    print("=" * 60)
    print("ЗАПУСК ПАЙПЛАЙНА ОБРАБОТКИ СТАТЕЙ")
    print("=" * 60)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = get_connection()
    if conn is not None:
        df_for_pipeline = load_articles_for_window(conn, DEFAULT_HOURS_BACK)
else:
        df_for_pipeline = __import__("pandas").DataFrame()

stats_rss = {
        "unique_articles": 0,
        "total_parsed": 0,
        "duplicates_skipped": 0,
        "already_processed_skipped": 0,
        "feeds_failed": 0,
        "per_feed_new_count": {},
    }

    print(f"   Статей в окне {DEFAULT_HOURS_BACK} ч из БД: {len(df_for_pipeline)}")
    print()
    for _, row in df_for_pipeline.iterrows():
        source = row.get("source", "")
        title = row.get("title", "")
        link = row.get("link", "")
        print(f"   {source} | {title} | {link}")
print()

    print("[Этап 2] Фильтрация по ключевым словам (лемматизация)...")
    stage2_start = time.time()
    taxonomy = load_taxonomy()

    collection = get_or_create_collection(
        conn,
        selection,
        taxonomy,
        collection_name=collection_name,
    )
    if collection:
        print(f"   Коллекция: {collection['name']} (id={collection['id']})")
keywords_config = get_keywords_config_for_selection(taxonomy, selection)
    df_filtered, stats_keywords = filter_articles_by_keywords(
        df_for_pipeline,
        keywords_config=keywords_config,
        generic_single_lemmas=GENERIC_SINGLE_LEMMAS
    )

    stage2_time = time.time() - stage2_start
    print(f"   Завершено за {stage2_time:.2f} сек")
    print(f"   Статей прошло фильтр: {stats_keywords['passed']}")
    print()

    passed_links = set(df_filtered["link"]) if not df_filtered.empty else set()
    link_to_reason = dict(zip(df_filtered["link"], df_filtered["bool_lemma_reason"])) if not df_filtered.empty else {}
    for _, row in df_for_pipeline.iterrows():
        title = row.get("title", "")
        source = row.get("source", "")
        link = row.get("link", "")
        is_passed = link in passed_links
        prefix = f"{GREEN}+ " if is_passed else "   "
        suffix = f"{RESET}" if is_passed else ""
        reason = link_to_reason.get(link, "")
        if reason.startswith("strong lemma matched: "):
            match_keyword = reason.replace("strong lemma matched: ", "", 1)
            print(f"   {prefix}{title} | {source}{suffix}  ← ключ: {match_keyword}")
else:
            print(f"   {prefix}{title} | {source}{suffix}")
print()

    print("[Этап 3] Фильтрация по эмбеддингам (семантическое сходство)...")
    stage3_start = time.time()
    topic_descriptions_per_node = get_topic_descriptions_per_node(taxonomy, selection)
    embed_model = get_embedding_model()
    df_embedding, stats_embedding = filter_articles_by_embedding(
        df_filtered,
        keywords_config=keywords_config,
        model=embed_model,
        topic_descriptions_per_node=topic_descriptions_per_node,
        threshold=DEFAULT_EMBED_THRESHOLD
    )

    stage3_time = time.time() - stage3_start
    print(f"   Завершено за {stage3_time:.2f} сек")
    print(f"   Статей прошло фильтр: {stats_embedding['passed']}")
    print()

    embedding_passed_links = set(df_embedding["link"]) if not df_embedding.empty else set()
    for _, row in df_filtered.iterrows():
        title = row.get("title", "")
        source = row.get("source", "")
        link = row.get("link", "")
        is_passed = link in embedding_passed_links
        prefix = f"{GREEN}" if is_passed else ""
        suffix = f"{RESET}" if is_passed else ""
        print(f"   {prefix}{title} | {source}{suffix}")
print()

    print(f"Отбор статей выше порога сходства (>= {EMBED_RELEVANT_THRESHOLD}):")
    df_embedding_sorted = df_embedding.sort_values("embed_similarity", ascending=False)
    df_above_threshold = df_embedding_sorted[
        df_embedding_sorted["embed_similarity"] >= EMBED_RELEVANT_THRESHOLD
    ].copy()
    print(f"   Отобрано статей: {len(df_above_threshold)}")
    print()

    above_threshold_links = set(df_above_threshold["link"]) if not df_above_threshold.empty else set()
    for rank, (_, row) in enumerate(df_embedding_sorted.iterrows(), 1):
        title = row.get("title", "")
        source = row.get("source", "")
        link = row.get("link", "")
        sim = row.get("embed_similarity", 0)
        in_relevant = link in above_threshold_links
        prefix = f"{GREEN}" if in_relevant else ""
        suffix = f"{RESET}" if in_relevant else ""
        print(f"   {prefix}{rank}. {title} | {source} (сходство: {sim:.3f}){suffix}")
print()

    print("[Этап 4] Извлечение полного текста статей...")
    stage4_start = time.time()

    df_with_text = add_full_text_column(df_above_threshold)

    stage4_time = time.time() - stage4_start
    successful_texts = sum(1 for t in df_with_text["full_text"] if t is not None)
    print(f"   Завершено за {stage4_time:.2f} сек")
    print(f"   Успешно извлечено текстов: {successful_texts}/{len(df_with_text)}")
    print()

    df_relevant = df_with_text

    print("[Этап 6] Суммаризация статей...")
    stage6_start = time.time()

    giga_client = create_gigachat_client()
    rate_limiter = RateLimiter(delay_seconds=DEFAULT_LLM_SLEEP)

    summaries = []
    total_relevant = len(df_relevant)

    for idx, (_, row) in enumerate(df_relevant.iterrows(), 1):
        title = row["title"]
        full_text = row.get("full_text")

        if full_text is None:
            logger.warning(f"Пропуск статьи {idx} без текста: {title[:50]}...")
            summaries.append("Не удалось получить текст статьи для суммаризации.")
            continue

print(f"   ▶ Суммаризация [{idx}/{total_relevant}]: {title[:60]}...")
        summary = summarize_article(
            title=title,
            full_text=full_text,
            client=giga_client,
            rate_limiter=rate_limiter
        )
        summaries.append(summary)

df_relevant["summary"] = summaries

    stage6_time = time.time() - stage6_start
    print(f"   Завершено за {stage6_time:.2f} сек")
    print(f"   Суммаризировано статей: {len(summaries)}")
    print()

    project_root = Path(__file__).parent.parent
    outputs_dir = project_root / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    output_file = outputs_dir / "articles_filtered.csv"
    df_relevant.to_csv(output_file, index=False, encoding='utf-8')

    if collection and collection.get("id"):
        update_collection_last_refreshed(conn, collection["id"])

if conn and collection and not df_relevant.empty:
        try:
            from .pipeline.rag_prep import prepare_and_upsert_rag_documents
            rag_count = prepare_and_upsert_rag_documents(
                conn, collection, df_relevant, model=embed_model
            )
            if rag_count > 0:
                print(f"   RAG: записано документов в коллекцию: {rag_count}")
except Exception as e:
            logger.warning("Не удалось записать RAG-документы (проверьте pgvector и таблицу rag_documents): %s", e)

total_time = time.time() - pipeline_start

    print("=" * 60)
    print("ИТОГОВАЯ СВОДКА ПАЙПЛАЙНА")
    print("=" * 60)
    print(f"[Источник] Статей из БД (окно {DEFAULT_HOURS_BACK} ч): {len(df_for_pipeline)}")
    print("   Подсказка: для обновления данных из RSS вызовите POST /api/rss/collect")
    print()
    print("[Этап 2] Фильтрация по ключевым словам (лемматизация):")
    print(f"   Всего статей на входе: {stats_keywords['total_articles']}")
    print(f"   Прошло фильтр: {stats_keywords['passed']}")
    print()
    print("[Этап 3] Фильтрация по эмбеддингам:")
    print(f"   Всего статей на входе: {stats_embedding['total_articles']}")
    print(f"   Прошло фильтр: {stats_embedding['passed']}")
    print(f"   Отклонено: {stats_embedding['rejected']}")
    print(f"   Сходство: min={stats_embedding['min_similarity']:.3f}, "
          f"mean={stats_embedding['mean_similarity']:.3f}, max={stats_embedding['max_similarity']:.3f}")
    print()
    print(f"Отбор выше порога сходства (>= {EMBED_RELEVANT_THRESHOLD}):")
    print(f"   Отобрано статей: {len(df_above_threshold)}")
    if len(df_above_threshold) > 0:
        top_similarity = df_above_threshold["embed_similarity"].max()
        min_similarity = df_above_threshold["embed_similarity"].min()
        print(f"   Диапазон сходства: {min_similarity:.3f} - {top_similarity:.3f}")
print()
    print("[Этап 4] Извлечение полного текста:")
    print(f"   Всего статей: {len(df_with_text)}")
    print(f"   Успешно извлечено: {successful_texts}")
    print()
    print("[Этап 6] Суммаризация:")
    print(f"   Суммаризировано статей: {len(summaries)}")
    print()
    print(f"Общее время выполнения: {total_time:.2f} сек ({total_time/60:.2f} мин)")
    print(f"Результат сохранён: {output_file}")
    if collection and collection.get("id"):
        print(f"Коллекция обновлена: {collection.get('name', '')} (id={collection['id']})")
print("="*60)

    if len(df_relevant) > 0:
        print("\n" + "="*60)
        print("ОТОБРАННЫЕ СТАТЬИ")
        print("="*60 + "\n")

        for i, (_, row) in enumerate(df_relevant.iterrows(), 1):
            title = row["title"]
            link = row["link"]
            summary = row["summary"]
            similarity = row.get("embed_similarity", 0.0)

            formatted_summary = format_summary_text(summary, width=95)

            print("─" * 60)
            print(f"[{i}] {title}")
            print(f"    {link}")
            print(f"    Сходство: {similarity:.3f}\n")
            print("    Аннотация:\n")
            print(formatted_summary)
            print("\n")

return df_relevant


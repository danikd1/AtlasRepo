
import calendar
import logging
import re
import socket
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.error import URLError

import feedparser
import pandas as pd

from ..tools.db_state import (
    ensure_tables,
    get_connection,
    get_existing_links,
    get_feeds_as_dict,
    load_feed_states,
    load_feed_url_id_map,
    update_feed_states_from_seen,
    update_feed_status,
    update_state_with_articles,
)
logger = logging.getLogger(__name__)

def validate_and_deduplicate_feeds(rss_feeds: Dict[str, str]) -> Dict[str, str]:
    
    if not isinstance(rss_feeds, dict):
        raise ValueError("rss_feeds должен быть словарем")

seen_keys = set()
    duplicates = []

    for key in rss_feeds.keys():
        if key in seen_keys:
            duplicates.append(key)
seen_keys.add(key)

if duplicates:
        logger.warning(
            f"Обнаружены дубликаты ключей в RSS feeds: {duplicates}. "
            f"Будут использованы последние значения."
        )

cleaned_feeds = {}
    for name, url in rss_feeds.items():
        if not isinstance(name, str) or not name.strip():
            logger.warning(f"Пропущен некорректный ключ: {name}")
            continue
if not isinstance(url, str) or not url.strip():
            logger.warning(f"Пропущен некорректный URL для '{name}': {url}")
            continue
cleaned_feeds[name] = url.strip()

return cleaned_feeds

_RE_STRIP_APPEARED_FIRST = re.compile(
    r"\s*The post\s+.+?appeared first on\s+.+$",
    re.IGNORECASE | re.DOTALL,
)

def strip_appeared_first_on(summary: str) -> str:
    
    if not summary or not isinstance(summary, str):
        return summary or ""
s = summary.strip()
    cleaned = _RE_STRIP_APPEARED_FIRST.sub("", s).strip()
    if cleaned != s:
        return cleaned or s
if " appeared first on " in s:
        return s.split(" appeared first on ")[0].strip() or s
return s

def parse_rss(
    feed_url: str,
    limit: int = 30,
    hours_back: Optional[int] = None,
    min_published_dt: Optional[datetime] = None,
    max_retries: int = 3,
    retry_delay: int = 2,
    timeout: int = 30
) -> List[Dict]:
    

    entries: List[Dict] = []
    cutoff_dt = None

    cutoff_from_hours = None
    if hours_back is not None:
        if hours_back < 0:
            raise ValueError("hours_back должен быть неотрицательным")

now = datetime.now(timezone.utc)
        cutoff_from_hours = now - timedelta(hours=hours_back)

if min_published_dt is not None:
        if min_published_dt.tzinfo is None:

            min_published_dt = min_published_dt.replace(tzinfo=timezone.utc)

if min_published_dt is not None and cutoff_from_hours is not None:
        cutoff_dt = max(min_published_dt, cutoff_from_hours)
elif min_published_dt is not None:
        cutoff_dt = min_published_dt
elif cutoff_from_hours is not None:
        cutoff_dt = cutoff_from_hours

cutoff_exclusive = min_published_dt is not None

    last_error = None
    for attempt in range(max_retries):
        try:

            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(timeout)
            try:
                feed = feedparser.parse(feed_url)
finally:
                socket.setdefaulttimeout(old_timeout)

if hasattr(feed, 'bozo') and feed.bozo:
                error_msg = getattr(feed, 'bozo_exception', 'Unknown parsing error')
                logger.warning(f"Ошибка парсинга RSS {feed_url}: {error_msg}")

for entry in feed.entries:
                try:

                    pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")

                    if cutoff_exclusive and pub_struct is None:
                        continue

if cutoff_dt is not None and pub_struct is not None:
                        try:
                            timestamp = calendar.timegm(pub_struct)
                            pub_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

                            if cutoff_exclusive:
                                if pub_dt <= cutoff_dt:
                                    continue
else:
                                if pub_dt < cutoff_dt:
                                    continue
except (ValueError, OSError) as e:
                            logger.debug(f"Ошибка обработки даты для статьи: {e}")

                            continue

title = entry.get("title", "")
                    link = entry.get("link", "").strip()
                    published = entry.get("published", "—")
                    summary = strip_appeared_first_on(entry.get("summary", "Без описания"))

                    if not title or not link:
                        logger.debug(f"Пропущена статья без title или link: {link}")
                        continue

article = {
                        "title": title,
                        "link": link,
                        "published": published,
                        "summary": summary,
                        "published_dt": pub_dt if "pub_dt" in locals() else None,
                    }
                    entries.append(article)

                    if limit is not None and len(entries) >= limit:
                        break

except Exception as e:
                    logger.debug(f"Ошибка обработки записи из RSS: {e}")
                    continue

return entries

except (URLError, socket.timeout, socket.gaierror, ConnectionError) as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Ошибка сети при парсинге {feed_url} (попытка {attempt + 1}/{max_retries}): {e}. "
                    f"Повтор через {retry_delay} сек..."
                )
                time.sleep(retry_delay)
else:
                logger.error(f"Не удалось распарсить {feed_url} после {max_retries} попыток: {e}")
except Exception as e:

            logger.error(f"Неожиданная ошибка при парсинге {feed_url}: {e}")
            break

return entries

def collect_articles_for_window(
    hours_back: int,
    limit_per_feed: int = 30,
    rss_feeds: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    retry_delay: int = 2
) -> Tuple[pd.DataFrame, Dict]:
    
    from config.config import SUMMARY_TRUNCATE_MAX_CHARS, SUMMARY_TRUNCATE_SOURCE_PREFIXES

    if rss_feeds is None:
        _conn_tmp = get_connection()
        ensure_tables(_conn_tmp)
        db_feeds = get_feeds_as_dict(_conn_tmp)
        if db_feeds:
            rss_feeds = db_feeds
            logger.info("RSS: используем %d лент из БД (user_feeds)", len(rss_feeds))
else:
            from config.config import get_feed_urls
            rss_feeds = get_feed_urls()
            logger.info("RSS: user_feeds пустая, используем %d лент из config", len(rss_feeds))

rss_feeds = validate_and_deduplicate_feeds(rss_feeds)

    if not rss_feeds:
        logger.warning("Список RSS-лент пуст")
        return pd.DataFrame(), {
            "total_parsed": 0,
            "unique_articles": 0,
            "duplicates_skipped": 0,
            "already_processed_skipped": 0,
            "time_elapsed_sec": 0,
            "hours_back": hours_back,
            "feeds_processed": 0,
            "feeds_failed": 0
        }

conn = get_connection()
    ensure_tables(conn)

    feed_states = load_feed_states(conn)

    feed_url_id_map = load_feed_url_id_map(conn)

    all_articles = []
    seen_links = set()
    total_parsed = 0
    skipped_duplicates = 0
    skipped_already_processed = 0
    feeds_failed = 0
    per_feed_max_published: Dict[str, datetime] = {}
    per_feed_new_count: Dict[str, int] = {}

    start_time = time.time()

    for name, url in rss_feeds.items():
        try:

            min_published_dt = feed_states.get(name)
            if min_published_dt:
                logger.debug(
                    f"Источник '{name}': используем last_processed_published_at = {min_published_dt}"
                )

logger.info("Парсинг RSS-ленты '%s' (%s)...", name, url)

            articles = parse_rss(
                url,
                limit=limit_per_feed,
                hours_back=hours_back,
                min_published_dt=min_published_dt,
                max_retries=max_retries,
                retry_delay=retry_delay
            )

            for art in articles:
                total_parsed += 1
                link = art["link"]

                pub_dt = art.get("published_dt")
                if pub_dt is not None and name:
                    current = per_feed_max_published.get(name)
                    if current is None or pub_dt > current:
                        per_feed_max_published[name] = pub_dt

art["source"] = name

                art["feed_id"] = feed_url_id_map.get(url)

                if SUMMARY_TRUNCATE_SOURCE_PREFIXES and any(
                    name.startswith(p) for p in SUMMARY_TRUNCATE_SOURCE_PREFIXES
                ):
                    s = (art.get("summary") or "")
                    if len(s) > SUMMARY_TRUNCATE_MAX_CHARS:
                        art["summary"] = s[:SUMMARY_TRUNCATE_MAX_CHARS].strip()

if link in seen_links:
                    skipped_duplicates += 1
                    continue

seen_links.add(link)
                all_articles.append(art)

update_feed_status(conn, url, error=None)
except Exception as e:
            feeds_failed += 1
            logger.error(f"Критическая ошибка при обработке ленты '{name}' ({url}): {e}")
            update_feed_status(conn, url, error=str(e))
            continue

candidate_links = [art["link"] for art in all_articles]
    existing_in_db = get_existing_links(conn, candidate_links)
    new_articles = [art for art in all_articles if art["link"] not in existing_in_db]
    skipped_already_processed = len(all_articles) - len(new_articles)

    for art in new_articles:
        name = art.get("source", "")
        per_feed_new_count[name] = per_feed_new_count.get(name, 0) + 1

end_time = time.time()
    elapsed = end_time - start_time

    update_state_with_articles(conn, new_articles)

    update_feed_states_from_seen(conn, per_feed_max_published)

    df = pd.DataFrame(new_articles)

    stats = {
        "total_parsed": total_parsed,
        "unique_articles": len(df),
        "duplicates_skipped": skipped_duplicates,
        "already_processed_skipped": skipped_already_processed,
        "time_elapsed_sec": elapsed,
        "hours_back": hours_back,
        "feeds_processed": len(rss_feeds),
        "feeds_failed": feeds_failed,
        "per_feed_new_count": per_feed_new_count,
    }

    return df, stats

def main():
    
    from config import get_feed_urls, DEFAULT_HOURS_BACK, DEFAULT_LIMIT_PER_FEED
    _feed_urls = get_feed_urls()

    print("🚀 Запуск пайплайна сбора статей с Habr...")
    print(f"📡 Обработка {len(_feed_urls)} RSS-лент...")

    df_articles, stats = collect_articles_for_window(
        DEFAULT_HOURS_BACK,
        limit_per_feed=DEFAULT_LIMIT_PER_FEED,
        rss_feeds=_feed_urls
    )

    output_file = "articles_collected.csv"
    df_articles.to_csv(output_file, index=False, encoding='utf-8')

    print("\n" + "="*60)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("="*60)
    print(f"✅ Уникальных статей собрано: {stats['unique_articles']}")
    print(f"📝 Всего попыток добавления: {stats['total_parsed']}")
    print(f"🔄 Дубликатов отброшено: {stats['duplicates_skipped']}")
    if stats['feeds_failed'] > 0:
        print(f"⚠️  Лент с ошибками: {stats['feeds_failed']}")
print(f"⏱️  Время выполнения: {stats['time_elapsed_sec']:.2f} сек ({stats['time_elapsed_sec']/60:.2f} мин)")
    print(f"💾 Результат сохранен в: {output_file}")
    print("="*60)

    return df_articles, stats

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()


import logging
import re
from typing import Optional

from bs4 import BeautifulSoup
from gigachat import GigaChat

from config.config import (
    BART_SUMMARIZATION_MODEL,
    BART_SUMMARY_MAX_LENGTH,
    BART_SUMMARY_MIN_LENGTH,
    DEFAULT_SUMMARY_MAX_CHARS,
    DEFAULT_SUMMARY_TEMPERATURE,
    DEFAULT_TEXT_CLEAN_MAX_CHARS,
    GIGACHAT_CREDENTIALS,
    GIGACHAT_MODEL,
    GIGACHAT_SUMMARIZATION_ENABLED,
    GIGACHAT_VERIFY_SSL,
)
from .prompt_loader import format_prompt, load_prompt
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_bart_pipeline = None

def _get_bart_pipeline():
    
    global _bart_pipeline
    if _bart_pipeline is None:
        try:
            from transformers import pipeline
            logger.info("Загрузка BART fallback модели: %s", BART_SUMMARIZATION_MODEL)
            _bart_pipeline = pipeline(
                "summarization",
                model=BART_SUMMARIZATION_MODEL,
                truncation=True,
            )
            logger.info("✅ BART модель загружена")
except Exception as e:
            logger.error("Не удалось загрузить BART модель: %s", e)
            raise RuntimeError(f"BART fallback недоступен: {e}") from e
return _bart_pipeline

def _summarize_with_bart(title: str, text: str, max_chars: int = 4000) -> str:
    
    bart = _get_bart_pipeline()

    combined = f"{title}. {text}" if title else text
    combined = combined[:max_chars]

    result = bart(
        combined,
        max_new_tokens=BART_SUMMARY_MAX_LENGTH,
        min_new_tokens=BART_SUMMARY_MIN_LENGTH,
        do_sample=False,
    )
    return result[0]["summary_text"].strip()

def create_gigachat_client(credentials: Optional[str] = None, model: Optional[str] = None) -> GigaChat:
    
    if credentials is None:
        raise ValueError("GigaChat не настроен. Укажите credentials в профиле.")

import asyncio
    try:
        asyncio.get_event_loop()
except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

effective_model = model or GIGACHAT_MODEL

    try:
        logger.info(f"Инициализация GigaChat клиента (модель: {effective_model})...")
        client = GigaChat(
            credentials=credentials,
            verify_ssl_certs=GIGACHAT_VERIFY_SSL,
            model=effective_model,
            timeout=120,
        )
        logger.info("✅ GigaChat клиент инициализирован")
        return client
except Exception as e:
        error_msg = f"Ошибка инициализации GigaChat клиента: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

def clean_text_for_llm(text: str, max_chars: int = DEFAULT_TEXT_CLEAN_MAX_CHARS) -> str:
    
    if not isinstance(text, str) or len(text.strip()) == 0:
        return ""

try:

        soup = BeautifulSoup(text, "lxml")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

cleaned = soup.get_text(separator="\n")
except Exception:

        cleaned = text

cleaned = re.sub(r"[ \t]+", " ", cleaned)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    cleaned = cleaned.strip()

    if max_chars is not None and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n\n[TEXT TRUNCATED]"

return cleaned

def summarize_article(
    title: str,
    full_text: str,
    client: Optional[GigaChat] = None,
    rate_limiter: Optional[RateLimiter] = None,
    max_chars: int = DEFAULT_SUMMARY_MAX_CHARS,
    temperature: float = DEFAULT_SUMMARY_TEMPERATURE,
) -> str:
    
    if not isinstance(full_text, str) or not full_text.strip():
        return "Не удалось получить текст статьи для суммаризации."

cleaned = clean_text_for_llm(full_text, max_chars=max_chars)

    if GIGACHAT_SUMMARIZATION_ENABLED:
        if client is None:
            logger.warning("GigaChat включён, но client не передан — переключаемся на BART.")
else:
            system_prompt = load_prompt("summary_system")
            user_prompt_template = load_prompt("summary_user")
            user_prompt = format_prompt(user_prompt_template, title=title, cleaned_text=cleaned)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            if rate_limiter:
                rate_limiter.wait_if_needed()

try:
                result = client.chat({"messages": messages, "temperature": temperature})
                return result.choices[0].message.content.strip()
except Exception as e:
                logger.warning(
                    "GigaChat недоступен для статьи '%s': %s — переключаемся на BART.",
                    title[:50],
                    e,
                )
else:
        logger.info("GigaChat отключён (GIGACHAT_SUMMARIZATION_ENABLED=False) — используем BART.")

try:
        summary = _summarize_with_bart(title, cleaned)
        logger.info("BART fallback успешно сработал для '%s'", title[:50])
        return summary
except Exception as e:
        logger.error("BART fallback тоже недоступен для '%s': %s", title[:50], e)
        return "Ошибка при суммаризации статьи (GigaChat и BART недоступны)."

FEED_CATEGORIES = [
    "AI & ML",
    "Engineering",
    "Cloud & DevOps",
    "Data",
    "Security",
    "Design",
    "Tools",
    "Management",
    "Tech News",
    "Case Studies",
]

def suggest_feed_category(name: str, description: str, url: str, credentials: Optional[str] = None, model: Optional[str] = None) -> Optional[str]:
    
    try:
        categories_list = "\n".join(f"- {c}" for c in FEED_CATEGORIES)
        prompt = (
            f"Определи категорию для RSS-ленты. Выбери одну категорию из списка ниже.\n\n"
            f"Лента:\n"
            f"- Название: {name}\n"
            f"- Описание: {description or 'не указано'}\n"
            f"- URL: {url}\n\n"
            f"Доступные категории:\n{categories_list}\n\n"
            f"Ответь одной строкой — только названием категории из списка, без пояснений."
        )
        client = create_gigachat_client(credentials=credentials, model=model)
        with client:
            from gigachat.models import Chat, Messages, MessagesRole
            response = client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    temperature=0.0,
                    max_tokens=20,
                )
            )
result = response.choices[0].message.content.strip()

        if result in FEED_CATEGORIES:
            return result

for cat in FEED_CATEGORIES:
            if cat.lower() in result.lower() or result.lower() in cat.lower():
                return cat
logger.warning("GigaChat вернул неизвестную категорию: '%s'", result)
        return None
except Exception as e:
        logger.warning("Не удалось определить категорию через GigaChat: %s", e)
        return None

def generate_feed_description(name: str, url: str, titles: list, credentials: Optional[str] = None, model: Optional[str] = None) -> Optional[str]:
    
    if not titles:
        return None
try:
        titles_text = "\n".join(f"- {t}" for t in titles[:10])
        prompt = (
            f"Напиши описание RSS-ленты одним коротким предложением на русском языке.\n"
            f"Описание должно объяснять о чём эта лента — какие темы она освещает.\n"
            f"Не упоминай название ленты в описании.\n\n"
            f"Лента: {name}\n"
            f"URL: {url}\n\n"
            f"Последние заголовки статей:\n{titles_text}\n\n"
            f"Ответь только одним предложением, без пояснений."
        )
        client = create_gigachat_client(credentials=credentials, model=model)
        with client:
            from gigachat.models import Chat, Messages, MessagesRole
            response = client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    temperature=0.3,
                    max_tokens=100,
                )
            )
return response.choices[0].message.content.strip()
except Exception as e:
        logger.warning("Не удалось сгенерировать описание ленты через GigaChat: %s", e)
        return None

def generate_feed_descriptions_batch(feeds: list) -> dict:
    
    if not feeds:
        return {}
try:
        feeds_text = ""
        for i, feed in enumerate(feeds, 1):
            titles_text = "\n".join(f"  - {t}" for t in feed["titles"][:10])
            feeds_text += (
                f"Лента {i}:\n"
                f"  Название: {feed['name']}\n"
                f"  URL: {feed['url']}\n"
                f"  Заголовки статей:\n{titles_text}\n\n"
            )
prompt = (
            f"Для каждой ленты напиши описание одним коротким предложением на русском языке.\n"
            f"Описание должно объяснять о чём лента — какие темы она освещает.\n"
            f"Не упоминай название ленты в описании.\n\n"
            f"{feeds_text}"
            f"Ответь строго в формате JSON-массива:\n"
            f'[{{"index": 1, "description": "..."}}, {{"index": 2, "description": "..."}}, ...]'
        )
        from config.config import GIGACHAT_CREDENTIALS, GIGACHAT_MODEL
        client = create_gigachat_client(credentials=GIGACHAT_CREDENTIALS, model=GIGACHAT_MODEL)
        with client:
            from gigachat.models import Chat, Messages, MessagesRole
            response = client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    temperature=0.3,
                    max_tokens=2000,
                )
            )
import json, re
        raw = response.choices[0].message.content.strip()

        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            logger.warning("generate_feed_descriptions_batch: не удалось найти JSON в ответе")
            return {}
items = json.loads(match.group())
        result = {}
        for item in items:
            idx = item.get("index", 0) - 1
            if 0 <= idx < len(feeds) and item.get("description"):
                result[feeds[idx]["id"]] = item["description"].strip()
return result
except Exception as e:
        logger.warning("generate_feed_descriptions_batch: ошибка GigaChat: %s", e)
        return {}

def format_summary_text(summary: str, width: int = 100) -> str:
    
    import textwrap

    paragraphs = summary.split("\n")

    formatted = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            formatted.append("")
else:
            wrapped = textwrap.fill(p, width=width)
            formatted.append(wrapped)

return "\n".join(formatted)

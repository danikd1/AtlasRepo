

from __future__ import annotations
import re
from html import escape
from typing import Optional

MODEL_NAME = "Helsinki-NLP/opus-mt-en-ru"

_model = None
_tokenizer = None

def _get_translator():
    global _model, _tokenizer
    if _model is None:
        from transformers import MarianMTModel, MarianTokenizer
        _tokenizer = MarianTokenizer.from_pretrained(MODEL_NAME)
        _model = MarianMTModel.from_pretrained(MODEL_NAME)
return _model, _tokenizer

def _split_into_chunks(text: str, max_words: int = 200) -> list[str]:
    

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = len(sentence.split())
        if current_words + words > max_words and current:
            chunks.append(" ".join(current))
            current = [sentence]
            current_words = words
else:
            current.append(sentence)
            current_words += words

if current:
        chunks.append(" ".join(current))

return chunks or [text]

def _is_garbage(text: str) -> bool:
    
    if len(text) < 10:
        return False

sample = text[:200].upper()
    words = sample.split()
    if len(words) < 4:
        return False

unique = len(set(words))
    return unique / len(words) < 0.4

def _translate_chunk(text: str, model, tokenizer) -> str:
    
    inputs = tokenizer(
        [text],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )
    translated = model.generate(
        **inputs,
        num_beams=4,
        repetition_penalty=3.0,
        no_repeat_ngram_size=4,
        max_new_tokens=512,
    )
    result = tokenizer.decode(translated[0], skip_special_tokens=True)

    if _is_garbage(result):
        return text
return result

def translate_text(text: str) -> str:
    
    if not text or not text.strip():
        return text

model, tokenizer = _get_translator()
    chunks = _split_into_chunks(text)
    translated_chunks = [_translate_chunk(chunk, model, tokenizer) for chunk in chunks]
    return " ".join(translated_chunks)

_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "figcaption", "blockquote"}

def _translate_html_tag(tag) -> None:
    
    from bs4 import NavigableString, Tag
    for child in list(tag.children):
        if not isinstance(child, Tag):
            continue
if child.name == "img":
            continue
if child.name in _BLOCK_TAGS:
            text = child.get_text(strip=True)
            if text:
                child.clear()
                child.append(NavigableString(translate_text(text)))
else:
            _translate_html_tag(child)

def translate_html_structure(html: str) -> str:
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    _translate_html_tag(soup)
    return str(soup)

def strip_html(html: str) -> str:
    
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["p", "br", "h1", "h2", "h3", "h4", "li"]):
            tag.append("\n")
return soup.get_text(separator=" ").strip()
except Exception:

        return re.sub(r"<[^>]+>", " ", html).strip()

def translate_article(
    title: Optional[str],
    summary: Optional[str],
    full_text: Optional[str],
) -> dict:
    
    result: dict = {}

    result["title"] = translate_text(title) if title else None
    result["summary"] = translate_text(summary) if summary else None

    if full_text:
        if re.search(r"<[a-z][\s\S]*>", full_text, re.IGNORECASE):

            result["full_text"] = translate_html_structure(full_text)
else:

            translated_plain = translate_text(full_text)
            paragraphs = [p.strip() for p in translated_plain.split("\n") if p.strip()]
            result["full_text"] = "\n".join(f"<p>{escape(p)}</p>" for p in paragraphs)
else:
        result["full_text"] = None

return result

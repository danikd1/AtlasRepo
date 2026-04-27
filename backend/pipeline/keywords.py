
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def get_keywords_file_path(config_file: Optional[str] = None) -> Path:
    
    if config_file:
        return Path(config_file)

project_root = Path(__file__).parent.parent
    data_path = project_root / "data" / "keywords.json"
    root_path = project_root / "keywords.json"

    if data_path.exists():
        return data_path
elif root_path.exists():
        return root_path
else:
        return data_path

def normalize_keywords_list(keywords: List[str]) -> List[str]:
    
    if not keywords:
        return []

normalized = []
    seen = set()

    for keyword in keywords:
        if not isinstance(keyword, str):
            continue

normalized_keyword = keyword.lower().strip()
        if normalized_keyword and normalized_keyword not in seen:
            seen.add(normalized_keyword)
            normalized.append(normalized_keyword)

return sorted(normalized)

def load_keywords_config(config_file: Optional[str] = None) -> Dict[str, List[str]]:
    
    keywords_path = get_keywords_file_path(config_file)

    try:
        with open(keywords_path, "r", encoding="utf-8") as f:
            config = json.load(f)
except FileNotFoundError:
        logger.error(f"Файл конфигурации не найден: {keywords_path}")
        raise
except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в {keywords_path}: {e}")
        raise

required_keys = {"strong", "weak", "blacklist"}
    if not all(key in config for key in required_keys):
        missing = required_keys - set(config.keys())
        raise ValueError(f"В конфигурации отсутствуют ключи: {missing}")

normalized_config = {}
    for key in required_keys:
        keywords = config.get(key, [])
        normalized_config[key] = normalize_keywords_list(keywords)

logger.info(f"Загружена конфигурация ключевых слов: strong={len(normalized_config['strong'])}, "
                f"weak={len(normalized_config['weak'])}, blacklist={len(normalized_config['blacklist'])}")

    return normalized_config

def save_keywords_config(
    keywords_config: Dict[str, List[str]],
    output_file: Optional[str] = None
) -> Path:
    
    output_path = get_keywords_file_path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_config = {}
    for key in ["strong", "weak", "blacklist"]:
        keywords = keywords_config.get(key, [])
        normalized_config[key] = normalize_keywords_list(keywords)

with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_config, f, ensure_ascii=False, indent=2)

logger.info(f"Конфигурация ключевых слов сохранена в {output_path}")
    return output_path

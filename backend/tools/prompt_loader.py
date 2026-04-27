
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_prompts_data: Optional[Dict] = None

def get_prompts_file() -> Path:
    
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "prompts.json"

def _load_prompts_data() -> Dict:
    
    global _prompts_data
    if _prompts_data is not None:
        return _prompts_data

prompts_file = get_prompts_file()

    if not prompts_file.exists():
        error_msg = f"Файл промптов не найден: {prompts_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

try:
        with open(prompts_file, "r", encoding="utf-8") as f:
            _prompts_data = json.load(f)
logger.debug(f"Загружены промпты из {prompts_file}")
        return _prompts_data
except json.JSONDecodeError as e:
        error_msg = f"Ошибка парсинга JSON в {prompts_file}: {e}"
        logger.error(error_msg)
        raise
except Exception as e:
        error_msg = f"Ошибка загрузки промптов из {prompts_file}: {e}"
        logger.error(error_msg)
        raise

def load_prompt(prompt_name: str) -> str:
    
    prompts = _load_prompts_data()

    if prompt_name in prompts:
        prompt_text = prompts[prompt_name]
        if isinstance(prompt_text, str):
            logger.debug(f"Загружен промпт (верхний уровень): {prompt_name}")
            return prompt_text

last_underscore = prompt_name.rfind("_")
    if last_underscore == -1:
        error_msg = f"Промпт '{prompt_name}' не найден"
        logger.error(error_msg)
        raise KeyError(error_msg)

category = prompt_name[:last_underscore]
    prompt_type = prompt_name[last_underscore + 1:]

    try:
        prompt_text = prompts[category][prompt_type]
        logger.debug(f"Загружен промпт: {prompt_name}")
        return prompt_text
except KeyError as e:
        error_msg = f"Промпт '{prompt_name}' не найден (category='{category}', type='{prompt_type}')"
        logger.error(error_msg)
        raise KeyError(error_msg) from e

def format_prompt(template: str, **kwargs) -> str:
    
    try:
        return template.format(**kwargs)
except KeyError as e:
        logger.error(f"Отсутствует переменная в промпте: {e}")
        raise
except Exception as e:
        logger.error(f"Ошибка форматирования промпта: {e}")
        raise


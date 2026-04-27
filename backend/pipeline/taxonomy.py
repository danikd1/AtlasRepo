
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

def get_taxonomy_path(taxonomy_file: Optional[str] = None) -> Path:
    
    if taxonomy_file:
        return Path(taxonomy_file)
project_root = Path(__file__).parent.parent
    return project_root / "data" / "taxonomy.json"

def load_taxonomy(taxonomy_file: Optional[str] = None) -> Dict[str, Any]:
    
    path = get_taxonomy_path(taxonomy_file)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
if "disciplines" not in data:
        raise ValueError("В таксономии отсутствует ключ 'disciplines'")
logger.info("Загружена таксономия: %s", path)
    return data

def _collect_keywords_from_node(node: Dict[str, Any]) -> List[str]:
    
    raw = node.get("keywords") or []
    return [str(k).strip().lower() for k in raw if k and isinstance(k, str)]

def _collect_topic_descriptions_from_node(node: Dict[str, Any]) -> List[str]:
    
    raw = node.get("topic_descriptions") or []
    return [str(t).strip() for t in raw if t and isinstance(t, str)]

def get_topic_descriptions_per_node(
    taxonomy: Dict[str, Any],
    selection: Optional[Dict[str, Optional[str]]] = None,
) -> List[Tuple[str, List[str]]]:
    
    selection = selection or {}
    discipline_id = selection.get("discipline")
    ga_id = selection.get("ga")
    activity_id = selection.get("activity")

    result: List[Tuple[str, List[str]]] = []

    disciplines = taxonomy.get("disciplines") or []
    for d in disciplines:
        if d.get("id") != discipline_id:
            continue
desc_d = _collect_topic_descriptions_from_node(d)
        if desc_d:
            result.append((d.get("id", ""), desc_d))
if ga_id is not None:
            for g in (d.get("groups") or []):
                if g.get("id") != ga_id:
                    continue
desc_g = _collect_topic_descriptions_from_node(g)
                if desc_g:
                    result.append((g.get("id", ""), desc_g))
if activity_id is not None:
                    for a in (g.get("activities") or []):
                        if a.get("id") == activity_id:
                            desc_a = _collect_topic_descriptions_from_node(a)
                            if desc_a:
                                result.append((a.get("id", ""), desc_a))
break
break
break

return result

def get_keywords_config_for_selection(
    taxonomy: Dict[str, Any],
    selection: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, List[str]]:
    
    selection = selection or {}
    discipline_id = selection.get("discipline")
    ga_id = selection.get("ga")
    activity_id = selection.get("activity")

    strong: List[str] = []
    seen = set()

    def add_keywords(keywords: List[str]) -> None:
        for k in keywords:
            k = k.strip().lower()
            if k and k not in seen:
                seen.add(k)
                strong.append(k)

disciplines = taxonomy.get("disciplines") or []
    for d in disciplines:
        if d.get("id") != discipline_id:
            continue

if ga_id is None:

            add_keywords(_collect_keywords_from_node(d))
            for g in (d.get("groups") or []):
                add_keywords(_collect_keywords_from_node(g))
                for a in (g.get("activities") or []):
                    add_keywords(_collect_keywords_from_node(a))
else:
            for g in (d.get("groups") or []):
                if g.get("id") != ga_id:
                    continue

if activity_id is None:

                    add_keywords(_collect_keywords_from_node(g))
                    for a in (g.get("activities") or []):
                        add_keywords(_collect_keywords_from_node(a))
else:

                    for a in (g.get("activities") or []):
                        if a.get("id") == activity_id:
                            add_keywords(_collect_keywords_from_node(a))
                            break
break
break

blacklist_raw = taxonomy.get("blacklist") or []
    blacklist = [str(b).strip().lower() for b in blacklist_raw if b and isinstance(b, str)]

    return {
        "strong": strong,
        "weak": [],
        "blacklist": blacklist,
    }

def get_collection_display_name(
    taxonomy: Dict[str, Any],
    selection: Optional[Dict[str, Optional[str]]] = None,
) -> str:
    
    selection = selection or {}
    discipline_id = selection.get("discipline")
    ga_id = selection.get("ga")
    activity_id = selection.get("activity")

    parts: List[str] = []
    name_suffix = ""

    for d in taxonomy.get("disciplines") or []:
        if d.get("id") != discipline_id:
            continue
parts.append(f"{d['id']}")
        name_suffix = d.get("name") or ""
        if ga_id is not None:
            for g in (d.get("groups") or []):
                if g.get("id") != ga_id:
                    continue
parts.append(f"{g['id']}")
                name_suffix = g.get("name") or ""
                if activity_id is not None:
                    for a in (g.get("activities") or []):
                        if a.get("id") == activity_id:
                            parts.append(f"{a['id']}")
                            name_suffix = a.get("name") or ""
                            break
break
break

if not parts:
        return "—"
return " / ".join(parts) + (" — " + name_suffix if name_suffix else "")

def format_taxonomy_for_router_prompt(taxonomy: Dict[str, Any]) -> str:
    
    lines: List[str] = []
    for d in taxonomy.get("disciplines") or []:
        lines.append(f"{d['id']}. {d['name']}")
        desc = _collect_topic_descriptions_from_node(d)
        if desc:
            lines.append(f"  Описание: {' '.join(desc)}")
kw = _collect_keywords_from_node(d)
        if kw:
            lines.append(f"  Ключевые слова: {', '.join(kw)}")
for g in d.get("groups") or []:
            lines.append(f"  {g['id']}. {g['name']}")
            g_desc = _collect_topic_descriptions_from_node(g)
            if g_desc:
                lines.append(f"    Описание: {' '.join(g_desc)}")
g_kw = _collect_keywords_from_node(g)
            if g_kw:
                lines.append(f"    Ключевые слова: {', '.join(g_kw)}")
for a in g.get("activities") or []:
                a_desc = _collect_topic_descriptions_from_node(a)
                part = f"    {a['id']}. {a['name']}"
                if a_desc:
                    part += f" — {' '.join(a_desc)}"
lines.append(part)
                a_kw = _collect_keywords_from_node(a)
                if a_kw:
                    lines.append(f"      Ключевые слова: {', '.join(a_kw)}")
eq = a.get("example_queries") or []
                eq = [str(q).strip() for q in eq if q and isinstance(q, str)][:5]
                if eq:
                    lines.append(f"      Примеры запросов: {'; '.join(eq)}")
lines.append("")
return "\n".join(lines).strip()


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

SECTION_KEY_BY_TYPE = {
    "trend": "key_trends",
    "method": "methods",
    "tool": "tools",
    "case_study": "case_studies",
}

@dataclass
class ArticleRef:
    
    link: str
    title: str
    published_at: Any = None
    article_id: int = 0

@dataclass
class ClusterInfo:
    
    cluster_id: int
    label: str
    description: str
    primary_type: str
    articles: List[ArticleRef]
    size: int = 0

def assign_clusters_to_sections(
    cluster_infos: List[ClusterInfo],
    max_items_per_section: int = 5,
    max_articles_per_cluster: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    
    by_section: Dict[str, List[ClusterInfo]] = {
        "key_trends": [],
        "methods": [],
        "tools": [],
        "case_studies": [],
    }

    for info in cluster_infos:
        key = SECTION_KEY_BY_TYPE.get(info.primary_type)
        if key is None:
            key = "key_trends"
by_section[key].append(info)

out: Dict[str, List[Dict[str, Any]]] = {
        "key_trends": [],
        "methods": [],
        "tools": [],
        "case_studies": [],
    }

    for section_key, infos in by_section.items():

        infos_sorted = sorted(infos, key=lambda x: x.size, reverse=True)
        used_links: Set[str] = set()
        for info in infos_sorted[:max_items_per_section]:

            articles = []
            for a in info.articles[:max_articles_per_cluster]:
                if a.link not in used_links:
                    articles.append({"link": a.link, "title": a.title, "published_at": a.published_at, "article_id": a.article_id})
                    used_links.add(a.link)

if not articles:
                continue
label = (info.label or info.description[:60] or "").strip()
            if not label and info.description:
                label = info.description[:60] + ("..." if len(info.description) > 60 else "")
out[section_key].append({
                "label": label,
                "description": info.description,
                "articles": articles,
            })

return out

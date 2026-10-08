"""Read-only access to JSON content in database/seed (knowledge base, Lab content, templates)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


def seed_dir() -> Path:
    if settings.seed_dir:
        return Path(settings.seed_dir).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "database" / "seed"
        if candidate.is_dir():
            return candidate
    return here.parents[3] / "database" / "seed"


@lru_cache(maxsize=64)
def load_json(name: str) -> Any:
    path = seed_dir() / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_many(prefix: str) -> list:
    items: list = []
    for path in sorted(seed_dir().glob(f"{prefix}*.json")):
        items.extend(load_json(path.name))
    return items


def knowledge_base() -> dict:
    return load_json("knowledge_base.json")


def kb_entry(subcategory: str) -> dict | None:
    return knowledge_base().get(subcategory)


def daily_english() -> list[dict]:
    return load_json("daily_english.json")


def pronunciation_sets() -> list[dict]:
    return load_json("pronunciation.json")


def conversation_scenarios() -> list[dict]:
    return load_json("conversation_scenarios.json")


def scenario(scenario_id: str) -> dict | None:
    return next((s for s in conversation_scenarios() if s["id"] == scenario_id), None)


def speaking_bank() -> dict:
    return load_json("speaking_topics.json")


def diagnostic_bank() -> dict:
    return load_json("diagnostic.json")


def writing_templates() -> dict:
    return load_json("writing_templates.json")

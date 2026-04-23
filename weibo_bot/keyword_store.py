from __future__ import annotations

import json
import os
from pathlib import Path


KEYWORDS_PATH = Path(os.getenv("ACTIVE_KEYWORDS_PATH", "active_keywords.json"))


def configure(path: str) -> None:
    global KEYWORDS_PATH
    KEYWORDS_PATH = Path(path)


def _clean(values) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


def load_keywords() -> list[str]:
    if not KEYWORDS_PATH.exists():
        return []
    try:
        with open(KEYWORDS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return _clean(data)
    return []


def save_keywords(values) -> list[str]:
    cleaned = _clean(values)
    KEYWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(KEYWORDS_PATH, "w", encoding="utf-8") as handle:
        json.dump(cleaned, handle, ensure_ascii=False, indent=2)
    return cleaned

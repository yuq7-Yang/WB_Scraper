from __future__ import annotations

import json
import os
from pathlib import Path

from .config import REPLY_TEMPLATES


TEMPLATES_PATH = Path(os.getenv("REPLY_TEMPLATES_PATH", "reply_templates.json"))


def configure(path: str) -> None:
    global TEMPLATES_PATH
    TEMPLATES_PATH = Path(path)


def _clean_templates(values) -> list[str]:
    seen = set()
    cleaned = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


def load_templates() -> list[str]:
    if not TEMPLATES_PATH.exists():
        return _clean_templates(REPLY_TEMPLATES)
    try:
        raw = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _clean_templates(REPLY_TEMPLATES)
    templates = _clean_templates(raw)
    return templates or _clean_templates(REPLY_TEMPLATES)


def save_templates(templates: list[str]) -> list[str]:
    cleaned = _clean_templates(templates)
    TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEMPLATES_PATH.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cleaned


def add_template(text: str) -> list[str]:
    template = text.strip()
    if not template:
        raise ValueError("template is empty")
    templates = load_templates()
    if template not in templates:
        templates.append(template)
        save_templates(templates)
    return templates

from __future__ import annotations

import os


def parse_env_file(path: str = ".env") -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            values[key.strip()] = value
    return values


def load_env_file(path: str = ".env") -> None:
    for key, value in parse_env_file(path).items():
        os.environ.setdefault(key, value)


def _split_cookies(raw: str) -> list[str]:
    if not raw.strip():
        return []
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for chunk in normalized.split("||"):
        parts.extend(chunk.split("\n"))
    return [part.strip() for part in parts if part.strip()]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


load_env_file()

DB_PATH = os.getenv("WEIBO_DB_PATH", "weibo.db")
SCRAPFLY_KEY = os.getenv("SCRAPFLY_KEY", "").strip()
COOKIES = _split_cookies(os.getenv("WEIBO_COOKIES", ""))

KEYWORDS = [
    "美甲款式",
    "美睫款式",
    "美甲胶水",
    "美睫胶水",
    "美甲品牌",
    "美睫品牌",
    "美甲培训",
    "美睫培训",
    "美睫店",
    "美甲店",
]

EAST_CHINA = ["上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"]

REPLY_TEMPLATES = [
    "您好！我们专注美甲美睫耗材批发，品质有保障，欢迎私聊了解～",
    "看到您对美甲感兴趣，我们有专业培训课程，欢迎咨询！",
    "您好，我们提供美甲美睫全套耗材，支持小批量，欢迎了解～",
]

REPLY_DELAY = int(os.getenv("REPLY_DELAY", "8"))
MAX_REPLIES_PER_RUN = int(os.getenv("MAX_REPLIES_PER_RUN", "20"))
MAX_COMMENTS_PER_KEYWORD = int(os.getenv("MAX_COMMENTS_PER_KEYWORD", "2"))
DEFAULT_MAX_PER_KEYWORD = int(os.getenv("DEFAULT_MAX_PER_KEYWORD", str(MAX_COMMENTS_PER_KEYWORD)))
DEFAULT_MAX_TOTAL = int(os.getenv("DEFAULT_MAX_TOTAL", "20"))
DRY_RUN_REPLIES = _env_bool("DRY_RUN_REPLIES", True)
ENABLE_REAL_REPLIES = _env_bool("ENABLE_REAL_REPLIES", False)

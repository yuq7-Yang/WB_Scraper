from __future__ import annotations

import re
from html import unescape

import requests

from . import config as _config
from .config import UNRELATED_COMMENT_TERMS

INTRO_PREFIX = "\u6211\u8fd9\u8fb9\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684"

BEAUTY_SIGNALS = [
    "\u7f8e\u7532",
    "\u7f8e\u776b",
    "\u776b\u6bdb",
    "\u732b\u773c",
    "\u7532\u6cb9\u80f6",
    "\u80f6\u6c34",
    "\u5c01\u5c42",
    "\u7a7f\u6234\u7532",
    "\u6b3e\u5f0f",
    "\u7532\u7247",
    "\u98df\u54c1",
    "\u5f00\u5e97",
    "\u62ff\u8d27",
    "\u8fdb\u8d27",
    "\u9009\u54c1",
    "\u57f9\u8bad",
    "\u6559\u7a0b",
    "\u6750\u6599",
    "\u5de5\u5177",
    "\u54c1\u724c",
    "\u5c55\u4f1a",
]

INTENT_SIGNALS = [
    "\u63a8\u8350",
    "\u94fe\u63a5",
    "\u60f3\u505a",
    "\u60f3\u8981",
    "\u79cd\u8349",
    "\u4e0b\u5355",
    "\u6c42",
    "\u5417",
    "\uff1f",
    "?",
    "\u600e\u4e48",
    "\u54ea\u91cc",
    "\u591a\u5c11\u94b1",
    "\u4ef7\u683c",
    "\u62ff\u8d27",
    "\u8fdb\u8d27",
    "\u5f00\u5e97",
    "\u52a0\u76df",
]

UNRELATED_SIGNALS = [*UNRELATED_COMMENT_TERMS, "cpfd", "cpf"]


def sanitize_comment_text(value: str | None) -> str:
    text = value or ""
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\[[^\]]{1,20}\]", "", text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"(?:\u7f51\u9875\u94fe\u63a5|\u67e5\u770b\u56fe\u7247|\u5168\u6587)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fallback_reply(lead: dict) -> str:
    return _config.get_template_by_keyword(lead.get("keyword") or "")


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _has_beauty_context(keyword: str, comment_text: str) -> bool:
    return _contains_any(keyword, BEAUTY_SIGNALS) or _contains_any(comment_text, BEAUTY_SIGNALS)


def is_relevant_for_expo_reply(lead: dict) -> bool:
    keyword = sanitize_comment_text(lead.get("keyword"))
    comment_text = sanitize_comment_text(lead.get("comment_text"))
    if not comment_text:
        return False
    if _contains_any(comment_text, UNRELATED_SIGNALS) and not _contains_any(comment_text, BEAUTY_SIGNALS):
        return False
    if not _has_beauty_context(keyword, comment_text):
        return False
    if _contains_any(comment_text, INTENT_SIGNALS):
        return True
    return bool(keyword and len(comment_text) <= 18)


def _build_messages(lead: dict) -> list[dict[str, str]]:
    keyword = sanitize_comment_text(lead.get("keyword"))
    comment_text = sanitize_comment_text(lead.get("comment_text"))
    return [
        {
            "role": "system",
            "content": (
                "\u4f60\u662f\u7f8e\u4e1a\u884c\u4e1a\u5c55\u4f1a\u7684\u5fae\u535a\u56de\u590d\u52a9\u624b\u3002"
                "\u8bf7\u6839\u636e\u8bc4\u8bba\u5185\u5bb9\u751f\u6210\u4e00\u6761\u534a\u5b98\u65b9\u3001\u534a\u81ea\u7136\u7684\u4e2d\u6587\u56de\u590d\u4e2d\u95f4\u6bb5\u3002"
                "\u53ea\u8f93\u51fa\u4e00\u53e5\u77ed\u53e5\uff0c\u4e0d\u8981\u5e26\u5f00\u5934\u81ea\u6211\u4ecb\u7ecd\uff0c\u4e0d\u8981\u5e26\u7ed3\u5c3e\u5f15\u5bfc\u3002"
                "\u5185\u5bb9\u5fc5\u987b\u5148\u7a81\u51fa\u6211\u4eec\u5c55\u4f1a\u73b0\u573a\u6709\u4ec0\u4e48\uff0c"
                "\u56f4\u7ed5\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u6750\u6599\u3001\u5de5\u5177\u3001\u57f9\u8bad\u3001\u9879\u76ee\u3001\u4f9b\u5e94\u94fe\u3001\u9009\u54c1\u3001\u5f00\u5e97\u8d44\u6e90\u91cc\u6700\u76f8\u5173\u7684\u4e00\u7c7b\u6765\u5199\u3002"
                "\u4e0d\u8981\u5148\u5bd2\u6684\uff0c\u4e0d\u8981\u50cf\u666e\u901a\u7f51\u53cb\u95f2\u804a\uff0c\u4e0d\u8981\u5938\u5bf9\u65b9\uff0c"
                "\u4e0d\u8981\u7f16\u9020\u548c\u8bc4\u8bba\u65e0\u5173\u7684\u751f\u6d3b\u573a\u666f\u3002"
                "\u4e0d\u8981\u51fa\u73b0AI\u3001\u81ea\u6211\u4ecb\u7ecd\u3001\u8054\u7cfb\u65b9\u5f0f\u3001\u79c1\u4fe1\u3001\u95e8\u7968\u3001\u94fe\u63a5\u3002"
                "\u957f\u5ea6\u63a7\u5236\u572814\u523030\u4e2a\u6c49\u5b57\u3002"
            ),
        },
        {
            "role": "user",
            "content": (
                f"\u5173\u952e\u8bcd\uff1a{keyword or '\u672a\u63d0\u4f9b'}\n"
                f"\u8bc4\u8bba\u5185\u5bb9\uff1a{comment_text or '\u672a\u63d0\u4f9b'}\n"
                "\u8bf7\u5199\u4e00\u6761\u5148\u7a81\u51fa\u6211\u4eec\u5c55\u4f1a\u73b0\u573a\u6709\u4ec0\u4e48\uff0c\u518d\u81ea\u7136\u627f\u63a5\u5174\u8da3\u70b9\u7684\u77ed\u53e5\u3002"
            ),
        },
    ]


def _normalize_body(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip("`\"'")
    if not cleaned:
        return ""
    cleaned = re.sub(
        r"^(\u6211\u8fd9\u8fb9\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684|\u6211\u662f\u505a\u7f8e\u4e1a\u5c55\u4f1a\u7684|\u6211\u4eec\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684)[\uff0c, ]*",
        "",
        cleaned,
    ).strip()
    cleaned = re.split(r"(\u79c1\u4fe1|\u95e8\u7968|\u94fe\u63a5|\u9886\u53d6)", cleaned, maxsplit=1)[0].strip()
    cleaned = cleaned.rstrip("\uff0c\u3002\uff01\uff1f,.!?\u3001 ")
    if len(cleaned) > 34:
        cleaned = cleaned[:34].rstrip("\uff0c\u3002\uff01\uff1f,.!?\u3001 ")
    return cleaned


def _compose_reply(body: str) -> str:
    cta = _config.LOCAL_LLM_TICKET_CTA.strip()
    if not body:
        return cta
    return f"{INTRO_PREFIX}\uff0c{body}\uff0c{cta}"


def _ollama_chat(messages: list[dict[str, str]]) -> str:
    response = requests.post(
        f"{_config.LOCAL_LLM_BASE_URL.rstrip('/')}/api/chat",
        json={
            "model": _config.LOCAL_LLM_MODEL,
            "stream": False,
            "messages": messages,
        },
        timeout=_config.LOCAL_LLM_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    content = ((body.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("local llm returned empty content")
    return content


def generate_reply_for_lead(lead: dict) -> str | None:
    if not is_relevant_for_expo_reply(lead):
        return None
    if not _config.LOCAL_LLM_ENABLED:
        return _fallback_reply(lead)
    try:
        content = _ollama_chat(_build_messages(lead))
        body = _normalize_body(content)
        if not body:
            raise RuntimeError("local llm returned unusable content")
        return _compose_reply(body)
    except Exception:
        return _fallback_reply(lead)

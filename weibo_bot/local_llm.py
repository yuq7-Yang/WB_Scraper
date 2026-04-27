from __future__ import annotations

import re
from collections import deque
from html import unescape

import requests

from . import config as _config
from .config import UNRELATED_COMMENT_TERMS

INTRO_PREFIXES = [
    "我这边是展会的",
    "展会这边",
    "我们展会现场这边",
]
EXPO_CTA_VARIANTS = [
    "我这边是展会的，感兴趣可以找我免费领门票。",
    "这边是展会现场，想了解的话可以找我免费领门票。",
    "我们这边是展会方，有兴趣可以找我免费领门票。",
    "我这边对接展会，想来的话可以找我免费领门票。",
]
BODY_COPY_VARIANTS = [
    "{body}",
    "你问的这个方向，现场可以集中看相关品牌、产品和资源",
    "这类需求现场聊会更直观，相关产品和资源可以一起了解",
    "如果你想重点了解这块，现场能直接对比相关方案",
    "可以到现场看看同类资源，适合先对比再决定",
]
CTA_VARIANTS = [
    "感兴趣可以私信我免费领门票。",
    "想来的话可以找我免费领门票。",
    "要门票的话私信我，我这边可以免费发你。",
    "感兴趣就找我，我这边能免费给你门票。",
]
_reply_variant_index = 0
_recent_auto_replies: deque[str] = deque(maxlen=24)

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

STRONG_INTENT_SIGNALS = [
    "\u60f3\u4e70",
    "\u60f3\u8981",
    "\u60f3\u5165",
    "\u6c42\u63a8\u8350",
    "\u63a8\u8350",
    "\u94fe\u63a5",
    "\u4ef7\u683c",
    "\u591a\u5c11\u94b1",
    "\u5728\u54ea\u4e70",
    "\u54ea\u91cc\u4e70",
    "\u600e\u4e48\u4e70",
    "\u60f3\u5f00",
    "\u5f00\u5e97",
    "\u52a0\u76df",
    "\u62ff\u8d27",
    "\u8fdb\u8d27",
    "\u91c7\u8d2d",
    "\u6279\u53d1",
    "\u4f9b\u5e94\u5546",
    "\u57f9\u8bad",
    "\u60f3\u5b66",
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


def _next_variant_index() -> int:
    global _reply_variant_index
    current = _reply_variant_index
    _reply_variant_index += 1
    return current


def _strip_ticket_cta(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = cleaned.replace("CIBE", "展会")
    cleaned = cleaned.replace("展会展会", "展会")
    cleaned = re.sub(r"(有需要的话|感兴趣的话|感兴趣就|要门票的话).{0,30}(私信我|找我).{0,20}(门票|链接).*$", "", cleaned)
    cleaned = re.sub(r"(私信我|找我).{0,20}(门票|链接).*$", "", cleaned)
    cleaned = cleaned.rstrip("，。！？,.!、 ")
    return cleaned


def _normalize_cta(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = cleaned.replace("领取", "领")
    cleaned = cleaned.replace("门票链接", "门票")
    cleaned = cleaned.replace("获取门票", "免费领门票")
    cleaned = cleaned.replace("领门票链接", "领门票")
    cleaned = cleaned.replace("免费领取门票", "免费领门票")
    cleaned = cleaned.replace("免费领取门票链接", "免费领门票")
    cleaned = cleaned.rstrip("，。！？,.!、 ")
    if "免费领门票" not in cleaned:
        cleaned = "感兴趣可以私信我免费领门票"
    return f"{cleaned}。"


def _fallback_reply(lead: dict) -> str:
    template = _config.get_template_by_keyword(
        lead.get("keyword") or "",
        lead.get("comment_text") or "",
    )
    body = _strip_ticket_cta(template)
    if not body:
        body = "展会现场这类品牌和资源会更集中一些"
    return _compose_reply(body)


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _has_keyword_context(keyword: str, comment_text: str) -> bool:
    return bool(keyword and keyword in comment_text)


def _has_strong_intent(text: str) -> bool:
    return _contains_any(text, STRONG_INTENT_SIGNALS)


def _is_unrelated_to_keyword(keyword: str, comment_text: str) -> bool:
    return _contains_any(comment_text, UNRELATED_SIGNALS) and not _has_keyword_context(keyword, comment_text)


def is_relevant_for_expo_reply(lead: dict) -> bool:
    keyword = sanitize_comment_text(lead.get("keyword"))
    comment_text = sanitize_comment_text(lead.get("comment_text"))
    if not comment_text:
        return False
    if _is_unrelated_to_keyword(keyword, comment_text):
        return False
    return _contains_any(comment_text, INTENT_SIGNALS) or _has_strong_intent(comment_text)


def _build_intent_messages(lead: dict) -> list[dict[str, str]]:
    keyword = sanitize_comment_text(lead.get("keyword"))
    comment_text = sanitize_comment_text(lead.get("comment_text"))
    return [
        {
            "role": "system",
            "content": (
                "你是微博评论意向判断助手。请判断这条微博评论是否有真实意向，"
                "包括想买、想了解、求推荐、问价格、要链接、想加盟、想开店、想培训、想拿货、想采购等。"
                "只根据评论本身和采集关键词判断，不要臆测。"
                "如果只是夸一句、路过、玩梗、无明确需求，判断为否。"
                "请严格用两行回复：\n有意向：是/否\n需求：一句话概括"
            ),
        },
        {
            "role": "user",
            "content": (
                f"采集关键词：{keyword or '未提供'}\n"
                f"评论内容：{comment_text or '未提供'}"
            ),
        },
    ]


def _parse_intent_decision(text: str) -> bool | None:
    cleaned = str(text or "").strip().lower()
    if not cleaned:
        return None
    if re.search(r"有意向\s*[:：]\s*(是|yes|y|true)", cleaned):
        return True
    if re.search(r"有意向\s*[:：]\s*(否|no|n|false)", cleaned):
        return False
    if re.search(r"^(是|yes|true)\b", cleaned):
        return True
    if re.search(r"^(否|no|false)\b", cleaned):
        return False
    return None


def _llm_confirms_intent(lead: dict) -> bool | None:
    content = _ollama_chat(_build_intent_messages(lead))
    return _parse_intent_decision(content)


def _build_messages(lead: dict) -> list[dict[str, str]]:
    keyword = sanitize_comment_text(lead.get("keyword"))
    comment_text = sanitize_comment_text(lead.get("comment_text"))
    keyword_text = keyword or "\u672a\u63d0\u4f9b"
    comment_text_value = comment_text or "\u672a\u63d0\u4f9b"
    return [
        {
            "role": "system",
            "content": (
                "\u4f60\u662f\u884c\u4e1a\u5c55\u4f1a\u7684\u5fae\u535a\u56de\u590d\u52a9\u624b\u3002"
                "\u8bf7\u6839\u636e\u8bc4\u8bba\u5185\u5bb9\u751f\u6210\u4e00\u6761\u534a\u5b98\u65b9\u3001\u534a\u81ea\u7136\u7684\u4e2d\u6587\u56de\u590d\u4e2d\u95f4\u6bb5\u3002"
                "\u53ea\u8f93\u51fa\u4e00\u53e5\u77ed\u53e5\uff0c\u4e0d\u8981\u5e26\u5f00\u5934\u81ea\u6211\u4ecb\u7ecd\uff0c\u4e0d\u8981\u5e26\u7ed3\u5c3e\u5f15\u5bfc\u3002"
                "\u5185\u5bb9\u5fc5\u987b\u5148\u7a81\u51fa\u6211\u4eec\u5c55\u4f1a\u73b0\u573a\u6709\u4ec0\u4e48\uff0c"
                "\u56f4\u7ed5\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u6750\u6599\u3001\u5de5\u5177\u3001\u57f9\u8bad\u3001\u9879\u76ee\u3001\u4f9b\u5e94\u94fe\u3001\u9009\u54c1\u3001\u5f00\u5e97\u8d44\u6e90\u91cc\u6700\u76f8\u5173\u7684\u4e00\u7c7b\u6765\u5199\u3002"
                "\u4e0d\u8981\u5148\u5bd2\u6684\uff0c\u4e0d\u8981\u50cf\u666e\u901a\u7f51\u53cb\u95f2\u804a\uff0c\u4e0d\u8981\u5938\u5bf9\u65b9\uff0c"
                "\u4e0d\u8981\u7f16\u9020\u548c\u8bc4\u8bba\u65e0\u5173\u7684\u751f\u6d3b\u573a\u666f\u3002"
                "\u4e0d\u8981\u548c\u4e0a\u4e00\u6761\u56de\u590d\u4f7f\u7528\u51e0\u4e4e\u4e00\u6837\u7684\u8868\u8fbe\uff0c\u5c3d\u91cf\u6362\u4e00\u79cd\u81ea\u7136\u8bf4\u6cd5\u3002"
                "\u4e0d\u8981\u51fa\u73b0AI\u3001\u81ea\u6211\u4ecb\u7ecd\u3001\u8054\u7cfb\u65b9\u5f0f\u3001\u79c1\u4fe1\u3001\u95e8\u7968\u3001\u94fe\u63a5\u3002"
                "\u957f\u5ea6\u63a7\u5236\u572814\u523030\u4e2a\u6c49\u5b57\u3002"
            ),
        },
        {
            "role": "user",
            "content": (
                f"\u5173\u952e\u8bcd\uff1a{keyword_text}\n"
                f"\u8bc4\u8bba\u5185\u5bb9\uff1a{comment_text_value}\n"
                "\u8bf7\u5199\u4e00\u6761\u5148\u7a81\u51fa\u6211\u4eec\u5c55\u4f1a\u73b0\u573a\u6709\u4ec0\u4e48\uff0c\u518d\u81ea\u7136\u627f\u63a5\u5174\u8da3\u70b9\u7684\u77ed\u53e5\u3002"
            ),
        },
    ]


def _normalize_body(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.replace("CIBE", "展会")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip("`\"'")
    if not cleaned:
        return ""
    cleaned = re.sub(
        r"^(我这边是美业展会的|我是做美业展会的|我们是美业展会的|我这边是展会的|展会这边|我们展会现场这边)[\uff0c, ]*",
        "",
        cleaned,
    ).strip()
    cleaned = re.split(r"(\u79c1\u4fe1|\u95e8\u7968|\u94fe\u63a5|\u9886\u53d6)", cleaned, maxsplit=1)[0].strip()
    cleaned = cleaned.rstrip("\uff0c\u3002\uff01\uff1f,.!?\u3001 ")
    if len(cleaned) > 34:
        cleaned = cleaned[:34].rstrip("\uff0c\u3002\uff01\uff1f,.!?\u3001 ")
    return cleaned


def _compose_reply(body: str) -> str:
    body_text = _strip_ticket_cta(body)
    if not body_text:
        body_text = "展会现场这类品牌和资源会更集中一些"
    start = _next_variant_index()
    total = len(BODY_COPY_VARIANTS) * len(EXPO_CTA_VARIANTS)
    for offset in range(total):
        variant_index = start + offset
        body_variant = BODY_COPY_VARIANTS[variant_index % len(BODY_COPY_VARIANTS)]
        cta = EXPO_CTA_VARIANTS[(variant_index // len(BODY_COPY_VARIANTS)) % len(EXPO_CTA_VARIANTS)]
        varied_body = body_variant.format(body=body_text)
        candidate = f"{varied_body}，{cta}"
        if candidate not in _recent_auto_replies:
            _recent_auto_replies.append(candidate)
            return candidate
    body_variant = BODY_COPY_VARIANTS[start % len(BODY_COPY_VARIANTS)]
    cta = EXPO_CTA_VARIANTS[(start // len(BODY_COPY_VARIANTS)) % len(EXPO_CTA_VARIANTS)]
    candidate = f"{body_variant.format(body=body_text)}，{cta}"
    _recent_auto_replies.append(candidate)
    return candidate


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
    keyword = sanitize_comment_text(lead.get("keyword"))
    comment_text = sanitize_comment_text(lead.get("comment_text"))
    if not comment_text or _is_unrelated_to_keyword(keyword, comment_text):
        return None
    if not _config.LOCAL_LLM_ENABLED:
        if not is_relevant_for_expo_reply(lead):
            return None
        return _fallback_reply(lead)
    try:
        intent_decision = _llm_confirms_intent(lead)
        if intent_decision is False and not _has_strong_intent(comment_text):
            return None
        if intent_decision is None and not is_relevant_for_expo_reply(lead):
            return None
        content = _ollama_chat(_build_messages(lead))
        body = _normalize_body(content)
        if not body:
            raise RuntimeError("local llm returned unusable content")
        return _compose_reply(body)
    except Exception:
        if not is_relevant_for_expo_reply(lead):
            return None
        return _fallback_reply(lead)

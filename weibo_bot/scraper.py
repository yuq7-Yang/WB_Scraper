from __future__ import annotations

import json
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .config import (
    AI_LIKE_PATTERNS,
    B2B_INTENT_TERMS,
    BEAUTY_TERMS,
    COOKIES,
    CONSUMER_INTENT_TERMS,
    EAST_CHINA,
    INTENT_KEYWORDS,
    KEYWORDS,
    MAX_COMMENTS_PER_KEYWORD,
    MIN_B2B_INTENT_SCORE,
    MIN_CONSUMER_INTENT_SCORE,
    SCRAPE_KEYWORD_DELAY,
    SCRAPE_PAGE_DELAY,
    SCRAPE_POST_DELAY,
    SCRAPFLY_KEY,
    SPAM_COMMENT_TERMS,
    UNRELATED_COMMENT_TERMS,
)
from .db import init_db, insert_lead
from .local_llm import sanitize_comment_text


SCRAPE_CONFIG = {
    "asp": True,
    "proxy_pool": "public_residential_pool",
    "country": "cn,hk",
    "render_js": False,
}


def _headers(cookie_index: int = 0) -> dict[str, str]:
    if not COOKIES:
        raise RuntimeError("WEIBO_COOKIES is not configured")
    return {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Cookie": COOKIES[cookie_index % len(COOKIES)],
        "Accept": "application/json, text/plain, */*",
        "MWeibo-Pwa": "1",
    }


def is_east_china(source: str | None) -> bool:
    return bool(source and any(region in source for region in EAST_CHINA))


def is_beauty_keyword(keyword: str) -> bool:
    return any(term in keyword for term in BEAUTY_TERMS)


def has_intent(text: str | None) -> bool:
    return bool(text and any(keyword in text for keyword in INTENT_KEYWORDS))


def _looks_spam_or_ai(text: str) -> bool:
    lowered = text.lower()
    if any(term.lower() in lowered for term in SPAM_COMMENT_TERMS):
        return True
    if any(pattern in text for pattern in AI_LIKE_PATTERNS):
        return True
    # heuristic: comment length >= 40 and structured like AI prose
    # (commas/periods used in "有序列表"/"建议 ..." style)
    if len(text) >= 40 and text.count("，") >= 4 and ("建议" in text or "选择" in text or "可以考虑" in text):
        return True
    # heuristic: pure-url / "扫码加微xxx" phone-like fragments
    if ("http" in lowered or "www." in lowered) and len(text) <= 40:
        return True
    return False


def analyze_intent(text: str | None, keyword: str | None = None) -> dict[str, Any]:
    clean_text = sanitize_comment_text(text)
    clean_keyword = sanitize_comment_text(keyword)
    haystack = f"{clean_keyword} {clean_text}".strip()

    if not clean_text:
        return {"matched": False, "lead_type": None, "intent_score": 0, "clean_text": clean_text}

    if any(term in clean_text.lower() for term in [item.lower() for item in UNRELATED_COMMENT_TERMS]):
        return {"matched": False, "lead_type": None, "intent_score": 0, "clean_text": clean_text}

    if _looks_spam_or_ai(clean_text):
        return {"matched": False, "lead_type": None, "intent_score": 0, "clean_text": clean_text}

    b2b_score = 0
    consumer_score = 0
    b2b_hits = 0
    consumer_hits = 0
    beauty_hits = 0

    for term in B2B_INTENT_TERMS:
        if term in haystack:
            b2b_score += 3
            b2b_hits += 1
    for term in CONSUMER_INTENT_TERMS:
        if term in haystack:
            consumer_score += 2
            consumer_hits += 1
    for term in BEAUTY_TERMS:
        if term in haystack:
            b2b_score += 1
            consumer_score += 1
            beauty_hits += 1
    for term in INTENT_KEYWORDS:
        if term in clean_text:
            consumer_score += 1

    if beauty_hits == 0:
        return {"matched": False, "lead_type": None, "intent_score": 0, "clean_text": clean_text}

    if b2b_hits > 0 and b2b_score >= MIN_B2B_INTENT_SCORE:
        return {"matched": True, "lead_type": "b2b", "intent_score": b2b_score, "clean_text": clean_text}
    if consumer_hits > 0 and consumer_score >= MIN_CONSUMER_INTENT_SCORE:
        return {
            "matched": True,
            "lead_type": "consumer",
            "intent_score": consumer_score,
            "clean_text": clean_text,
        }
    return {"matched": False, "lead_type": None, "intent_score": max(b2b_score, consumer_score), "clean_text": clean_text}


def _parse_weibo_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
    except (TypeError, ValueError):
        return None


def _is_recent(created_at: str | None, days: int = 90) -> bool:
    parsed = _parse_weibo_time(created_at)
    if parsed is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return parsed >= cutoff


def extract_post_ids(data: dict[str, Any]) -> list[str]:
    posts = []
    for card in data.get("data", {}).get("cards", []):
        mblog = card.get("mblog", {})
        post_id = mblog.get("id")
        if card.get("card_type") != 9 or not post_id:
            continue
        if not _is_recent(mblog.get("created_at")):
            continue
        posts.append(str(post_id))
    return posts


def _client():
    if not SCRAPFLY_KEY:
        raise RuntimeError("SCRAPFLY_KEY is not configured")
    from scrapfly import ScrapflyClient

    return ScrapflyClient(key=SCRAPFLY_KEY)


def _scrape_json(url: str, cookie_index: int = 0, client: Any | None = None) -> dict[str, Any]:
    from scrapfly import ScrapeConfig

    active_client = client or _client()
    result = active_client.scrape(
        ScrapeConfig(url=url, headers=_headers(cookie_index), **SCRAPE_CONFIG)
    )
    return json.loads(result.content)


def search_posts(keyword: str, page: int = 1, cookie_index: int = 0, client: Any | None = None) -> list[str]:
    encoded = urllib.parse.quote(keyword)
    url = (
        "https://m.weibo.cn/api/container/getIndex"
        f"?containerid=100103type%3D1%26q%3D{encoded}&page_type=searchall&page={page}"
    )
    try:
        return extract_post_ids(_scrape_json(url, cookie_index=cookie_index, client=client))
    except Exception as exc:
        print(f"[!] 搜索失败 [{keyword}]: {exc}")
        return []


def fetch_comments(
    post_id: str,
    cookie_index: int = 0,
    client: Any | None = None,
    max_pages: int = 3,
) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    max_id: str | int = 0
    max_id_type = 0

    for page in range(max(1, max_pages)):
        params = f"id={post_id}&mid={post_id}&max_id_type={max_id_type}"
        if page > 0:
            params += f"&max_id={urllib.parse.quote(str(max_id))}"
        url = f"https://m.weibo.cn/comments/hotflow?{params}"
        try:
            data = _scrape_json(url, cookie_index=cookie_index, client=client)
        except Exception as exc:
            print(f"[!] 评论获取失败 [post={post_id}]: {exc}")
            break

        payload = data.get("data", {}) or {}
        comments.extend(payload.get("data", []) or [])
        max_id = payload.get("max_id") or 0
        max_id_type = payload.get("max_id_type") or 0
        if not max_id:
            break
        if SCRAPE_PAGE_DELAY > 0:
            time.sleep(SCRAPE_PAGE_DELAY)

    return comments


def run_scrape(
    keywords: list[str] | None = None,
    max_per_keyword: int = MAX_COMMENTS_PER_KEYWORD,
    max_total: int = 20,
    progress_callback: Callable[..., None] | None = None,
    client: Any | None = None,
) -> int:
    if not SCRAPFLY_KEY:
        raise RuntimeError("SCRAPFLY_KEY is not configured")
    if not COOKIES:
        raise RuntimeError("WEIBO_COOKIES is not configured")

    init_db()
    active_keywords = keywords or KEYWORDS
    max_per_keyword = max(1, int(max_per_keyword))
    max_total = max(1, int(max_total))
    total_found = 0
    for index, keyword in enumerate(active_keywords):
        if total_found >= max_total:
            break
        if progress_callback:
            progress_callback(keyword=keyword, step=index + 1, total=len(active_keywords))
        post_ids = search_posts(keyword, cookie_index=index, client=client)
        found_for_keyword = 0
        for post_id in post_ids:
            if found_for_keyword >= max_per_keyword or total_found >= max_total:
                break
            comments = fetch_comments(post_id, cookie_index=index, client=client)
            for comment in comments:
                if found_for_keyword >= max_per_keyword or total_found >= max_total:
                    break
                source = comment.get("source", "")
                analysis = analyze_intent(comment.get("text", ""), keyword=keyword)
                text = analysis["clean_text"]
                if analysis["matched"]:
                    inserted = insert_lead(
                        user_name=comment.get("user", {}).get("screen_name", ""),
                        location=source,
                        comment_text=text,
                        comment_id=str(comment.get("id") or comment.get("idstr") or "") or None,
                        post_id=post_id,
                        keyword=keyword,
                        lead_type=analysis["lead_type"],
                        intent_score=analysis["intent_score"],
                    )
                    if inserted:
                        total_found += 1
                        found_for_keyword += 1
            if SCRAPE_POST_DELAY > 0:
                time.sleep(SCRAPE_POST_DELAY)
        if SCRAPE_KEYWORD_DELAY > 0:
            time.sleep(SCRAPE_KEYWORD_DELAY)
    return total_found


if __name__ == "__main__":
    count = run_scrape(lambda **kw: print(f"[{kw['step']}/{kw['total']}] {kw['keyword']}"))
    print(f"采集完成，共找到 {count} 位意向用户")

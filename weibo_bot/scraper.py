from __future__ import annotations

import json
import time
import urllib.parse
from typing import Any, Callable

from .config import COOKIES, EAST_CHINA, KEYWORDS, MAX_COMMENTS_PER_KEYWORD, SCRAPFLY_KEY
from .db import init_db, insert_lead


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


def extract_post_ids(data: dict[str, Any]) -> list[str]:
    posts = []
    for card in data.get("data", {}).get("cards", []):
        mblog = card.get("mblog", {})
        post_id = mblog.get("id")
        if card.get("card_type") == 9 and post_id:
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


def fetch_comments(post_id: str, cookie_index: int = 0, client: Any | None = None) -> list[dict[str, Any]]:
    url = f"https://m.weibo.cn/comments/hotflow?id={post_id}&mid={post_id}&max_id_type=0"
    try:
        data = _scrape_json(url, cookie_index=cookie_index, client=client)
        return data.get("data", {}).get("data", [])
    except Exception as exc:
        print(f"[!] 评论获取失败 [post={post_id}]: {exc}")
        return []


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
                if is_east_china(source):
                    inserted = insert_lead(
                        user_name=comment.get("user", {}).get("screen_name", ""),
                        location=source,
                        comment_text=comment.get("text", ""),
                        comment_id=str(comment.get("id") or comment.get("idstr") or "") or None,
                        post_id=post_id,
                        keyword=keyword,
                    )
                    if inserted:
                        total_found += 1
                        found_for_keyword += 1
            time.sleep(2.5)
        time.sleep(5)
    return total_found


if __name__ == "__main__":
    count = run_scrape(lambda **kw: print(f"[{kw['step']}/{kw['total']}] {kw['keyword']}"))
    print(f"采集完成，共找到 {count} 位华东用户")

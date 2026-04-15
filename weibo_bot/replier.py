from __future__ import annotations

import json
import time
from typing import Callable

import requests

from .config import (
    COOKIES,
    ENABLE_REAL_REPLIES,
    MAX_REPLIES_PER_RUN,
    REPLY_DELAY,
    REPLY_TEMPLATES as CONFIG_REPLY_TEMPLATES,
    SCRAPFLY_KEY,
)
from .db import get_leads_by_ids, get_pending_leads, update_lead_status
from .template_store import load_templates

REPLY_TEMPLATES = CONFIG_REPLY_TEMPLATES


def choose_reply_template() -> str:
    templates = REPLY_TEMPLATES if REPLY_TEMPLATES != CONFIG_REPLY_TEMPLATES else load_templates()
    if not templates:
        raise RuntimeError("REPLY_TEMPLATES is empty")
    return templates[0]


def _make_scenario(reply_text: str) -> list[dict]:
    return [
        {"scroll": {"element": "body", "selector": "bottom"}},
        {"wait": 1500},
        {"click": {"selector": ".lite-detail-page_reply", "ignore_if_not_visible": True}},
        {"wait": 800},
        {"fill": {"selector": "textarea.comment-send_textarea", "value": reply_text}},
        {"wait": 500},
        {"click": {"selector": "button.comment-send_btn"}},
        {"wait": 1200},
    ]


def _send_real_reply(lead: dict, reply_text: str, cookie_index: int = 0) -> tuple[bool, str]:
    if not COOKIES:
        raise RuntimeError("WEIBO_COOKIES is not configured")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Cookie": COOKIES[cookie_index % len(COOKIES)],
            "Referer": f"https://m.weibo.cn/detail/{lead['post_id']}",
            "Accept": "application/json, text/plain, */*",
        }
    )
    config_response = session.get("https://m.weibo.cn/api/config", timeout=30)
    config_data = config_response.json()
    login_data = config_data.get("data", {})
    if not login_data.get("login"):
        raise RuntimeError("WEIBO_COOKIES is not logged in")

    st = login_data.get("st")
    if not st:
        raise RuntimeError("Weibo st token is missing")

    comment_id = str(lead.get("comment_id") or "").strip()
    if comment_id:
        endpoint = "https://m.weibo.cn/api/comments/reply"
        payload = {
            "content": reply_text,
            "mid": str(lead["post_id"]),
            "cid": comment_id,
            "st": st,
        }
    else:
        endpoint = "https://m.weibo.cn/api/comments/create"
        payload = {"content": reply_text, "mid": str(lead["post_id"]), "st": st}
    response = session.post(
        endpoint,
        data=payload,
        timeout=30,
    )
    data = response.json()
    if int(data.get("ok", 0)) <= 0:
        raise RuntimeError(f"Weibo comment API failed: {data}")
    return True, reply_text


def reply_to_lead(
    lead: dict,
    reply_text: str,
    confirm_real_send: bool = False,
    cookie_index: int = 0,
) -> tuple[bool, str]:
    if ENABLE_REAL_REPLIES and confirm_real_send:
        ok, info = _send_real_reply(lead, reply_text, cookie_index=cookie_index)
        if ok:
            update_lead_status(lead["id"], "replied", reply_text)
        return ok, info

    update_lead_status(lead["id"], "reviewed", reply_text)
    return True, reply_text


def run_reply(
    progress_callback: Callable[..., None] | None = None,
    limit: int = MAX_REPLIES_PER_RUN,
    dry_run: bool | None = None,
    lead_ids: list[int] | None = None,
    reply_text: str | None = None,
    confirm_real_send: bool = False,
) -> int:
    if lead_ids is None:
        leads = get_pending_leads(limit=limit)
    else:
        leads = get_leads_by_ids([int(lead_id) for lead_id in lead_ids])

    selected_text = reply_text or choose_reply_template()
    if dry_run is True:
        confirm_real_send = False

    replied = 0
    for index, lead in enumerate(leads):
        try:
            ok, info = reply_to_lead(
                lead,
                reply_text=selected_text,
                confirm_real_send=confirm_real_send,
                cookie_index=index,
            )
        except Exception as exc:
            ok = False
            info = str(exc)
            update_lead_status(lead["id"], "failed", info)
        if progress_callback:
            progress_callback(lead=lead, ok=ok, current=index + 1, total=len(leads), info=info)
        replied += 1 if ok else 0
        if index < len(leads) - 1:
            time.sleep(REPLY_DELAY)
    return replied


if __name__ == "__main__":
    count = run_reply()
    print(f"reply run complete: {count}")

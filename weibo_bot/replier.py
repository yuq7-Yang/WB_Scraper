from __future__ import annotations

import json
import time
from uuid import uuid4
from typing import Callable

from scrapfly import ScrapeConfig, ScrapflyClient

from . import config as _config
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
REPLIES_PER_ACCOUNT = 3
ACCOUNT_SWITCH_DELAY = 5
COMMENT_TRIGGER_SELECTOR = (
    ".lite-detail-page_reply, "
    "button[class*='reply'], "
    "a[class*='reply'], "
    "[role='button'][class*='reply'], "
    "button[class*='comment'], "
    "a[class*='comment'], "
    "[role='button'][class*='comment']"
)
COMMENT_EDITOR_SELECTOR = (
    "textarea.comment-send_textarea, "
    "textarea, "
    "input[type='text'], "
    "[contenteditable='true'], "
    "[contenteditable=true]"
)
COMMENT_SEND_SELECTOR = (
    "button.comment-send_btn, "
    ".comment-send_btn, "
    "button[type='submit'], "
    "[class*='send']"
)


def choose_reply_template() -> str:
    templates = REPLY_TEMPLATES if REPLY_TEMPLATES != CONFIG_REPLY_TEMPLATES else load_templates()
    if not templates:
        raise RuntimeError("REPLY_TEMPLATES is empty")
    return templates[0]


def _make_scenario(reply_text: str) -> list[dict]:
    reply_literal = json.dumps(reply_text, ensure_ascii=False)
    editor_selector_literal = json.dumps(COMMENT_EDITOR_SELECTOR)
    return [
        {"scroll": {"element": "body", "selector": "bottom"}},
        {"wait": 1500},
        {"click": {"selector": COMMENT_TRIGGER_SELECTOR}},
        {"wait": 1200},
        {
            "execute": {
                "script": (
                    f"const editorSelector = {editor_selector_literal};"
                    "const editor = document.querySelector(editorSelector);"
                    "const body = document.body ? document.body.innerText : '';"
                    "return {"
                    "comment_editor_visible: !!(editor && editor.offsetParent !== null),"
                    "active_tag: document.activeElement ? document.activeElement.tagName : null,"
                    "body_sample: body.slice(0, 500)"
                    "};"
                ),
                "timeout": 1000,
            }
        },
        {"wait_for_selector": {"selector": COMMENT_EDITOR_SELECTOR, "state": "visible", "timeout": 5000}},
        {"fill": {"selector": COMMENT_EDITOR_SELECTOR, "value": reply_text, "clear": True}},
        {"wait": 500},
        {"click": {"selector": COMMENT_SEND_SELECTOR}},
        {"wait": 3000},
        {
            "execute": {
                "script": (
                    f"const target = {reply_literal};"
                    "const body = document.body ? document.body.innerText : '';"
                    "return {reply_visible: body.includes(target), body_sample: body.slice(0, 500)};"
                ),
                "timeout": 1000,
            }
        },
    ]


def _configured_cookies() -> list[str]:
    if COOKIES is not _config.COOKIES:
        return list(COOKIES)
    raw_cookies = getattr(_config, "WEIBO_COOKIES", "")
    if raw_cookies:
        return _config._split_cookies(raw_cookies)
    return list(COOKIES)


def _get_cookie_for_index(index: int) -> int:
    cookies = _configured_cookies()
    if not cookies:
        return 0
    return index % len(cookies)


def _make_reply_session(lead: dict, cookie_index: int) -> str:
    lead_id = lead.get("id") or lead.get("comment_id") or lead.get("post_id") or "unknown"
    safe_lead_id = "".join(ch if ch.isalnum() else "-" for ch in str(lead_id))[:40]
    return f"weibo-reply-{cookie_index}-{safe_lead_id}-{uuid4().hex[:12]}"


def _validate_scrapfly_scenario(response) -> tuple[bool, str]:
    if not getattr(response, "scrape_success", False):
        error = getattr(response, "error", None) or {}
        message = error.get("message") if isinstance(error, dict) else None
        return False, message or "Scrapfly scrape failed"

    result = getattr(response, "scrape_result", None) or {}
    scenario = (result.get("browser_data") or {}).get("js_scenario")
    if not scenario:
        return False, "Scrapfly did not return js_scenario execution details"

    failed_steps = []
    verification_seen = False
    for step in scenario.get("steps") or []:
        if step.get("success") is False or step.get("executed") is False:
            action = step.get("action", "unknown")
            detail = step.get("error") or step.get("result") or "not executed"
            failed_steps.append(f"{action}: {detail}")
        if step.get("action") == "execute" and isinstance(step.get("result"), dict):
            result = step["result"]
            if result.get("comment_editor_visible") is False:
                return False, "comment editor not visible after opening reply"
            if "reply_visible" in result:
                verification_seen = True
                if result.get("reply_visible") is not True:
                    return False, "Reply text not visible after send; Weibo may have blocked, hidden, or rejected it"

    if failed_steps:
        return False, "Scrapfly js_scenario failed: " + "; ".join(failed_steps)

    if not verification_seen:
        return False, "Scrapfly did not confirm reply text is visible after send"

    return True, "Scrapfly js_scenario completed"


def _send_real_reply(lead: dict, reply_text: str, cookie_index: int = 0) -> tuple[bool, str]:
    if not SCRAPFLY_KEY:
        raise RuntimeError("SCRAPFLY_KEY is not configured")
    cookies = _configured_cookies()
    if not cookies:
        raise RuntimeError("WEIBO_COOKIES is not configured")

    session_name = _make_reply_session(lead, cookie_index)
    client = ScrapflyClient(key=SCRAPFLY_KEY)
    response = client.scrape(
        ScrapeConfig(
            url=f"https://m.weibo.cn/detail/{lead['post_id']}",
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                "Cookie": cookies[cookie_index % len(cookies)],
            },
            asp=True,
            proxy_pool="public_residential_pool",
            country="cn,hk",
            render_js=True,
            session=session_name,
            session_sticky_proxy=True,
            correlation_id=session_name,
            tags=["weibo-reply", f"lead:{lead.get('id', 'unknown')}", f"account:{cookie_index}"],
            debug=True,
            js_scenario=_make_scenario(reply_text),
        )
    )
    ok, info = _validate_scrapfly_scenario(response)
    if not ok:
        return False, info
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
        else:
            update_lead_status(lead["id"], "failed", info)
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
    auto_match: bool = False,
) -> int:
    if lead_ids is None:
        leads = get_pending_leads(limit=limit)
    else:
        leads = get_leads_by_ids([int(lead_id) for lead_id in lead_ids])

    selected_text = reply_text or ("" if auto_match else choose_reply_template())
    if dry_run is True:
        confirm_real_send = False

    replied = 0
    for index, lead in enumerate(leads):
        if auto_match:
            selected_text_for_lead = _config.get_template_by_keyword(lead.get("keyword") or "")
        else:
            selected_text_for_lead = selected_text
        cookie_index = _get_cookie_for_index(index // REPLIES_PER_ACCOUNT)
        if index > 0 and index % REPLIES_PER_ACCOUNT == 0:
            time.sleep(ACCOUNT_SWITCH_DELAY)

        try:
            ok, info = reply_to_lead(
                lead,
                reply_text=selected_text_for_lead,
                confirm_real_send=confirm_real_send,
                cookie_index=cookie_index,
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

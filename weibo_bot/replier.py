from __future__ import annotations

import json
import re
import threading
import time
from html import unescape
from http.cookies import SimpleCookie
from uuid import uuid4
from typing import Callable


_pause_event = threading.Event()
_cancel_event = threading.Event()


def pause_run() -> None:
    _pause_event.set()


def resume_run() -> None:
    _pause_event.clear()


def cancel_run() -> None:
    _cancel_event.set()


def clear_pause_state() -> None:
    _pause_event.clear()
    _cancel_event.clear()


def is_paused() -> bool:
    return _pause_event.is_set()


def _wait_while_paused() -> bool:
    """Block while paused. Return False if cancelled."""
    while _pause_event.is_set():
        if _cancel_event.is_set():
            return False
        time.sleep(0.3)
    return not _cancel_event.is_set()

import requests
from scrapfly import ScrapeConfig, ScrapflyClient

from . import config as _config
from .config import (
    COOKIES,
    ENABLE_REAL_REPLIES,
    MAX_REPLIES_PER_RUN,
    REPLY_DELAY,
    REPLIES_PER_ACCOUNT,
    REPLY_TEMPLATES as CONFIG_REPLY_TEMPLATES,
    SCRAPFLY_KEY,
)
from .db import (
    get_lead,
    get_leads_by_ids,
    get_pending_leads,
    set_sent_comment,
    update_lead_status,
)
from .local_llm import generate_reply_for_lead
from .template_store import load_templates

REPLY_TEMPLATES = CONFIG_REPLY_TEMPLATES
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


def _plain_comment_text(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return unescape(text).strip()


def _make_scenario(
    reply_text: str,
    comment_id: str | None = None,
    user_name: str | None = None,
    comment_text: str | None = None,
) -> list[dict]:
    reply_literal = json.dumps(reply_text, ensure_ascii=False)
    comment_id_literal = json.dumps(str(comment_id or ""), ensure_ascii=False)
    user_name_literal = json.dumps(str(user_name or ""), ensure_ascii=False)
    comment_text_literal = json.dumps(_plain_comment_text(comment_text), ensure_ascii=False)
    trigger_selector_literal = json.dumps(COMMENT_TRIGGER_SELECTOR)
    editor_selector_literal = json.dumps(COMMENT_EDITOR_SELECTOR)
    return [
        {"scroll": {"element": "body", "selector": "bottom"}},
        {"wait": 1500},
        {
            "execute": {
                "script": (
                    f"const targetCommentId = {comment_id_literal};"
                    f"const targetUserName = {user_name_literal};"
                    f"const targetCommentText = {comment_text_literal};"
                    f"const replySelector = {trigger_selector_literal};"
                    "const candidates = Array.from(document.querySelectorAll('*'));"
                    "function visibleText(node) { return String(node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim(); }"
                    "function hasTargetId(node) {"
                    "  if (!targetCommentId) return false;"
                    "  const attrs = ['id', 'data-id', 'data-comment-id', 'comment_id', 'mid', 'omid'];"
                    "  if (attrs.some(name => (node.getAttribute && node.getAttribute(name) || '').includes(targetCommentId))) return true;"
                    "  if ((node.href || '').includes(targetCommentId)) return true;"
                    "  if ((node.dataset && Object.values(node.dataset).some(value => String(value).includes(targetCommentId)))) return true;"
                    "  return false;"
                    "}"
                    "function hasTargetText(node) {"
                    "  const text = visibleText(node);"
                    "  if (!text || text.length > 1200) return false;"
                    "  const hasUser = targetUserName ? text.includes(targetUserName) : true;"
                    "  const hasComment = targetCommentText ? text.includes(targetCommentText) : false;"
                    "  return hasUser && hasComment;"
                    "}"
                    "let marker = candidates.find(hasTargetId);"
                    "let foundBy = marker ? 'comment_id' : null;"
                    "if (!marker) {"
                    "  const textMatches = candidates.filter(hasTargetText).sort((a, b) => visibleText(a).length - visibleText(b).length);"
                    "  marker = textMatches[0] || null;"
                    "  foundBy = marker ? 'user_and_text' : null;"
                    "}"
                    "let target = marker ? marker.closest('[data-id], [comment_id], article, section, li, .comment, .card, .weibo-og, .lite-page-list') : null;"
                    "if (!target && marker) target = marker.parentElement;"
                    "const searchRoot = target || document;"
                    "const buttons = Array.from(searchRoot.querySelectorAll(replySelector));"
                    "function buttonText(el) {"
                    "  return String(el.innerText || el.textContent || el.getAttribute('aria-label') || el.className || '').toLowerCase();"
                    "}"
                    "const replyButton = buttons.find(el => {"
                    "  const text = buttonText(el);"
                    "  return text.includes('reply') || text.includes('comment');"
                    "})"
                    "  || buttons[0];"
                    "let menuReplyButton = null;"
                    "if (replyButton) {"
                    "  replyButton.scrollIntoView({block: 'center'});"
                    "  replyButton.click();"
                    "} else if (target) {"
                    "  target.scrollIntoView({block: 'center'});"
                    "  target.click();"
                    "  await new Promise(resolve => setTimeout(resolve, 1000));"
                    "  const menuItems = Array.from(document.querySelectorAll('button, a, [role=\"button\"], div, span'));"
                    "  menuReplyButton = menuItems.find(el => visibleText(el) === '\\u56de\\u590d')"
                    "    || menuItems.find(el => buttonText(el).includes('reply'));"
                    "  if (menuReplyButton) menuReplyButton.click();"
                    "}"
                    "return {"
                    "  target_comment_id: targetCommentId || null,"
                    "  target_user_name: targetUserName || null,"
                    "  target_comment_text: targetCommentText || null,"
                    "  target_comment_found: targetCommentId ? !!target : true,"
                    "  target_comment_found_by: foundBy,"
                    "  reply_button_clicked: !!(replyButton || menuReplyButton),"
                    "  menu_reply_clicked: !!menuReplyButton,"
                    "  target_sample: target ? (target.innerText || '').slice(0, 300) : '',"
                    "  body_sample: (document.body ? document.body.innerText : '').slice(0, 500)"
                    "};"
                ),
                "timeout": 3000,
            }
        },
        {"wait": 6000},
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


def _compose_reply_url(lead: dict) -> str:
    return (
        "https://m.weibo.cn/compose/reply"
        f"?id={lead['post_id']}&reply={lead['comment_id']}&withReply=1"
    )


def _session_from_cookie(raw_cookie: str) -> requests.Session:
    session = requests.Session()
    jar = SimpleCookie()
    jar.load(raw_cookie)
    for morsel in jar.values():
        session.cookies.set(morsel.key, morsel.value, domain=".weibo.cn", path="/")
    return session


def _extract_st(html: str) -> str:
    match = re.search(r"st:\s*'([^']+)'", html)
    if not match:
        raise RuntimeError("st not found in compose reply page")
    return match.group(1)


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
            if result.get("target_comment_found") is False:
                target = result.get("target_comment_id") or "unknown"
                return False, f"target comment not found: {target}"
            if result.get("reply_button_clicked") is False:
                return False, "reply button not found inside target comment"
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
    cookies = _configured_cookies()
    if not cookies:
        raise RuntimeError("WEIBO_COOKIES is not configured")
    raw_cookie = cookies[cookie_index % len(cookies)]
    compose_url = _compose_reply_url(lead)
    session = _session_from_cookie(raw_cookie)
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "X-Requested-With": "XMLHttpRequest",
        "MWeibo-Pwa": "1",
        "Referer": compose_url,
        "Origin": "https://m.weibo.cn",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    compose_response = session.get(compose_url, headers=headers, timeout=30)
    compose_response.raise_for_status()
    st = _extract_st(compose_response.text)

    xsrf_token = session.cookies.get("XSRF-TOKEN", domain="m.weibo.cn") or session.cookies.get("XSRF-TOKEN")
    if xsrf_token:
        headers["X-XSRF-TOKEN"] = xsrf_token

    payload = {
        "content": reply_text,
        "mid": str(lead["post_id"]),
        "cid": str(lead["comment_id"]),
        "st": st,
        "_spr": "screen:390x844",
    }
    api_response = session.post(
        "https://m.weibo.cn/api/comments/reply",
        headers=headers,
        data=payload,
        timeout=30,
    )
    api_response.raise_for_status()
    body = api_response.json()
    if body.get("ok", 0) > 0:
        data = body.get("data") or {}
        sent_id = str(data.get("id") or data.get("rootid") or "") or None
        return True, {"text": reply_text, "sent_comment_id": sent_id}
    return False, body.get("msg") or body.get("url") or json.dumps(body, ensure_ascii=False)


def reply_to_lead(
    lead: dict,
    reply_text: str,
    confirm_real_send: bool = False,
    cookie_index: int = 0,
) -> tuple[bool, str]:
    if ENABLE_REAL_REPLIES and confirm_real_send:
        ok, info = _send_real_reply(lead, reply_text, cookie_index=cookie_index)
        if ok:
            sent_id = info.get("sent_comment_id") if isinstance(info, dict) else None
            update_lead_status(lead["id"], "replied", reply_text)
            set_sent_comment(lead["id"], sent_id, cookie_index)
            return True, reply_text
        update_lead_status(lead["id"], "failed", info)
        return False, info

    update_lead_status(lead["id"], "reviewed", reply_text)
    return True, reply_text


def recall_reply(lead_id: int) -> tuple[bool, str]:
    lead = get_lead(lead_id)
    if not lead:
        return False, "lead not found"
    if lead.get("status") != "replied":
        return False, f"only replied leads can be recalled (current: {lead.get('status')})"
    sent_comment_id = lead.get("sent_comment_id")
    if not sent_comment_id:
        return False, "缺少已发送评论的 id，无法撤回（本条是撤回功能上线前发的）"
    cookies = _configured_cookies()
    if not cookies:
        return False, "WEIBO_COOKIES is not configured"
    cookie_index = int(lead.get("cookie_index") or 0)
    raw_cookie = cookies[cookie_index % len(cookies)]
    session = _session_from_cookie(raw_cookie)
    # fetch any compose page on mobile site to get a fresh st token
    st_page = session.get(
        f"https://m.weibo.cn/compose/reply?id={lead['post_id']}&reply={sent_comment_id}",
        headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "MWeibo-Pwa": "1",
        },
        timeout=30,
    )
    st_page.raise_for_status()
    st = _extract_st(st_page.text)
    xsrf_token = session.cookies.get("XSRF-TOKEN", domain="m.weibo.cn") or session.cookies.get("XSRF-TOKEN")
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "X-Requested-With": "XMLHttpRequest",
        "MWeibo-Pwa": "1",
        "Referer": f"https://m.weibo.cn/detail/{lead['post_id']}",
        "Origin": "https://m.weibo.cn",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    if xsrf_token:
        headers["X-XSRF-TOKEN"] = xsrf_token
    payload = {
        "cid": str(sent_comment_id),
        "mid": str(lead["post_id"]),
        "st": st,
        "_spr": "screen:390x844",
    }
    response = session.post(
        "https://m.weibo.cn/comments/destroy",
        headers=headers,
        data=payload,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("ok", 0) > 0:
        update_lead_status(lead_id, "pending")
        set_sent_comment(lead_id, None, cookie_index)
        return True, "已从微博撤回该评论，已重置为待发送"
    return False, body.get("msg") or json.dumps(body, ensure_ascii=False)


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
    closed_post_ids: set[str] = set()
    clear_pause_state()
    for index, lead in enumerate(leads):
        if not _wait_while_paused():
            if progress_callback:
                progress_callback(lead=lead, ok=False, current=index + 1, total=len(leads), info="已取消")
            break
        post_id_str = str(lead.get("post_id") or "")
        if post_id_str and post_id_str in closed_post_ids:
            info = "同帖其他评论因对方关闭评论权限已失败，自动跳过"
            update_lead_status(lead["id"], "skipped", info)
            if progress_callback:
                progress_callback(lead=lead, ok=False, current=index + 1, total=len(leads), info=info)
            continue

        if auto_match:
            selected_text_for_lead = generate_reply_for_lead(lead)
            if not selected_text_for_lead:
                info = "评论与美业展会不相关，已跳过"
                update_lead_status(lead["id"], "skipped", info)
                if progress_callback:
                    progress_callback(lead=lead, ok=False, current=index + 1, total=len(leads), info=info)
                continue
        else:
            selected_text_for_lead = selected_text
        cookie_index = _get_cookie_for_index(index // REPLIES_PER_ACCOUNT)

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
        if not ok and isinstance(info, str) and ("对方的设置" in info or "不能评论" in info) and post_id_str:
            closed_post_ids.add(post_id_str)
        if progress_callback:
            progress_callback(lead=lead, ok=ok, current=index + 1, total=len(leads), info=info)
        replied += 1 if ok else 0
        if index < len(leads) - 1:
            next_index = index + 1
            if next_index % REPLIES_PER_ACCOUNT == 0:
                time.sleep(ACCOUNT_SWITCH_DELAY)
            else:
                time.sleep(REPLY_DELAY)
    return replied


if __name__ == "__main__":
    count = run_reply()
    print(f"reply run complete: {count}")

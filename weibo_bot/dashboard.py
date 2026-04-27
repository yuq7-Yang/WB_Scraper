from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import queue
import threading
import webbrowser

from flask import Flask, Response, jsonify, make_response, redirect, render_template_string, request, session, url_for

from . import db, keyword_store, template_store
from .config import (
    DEFAULT_MAX_PER_KEYWORD,
    DEFAULT_MAX_TOTAL,
    ENABLE_REAL_REPLIES,
    KEYWORDS,
    LOCAL_LLM_ENABLED,
)
from .local_llm import sanitize_comment_text
from .replier import cancel_run, is_paused, pause_run, recall_reply, resume_run, run_reply
from .scraper import run_scrape


app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "cibe-weibo-dashboard-login")
event_queue: queue.Queue[dict] = queue.Queue()

AUTH_USERNAME = os.getenv("DASHBOARD_USERNAME", "CIBE")
AUTH_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "cibe8888")
REMEMBER_COOKIE = "remember_login"
REMEMBER_MAX_AGE = 60 * 60 * 24 * 365 * 5
PUBLIC_ENDPOINTS = {"login", "static"}

CSV_COLUMNS = [
    "user_name",
    "location",
    "comment_text",
    "comment_id",
    "post_id",
    "keyword",
    "lead_type",
    "intent_score",
    "scraped_at",
    "status",
    "reply_text",
    "replied_at",
]


def _csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _serialize_lead(lead: dict) -> dict:
    row = dict(lead)
    row["comment_text"] = sanitize_comment_text(row.get("comment_text"))
    return row


def _build_remember_token() -> str:
    digest = hmac.new(
        app.secret_key.encode("utf-8"),
        f"{AUTH_USERNAME}:{AUTH_PASSWORD}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{AUTH_USERNAME}:{digest}"


def _has_valid_remember_cookie() -> bool:
    token = request.cookies.get(REMEMBER_COOKIE, "")
    return hmac.compare_digest(token, _build_remember_token())


def _is_logged_in() -> bool:
    return bool(session.get("logged_in"))


def _login_user() -> None:
    session["logged_in"] = True


def _logout_user() -> None:
    session.clear()


def _unauthorized_response():
    if request.path.startswith("/api/"):
        return jsonify({"error": "auth_required"}), 401
    return redirect(url_for("login", next=request.path))


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if _is_logged_in():
        return None
    if _has_valid_remember_cookie():
        _login_user()
        return None
    return _unauthorized_response()


LOGIN_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CIBE 登录</title>
<style>
  :root {
    --bg-top: #fff4e8;
    --bg-bottom: #f4d7d7;
    --panel: rgba(255, 255, 255, 0.92);
    --ink: #2b2320;
    --muted: #7a6b65;
    --line: rgba(110, 72, 55, 0.14);
    --accent: #a43b2f;
    --accent-deep: #7d281f;
    --shadow: 0 24px 80px rgba(122, 57, 37, 0.18);
  }
  * { box-sizing: border-box; }
  body {
    align-items: center;
    background:
      radial-gradient(circle at top left, rgba(255,255,255,.72), transparent 36%),
      linear-gradient(135deg, var(--bg-top), var(--bg-bottom));
    color: var(--ink);
    display: flex;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    justify-content: center;
    margin: 0;
    min-height: 100vh;
    padding: 24px;
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 28px;
    box-shadow: var(--shadow);
    max-width: 430px;
    overflow: hidden;
    width: 100%;
  }
  .hero {
    background:
      linear-gradient(135deg, rgba(164,59,47,.94), rgba(234,127,89,.86)),
      linear-gradient(120deg, rgba(255,255,255,.2), transparent 50%);
    color: #fff9f5;
    padding: 30px 30px 26px;
  }
  .eyebrow {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .18em;
    margin: 0 0 10px;
    opacity: .82;
    text-transform: uppercase;
  }
  h1 { font-size: 30px; margin: 0 0 10px; }
  .hero p { line-height: 1.7; margin: 0; opacity: .92; }
  form { padding: 28px 30px 30px; }
  label {
    color: var(--muted);
    display: block;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
  }
  .field { margin-bottom: 18px; }
  input {
    background: #fffdfb;
    border: 1px solid #e8d8d2;
    border-radius: 14px;
    color: var(--ink);
    font-size: 15px;
    outline: none;
    padding: 14px 15px;
    width: 100%;
  }
  input:focus {
    border-color: rgba(164,59,47,.5);
    box-shadow: 0 0 0 4px rgba(164,59,47,.12);
  }
  button {
    background: linear-gradient(135deg, var(--accent), var(--accent-deep));
    border: 0;
    border-radius: 14px;
    color: #fff;
    cursor: pointer;
    font-size: 15px;
    font-weight: 700;
    padding: 14px 18px;
    width: 100%;
  }
  .hint { color: var(--muted); font-size: 12px; line-height: 1.6; margin-top: 14px; }
  .error {
    background: #fff2f0;
    border: 1px solid #f0c4ba;
    border-radius: 14px;
    color: #a63a2b;
    font-size: 13px;
    margin-bottom: 16px;
    padding: 12px 14px;
  }
</style>
</head>
<body>
  <div class="card">
    <div class="hero">
      <div class="eyebrow">CIBE Secure Access</div>
      <h1>登录面板</h1>
      <p>请输入固定账号和密码。登录成功后，这台电脑会长期保持可访问状态，直到手动退出登录。</p>
    </div>
    <form method="post" action="/login">
      {% if error %}
      <div class="error">{{ error }}</div>
      {% endif %}
      <input type="hidden" name="next" value="{{ next_url }}">
      <div class="field">
        <label for="username">登录名</label>
        <input id="username" name="username" type="text" autocomplete="username" required>
      </div>
      <div class="field">
        <label for="password">密码</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required>
      </div>
      <button type="submit">进入系统</button>
      <div class="hint">请输入管理员分配的登录信息，验证通过后进入系统。</div>
    </form>
  </div>
</body>
</html>
"""


HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>微博美业拓客面板</title>
<style>
  :root {
    --ink: #1f2937;
    --muted: #667085;
    --line: #e5e7eb;
    --accent: #d81b60;
    --green: #16803c;
    --blue: #2563eb;
    --red: #c62828;
    --amber: #9a5b00;
  }
  * { box-sizing: border-box; }
  body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; color: var(--ink); background: #f7f7f8; }
  header { background: #ffffff; border-bottom: 1px solid var(--line); padding: 16px 24px; display: flex; justify-content: space-between; gap: 16px; align-items: center; }
  .header-actions { align-items: center; display: flex; gap: 12px; }
  .brand { align-items: center; display: flex; gap: 12px; min-width: 0; }
  .brand-logo { display: block; height: 40px; max-width: 180px; object-fit: contain; }
  .brand-title { color: #c2185b; font-size: 20px; font-weight: 800; line-height: 1.3; overflow-wrap: anywhere; }
  h2 { font-size: 15px; margin: 0 0 10px; }
  main { padding: 16px 24px 32px; }
  button, .export { border: 0; border-radius: 6px; color: #ffffff; cursor: pointer; display: inline-block; font-size: 14px; font-weight: 700; padding: 9px 16px; text-decoration: none; }
  button:disabled { cursor: not-allowed; opacity: 0.55; }
  .scrape { background: var(--green); }
  .send { background: var(--accent); }
  .blue { background: var(--blue); }
  .export { background: #374151; }
  .outline { background: #ffffff; border: 1px solid #9ca3af; color: #374151; }
  .danger { background: #ffffff; border: 1px solid var(--red); color: var(--red); padding: 5px 10px; }
  .box { background: #ffffff; border: 1px solid var(--line); border-radius: 8px; margin-bottom: 12px; padding: 14px; }
  .kw-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
  .kw-chip { align-items: center; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 8px; cursor: pointer; display: flex; gap: 5px; padding: 6px 10px; user-select: none; }
  .kw-chip .kw-del { background: none; border: 0; color: #9ca3af; cursor: pointer; font-size: 14px; font-weight: 700; padding: 0 2px; }
  .kw-chip .kw-del:hover { color: var(--red); }
  .kw-suggest .kw-chip { background: #eef2ff; border-color: #c7d2fe; color: #3730a3; }
  .kw-suggest .kw-chip.used { background: #e0e7ff; color: #6366f1; opacity: 0.55; }
  .kw-extra { border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; height: 68px; padding: 8px; resize: vertical; width: 100%; }
  .row { align-items: center; display: flex; flex-wrap: wrap; gap: 10px; }
  .row input[type=number] { border: 1px solid #d1d5db; border-radius: 6px; padding: 6px; width: 90px; }
  .notice { color: var(--muted); font-size: 13px; margin-left: auto; }
  .stats { display: flex; flex-wrap: wrap; gap: 18px; }
  .progress { height: 7px; background: #e5e7eb; border-radius: 6px; overflow: hidden; margin: 10px 0; }
  .fill { height: 100%; width: 0%; background: var(--accent); transition: width .25s ease; }
  .log { color: var(--muted); font-size: 13px; min-height: 22px; margin-bottom: 12px; }
  .table-wrap { overflow-x: auto; background: #ffffff; border: 1px solid var(--line); border-radius: 8px; }
  table { border-collapse: collapse; min-width: 1120px; width: 100%; }
  th, td { border-bottom: 1px solid #f0f1f3; font-size: 13px; padding: 10px 12px; text-align: left; vertical-align: top; }
  th { background: #f3f4f6; color: #344054; white-space: nowrap; }
  tr:last-child td { border-bottom: 0; }
  .comment { max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pending { color: var(--amber); font-weight: 700; }
  .reviewed { color: var(--blue); font-weight: 700; }
  .replied { color: var(--green); font-weight: 700; }
  .failed { color: var(--red); font-weight: 700; }
  .skipped { color: var(--muted); font-weight: 700; }
  .modal-mask { align-items: center; background: rgba(17, 24, 39, .52); display: none; inset: 0; justify-content: center; position: fixed; z-index: 20; }
  .modal-mask.show { display: flex; }
  .modal { background: #ffffff; border-radius: 8px; max-width: 94vw; padding: 20px; width: 560px; }
  .tpl-list { display: flex; flex-direction: column; gap: 10px; margin: 12px 0; }
  .tpl-item { border: 2px solid #e5e7eb; border-radius: 8px; cursor: pointer; line-height: 1.5; padding: 10px; }
  .tpl-item.selected { border-color: var(--accent); background: #fff0f6; }
  .auto-match { background: #fff0f6; border: 1px solid #f48fb1; border-radius: 8px; margin-bottom: 12px; padding: 10px 12px; }
  .auto-match label { align-items: center; color: #c0386b; cursor: pointer; display: flex; font-weight: 700; gap: 8px; margin: 0; }
  .auto-match input { accent-color: #c0386b; cursor: pointer; height: 16px; width: 16px; }
  .auto-match p { color: #667085; font-size: 12px; margin: 5px 0 0 24px; }
  .tpl-add { border-top: 1px solid var(--line); margin-top: 12px; padding-top: 12px; }
  .tpl-add textarea { border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; min-height: 76px; padding: 8px; resize: vertical; width: 100%; }
  .real-send-confirm { align-items: center; display: flex; gap: 8px; margin-bottom: 14px; }
  .real-send-confirm input { flex: 0 0 auto; margin: 0; }
  .modal-footer { display: flex; gap: 10px; justify-content: flex-end; }
</style>
</head>
<body>
<header>
  <div class="brand">
    <img src="/static/logo.png" alt="CIBE美博会" class="brand-logo" onerror="this.style.display='none'">
    <div class="brand-title">美业精准拓客面板</div>
  </div>
  <div class="header-actions">
    <div id="credits">Credits：请在 Scrapfly Dashboard 查看</div>
    <a class="export" href="/logout">退出登录</a>
  </div>
</header>
<main>
  <section class="box">
    <h2>1. 选择关键词</h2>
    <textarea class="kw-extra" id="kwExtra" placeholder="手动追加关键词，每行一个"></textarea>
    <div class="row" style="margin-top:8px">
      <button class="blue" onclick="addCustomKeywords()">添加关键词</button>
      <a class="export" href="/api/export.csv">导出 CSV</a>
      <span class="notice" id="kwAddMsg"></span>
      <span class="notice" id="realSendNotice">{{ real_send_notice }}</span>
    </div>
    <div style="color:var(--muted); font-size:13px; margin:12px 0 6px">已选采集关键词（点击 × 移除）：</div>
    <div class="kw-grid" id="kwActive"></div>
    <div class="row" style="margin-top:10px">
      <label>每个关键词最多采集 <input type="number" id="maxPerKw" value="{{ default_max_per_keyword }}" min="1" max="200"> 条</label>
      <label>总条数上限 <input type="number" id="maxTotal" value="{{ default_max_total }}" min="1" max="5000"> 条</label>
      <button class="scrape" id="scrapeBtn" onclick="startScrape()">开始采集</button>
      <button class="outline" onclick="clearActiveKeywords()">清空已选</button>
    </div>
  </section>

  <div class="progress"><div class="fill" id="progress"></div></div>
  <div class="log" id="log">等待操作...</div>

  <section class="box stats">
    <span>共找到 <b id="total">0</b> 人</span>
    <span>待回复 <b id="pending">0</b></span>
    <span>已预演 <b id="reviewed">0</b></span>
    <span>已回复 <b id="replied">0</b></span>
    <span>失败 <b id="failed">0</b></span>
    <span>已跳过 <b id="skipped">0</b></span>
  </section>

  <section class="box row">
    <button class="outline" onclick="selectAllPending()">全选可发送</button>
    <button class="outline" onclick="clearSelection()">清空勾选</button>
    <span id="selCount">已勾选 0 人</span>
    <button class="send" onclick="openModal([])">发送评论</button>
    <button class="outline" onclick="batchRetry()">批量重试</button>
    <button class="outline" id="pauseBtn" onclick="togglePause()">暂停发送</button>
    <button class="danger" onclick="deleteSelected()">批量删除</button>
  </section>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th><input type="checkbox" id="checkAll" onchange="toggleAll(this)"></th>
          <th>用户名</th>
          <th>属地</th>
          <th>评论内容</th>
          <th>关键词</th>
          <th>帖子链接</th>
          <th>预演/发送话术</th>
          <th>操作</th>
          <th>删除</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>
</main>

<div class="modal-mask" id="modalMask">
  <div class="modal">
    <h2 id="modalTitle">选择话术</h2>
    <div class="auto-match">
      <label>
        <input type="checkbox" id="autoMatchToggle" checked onchange="handleAutoMatchToggle(this.checked)">
        根据采集关键词自动匹配话术
      </label>
      <p>每条评论按采集关键词选话术，结尾统一引导私信获取门票</p>
    </div>
    <div class="tpl-list" id="templateListWrap"></div>
    <div class="tpl-add">
      <label for="newTemplateText">新增话术</label>
      <textarea id="newTemplateText" placeholder="输入一条新的回复话术"></textarea>
      <div class="row" style="margin-top:8px">
        <button class="blue" id="saveTemplateBtn" onclick="saveTemplate()">保存话术</button>
        <span class="notice" id="templateSaveMsg"></span>
      </div>
    </div>
    <label class="real-send-confirm">
      <input type="checkbox" id="confirmRealSend">
      我确认真实发送评论（仅当 .env 中 ENABLE_REAL_REPLIES=true 时生效）
    </label>
    <div class="modal-footer">
      <button class="outline" onclick="closeModal()">取消</button>
      <button class="send" onclick="confirmSend()">确认发送</button>
    </div>
  </div>
</div>

<script>
let ACTIVE_KEYWORDS = [];

function persistActive() {
  fetch("/api/keywords", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({keywords: ACTIVE_KEYWORDS})
  });
}

function loadActiveFromServer() {
  return fetch("/api/keywords").then(r => r.json()).then(data => {
    if (Array.isArray(data)) ACTIVE_KEYWORDS = data;
  }).catch(() => {});
}
let TEMPLATES = {{ templates|tojson }};
const REAL_SEND_ENABLED = {{ real_send_enabled|tojson }};
const statusLabels = {
  pending: ["待回复", "pending"],
  reviewed: ["已预演", "reviewed"],
  replied: ["已回复", "replied"],
  failed: ["失败", "failed"],
  skipped: ["已跳过", "skipped"]
};
let pendingIds = [];

function setText(node, value) { node.textContent = value || ""; }

function cell(value, className) {
  const td = document.createElement("td");
  if (className) td.className = className;
  setText(td, value);
  return td;
}

function postLink(postId) {
  const td = document.createElement("td");
  if (!postId) return td;
  const link = document.createElement("a");
  link.href = `https://m.weibo.cn/detail/${encodeURIComponent(postId)}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "查看帖子";
  td.appendChild(link);
  return td;
}

function buildActiveGrid() {
  const grid = document.getElementById("kwActive");
  grid.replaceChildren();
  if (!ACTIVE_KEYWORDS.length) {
    const hint = document.createElement("span");
    hint.style.color = "#9ca3af";
    hint.style.fontSize = "13px";
    hint.textContent = "暂未选择，请在上方手动追加关键词后添加";
    grid.appendChild(hint);
    return;
  }
  ACTIVE_KEYWORDS.forEach(kw => {
    const chip = document.createElement("span");
    chip.className = "kw-chip";
    chip.textContent = kw;
    const del = document.createElement("button");
    del.type = "button";
    del.className = "kw-del";
    del.title = "移除";
    del.textContent = "×";
    del.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      removeActiveKeyword(kw);
    });
    chip.appendChild(del);
    grid.appendChild(chip);
  });
}

function removeActiveKeyword(kw) {
  ACTIVE_KEYWORDS = ACTIVE_KEYWORDS.filter(item => item !== kw);
  buildActiveGrid();
  persistActive();
}

function clearActiveKeywords() {
  ACTIVE_KEYWORDS = [];
  buildActiveGrid();
  persistActive();
}

function addCustomKeywords() {
  const textarea = document.getElementById("kwExtra");
  const msg = document.getElementById("kwAddMsg");
  const entries = textarea.value.split("\\n").map(item => item.trim()).filter(Boolean);
  if (!entries.length) { msg.textContent = "请输入关键词"; return; }
  const existing = new Set(ACTIVE_KEYWORDS);
  const added = [];
  entries.forEach(keyword => {
    if (!existing.has(keyword)) { ACTIVE_KEYWORDS.push(keyword); existing.add(keyword); added.push(keyword); }
  });
  buildActiveGrid();
  textarea.value = "";
  msg.textContent = added.length ? `已添加 ${added.length} 个` : "关键词已存在";
  if (added.length) persistActive();
}

function getSelectedKeywords() {
  return [...ACTIVE_KEYWORDS];
}

function canSelectForReply(status) {
  return ["pending", "reviewed", "failed", "skipped"].includes(status);
}

function canRetry(status) {
  return ["reviewed", "failed", "skipped"].includes(status);
}

function startScrape() {
  const keywords = getSelectedKeywords();
  if (!keywords.length) {
    alert("请先从提示中点击选取，或手动追加关键词后再开始采集");
    return;
  }
  const pending = document.getElementById("kwExtra").value.trim();
  if (pending) {
    alert("检测到手动追加的关键词未添加，请先点击“添加关键词”再开始采集。");
    return;
  }
  document.getElementById("scrapeBtn").disabled = true;
  document.getElementById("log").textContent = "采集任务已启动...";
  fetch("/api/scrape", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      keywords,
      max_per_keyword: parseInt(document.getElementById("maxPerKw").value) || 2,
      max_total: parseInt(document.getElementById("maxTotal").value) || 20
    })
  }).finally(() => {
    setTimeout(() => {
      document.getElementById("scrapeBtn").disabled = false;
      refreshTable();
    }, 300);
  });
}

function rowCheck(id) {
  const td = document.createElement("td");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "row-check";
  checkbox.value = id;
  checkbox.addEventListener("change", updateSelCount);
  td.appendChild(checkbox);
  return td;
}

function refreshTable() {
  const prevChecked = new Set(getCheckedIds().map(String));
  const checkAllBox = document.getElementById("checkAll");
  const checkAllWas = checkAllBox ? checkAllBox.checked : false;
  fetch("/api/leads").then(r => r.json()).then(data => {
    document.getElementById("total").textContent = data.length;
    document.getElementById("pending").textContent = data.filter(d => d.status === "pending").length;
    document.getElementById("reviewed").textContent = data.filter(d => d.status === "reviewed").length;
    document.getElementById("replied").textContent = data.filter(d => d.status === "replied").length;
    document.getElementById("failed").textContent = data.filter(d => d.status === "failed").length;
    document.getElementById("skipped").textContent = data.filter(d => d.status === "skipped").length;
    const tbody = document.getElementById("tableBody");
    tbody.replaceChildren();
    data.forEach(row => {
      const tr = document.createElement("tr");
      tr.appendChild(canSelectForReply(row.status) ? rowCheck(row.id) : cell(""));
      tr.appendChild(cell(row.user_name));
      tr.appendChild(cell(row.location));
      tr.appendChild(cell(row.comment_text, "comment"));
      tr.appendChild(cell(row.keyword));
      tr.appendChild(postLink(row.post_id));
      const [label, cls] = statusLabels[row.status] || [row.status, ""];
      const replyCell = document.createElement("td");
      if (label) {
        const badge = document.createElement("span");
        badge.className = cls;
        badge.style.marginRight = "6px";
        badge.textContent = `[${label}] `;
        replyCell.appendChild(badge);
      }
      replyCell.appendChild(document.createTextNode(row.reply_text || ""));
      tr.appendChild(replyCell);
      const action = document.createElement("td");
      action.style.whiteSpace = "nowrap";
      if (row.status === "pending") {
        const send = document.createElement("button");
        send.className = "outline";
        send.textContent = "单发";
        send.addEventListener("click", () => openModal([row.id]));
        action.appendChild(send);
      }
      if (canRetry(row.status)) {
        const retry = document.createElement("button");
        retry.className = "danger";
        retry.textContent = "重试";
        retry.addEventListener("click", () => retryLead(row.id));
        retry.style.marginLeft = "4px";
        action.appendChild(retry);
      }
      if (row.status === "replied") {
        const recall = document.createElement("button");
        recall.className = "outline";
        recall.textContent = "撤回";
        recall.title = row.sent_comment_id ? "从微博删除已发送的评论" : "缺少记录，无法撤回";
        if (!row.sent_comment_id) recall.disabled = true;
        recall.addEventListener("click", () => recallReply(row.id));
        action.appendChild(recall);
      }
      tr.appendChild(action);
      const delCell = document.createElement("td");
      const del = document.createElement("button");
      del.className = "danger";
      del.textContent = "删除";
      del.addEventListener("click", () => deleteLeads([row.id]));
      delCell.appendChild(del);
      tr.appendChild(delCell);
      tbody.appendChild(tr);
    });
    document.querySelectorAll(".row-check").forEach(item => {
      if (prevChecked.has(String(item.value))) item.checked = true;
    });
    if (checkAllBox) checkAllBox.checked = checkAllWas && prevChecked.size > 0;
    updateSelCount();
  });
}

function toggleAll(source) { document.querySelectorAll(".row-check").forEach(item => item.checked = source.checked); updateSelCount(); }
function selectAllPending() { document.querySelectorAll(".row-check").forEach(item => item.checked = true); updateSelCount(); }
function clearSelection() { document.querySelectorAll(".row-check").forEach(item => item.checked = false); document.getElementById("checkAll").checked = false; updateSelCount(); }
function getCheckedIds() { return [...document.querySelectorAll(".row-check:checked")].map(item => parseInt(item.value)); }
function updateSelCount() { document.getElementById("selCount").textContent = `已勾选 ${getCheckedIds().length} 人`; }

function renderTemplates() {
  const list = document.getElementById("templateListWrap");
  list.replaceChildren();
  TEMPLATES.forEach((template, index) => {
    const label = document.createElement("label");
    label.className = `tpl-item${index === 0 ? " selected" : ""}`;
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "tpl";
    input.value = index;
    input.checked = index === 0;
    label.appendChild(input);
    label.appendChild(document.createTextNode(template));
    label.addEventListener("click", () => {
      document.querySelectorAll(".tpl-item").forEach(item => item.classList.remove("selected"));
      label.classList.add("selected");
      input.checked = true;
    });
    list.appendChild(label);
  });
}

function openModal(ids) {
  pendingIds = ids.length ? ids : getCheckedIds();
  if (!pendingIds.length) {
    alert("请先勾选要回复的用户");
    return;
  }
  document.getElementById("modalTitle").textContent = `选择话术（将处理 ${pendingIds.length} 人）`;
  renderTemplates();
  document.getElementById("newTemplateText").value = "";
  document.getElementById("templateSaveMsg").textContent = "";
  document.getElementById("confirmRealSend").checked = false;
  document.getElementById("autoMatchToggle").checked = true;
  handleAutoMatchToggle(true);
  document.getElementById("modalMask").classList.add("show");
}

function closeModal() { document.getElementById("modalMask").classList.remove("show"); }

function saveTemplate() {
  const input = document.getElementById("newTemplateText");
  const message = document.getElementById("templateSaveMsg");
  const text = input.value.trim();
  if (!text) {
    message.textContent = "请先输入话术";
    return;
  }
  fetch("/api/templates", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text})
  }).then(async response => {
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error || "保存失败");
    }
    return response.json();
  }).then(data => {
    TEMPLATES = data;
    input.value = "";
    message.textContent = "已保存";
    renderTemplates();
  }).catch(error => {
    message.textContent = error.message;
  });
}

function confirmSend() {
  const selected = document.querySelector("input[name=tpl]:checked");
  const autoMatchToggle = document.getElementById("autoMatchToggle");
  const autoMatch = Boolean(autoMatchToggle && autoMatchToggle.checked);
  if (!selected) {
    alert("请选择一条话术");
    return;
  }
  const confirmRealSend = document.getElementById("confirmRealSend").checked;
  if (confirmRealSend && !REAL_SEND_ENABLED) {
    alert("真实发送未开启：请先在 .env 设置 ENABLE_REAL_REPLIES=true 并重启面板。当前将按预演处理。");
  }
  closeModal();
  document.getElementById("log").textContent = `发送任务已启动（${pendingIds.length} 人）...`;
  fetch("/api/reply", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      lead_ids: pendingIds,
      reply_text: TEMPLATES[parseInt(selected.value)],
      confirm_real_send: confirmRealSend,
      auto_match: autoMatch
    })
  }).then(() => refreshTable());
}

function handleAutoMatchToggle(checked) {
  const wrap = document.getElementById("templateListWrap");
  if (!wrap) return;
  wrap.style.opacity = checked ? "0.35" : "1";
  wrap.style.pointerEvents = checked ? "none" : "auto";
}

function retryLead(id) { fetch(`/api/retry/${id}`, {method: "POST"}).then(() => refreshTable()); }

function batchRetry() {
  const ids = getCheckedIds();
  if (!ids.length) { alert("请先勾选要重试的评论"); return; }
  if (!confirm(`将 ${ids.length} 条重置为待回复？重置后可再次发送。`)) return;
  fetch("/api/retry/batch", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({lead_ids: ids})
  }).then(r => r.json()).then(data => {
    document.getElementById("log").textContent = `已重置 ${data.reset || 0} 条为待回复`;
    refreshTable();
  });
}

let isPaused = false;
function togglePause() {
  const url = isPaused ? "/api/reply/resume" : "/api/reply/pause";
  fetch(url, {method: "POST"}).then(r => r.json()).then(data => {
    isPaused = !!data.paused;
    const btn = document.getElementById("pauseBtn");
    btn.textContent = isPaused ? "继续发送" : "暂停发送";
    btn.className = isPaused ? "send" : "outline";
    document.getElementById("log").textContent = isPaused ? "已暂停，点击继续发送恢复" : "已继续发送";
  });
}

function syncPauseState() {
  fetch("/api/reply/state").then(r => r.json()).then(data => {
    isPaused = !!data.paused;
    const btn = document.getElementById("pauseBtn");
    if (btn) {
      btn.textContent = isPaused ? "继续发送" : "暂停发送";
      btn.className = isPaused ? "send" : "outline";
    }
  });
}

function recallReply(id) {
  if (!confirm("确认从微博撤回该评论？这会真实删除已发送的评论。")) return;
  document.getElementById("log").textContent = "撤回中...";
  fetch(`/api/recall/${id}`, {method: "POST"}).then(r => r.json()).then(data => {
    document.getElementById("log").textContent = `${data.ok ? "撤回成功" : "撤回失败"}：${data.info || ""}`;
    refreshTable();
  });
}

function deleteLeads(ids) {
  if (!ids.length) { alert("请先勾选要删除的用户"); return; }
  if (!confirm(`确认删除 ${ids.length} 条记录？此操作不可撤销。`)) return;
  fetch("/api/leads/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({lead_ids: ids})
  }).then(r => r.json()).then(data => {
    document.getElementById("log").textContent = `已删除 ${data.deleted || 0} 条`;
    refreshTable();
  });
}

function deleteSelected() { deleteLeads(getCheckedIds()); }

const stream = new EventSource("/stream");
stream.onmessage = event => {
  const msg = JSON.parse(event.data);
  if (msg.log) document.getElementById("log").textContent = msg.log;
  if (msg.progress !== undefined) document.getElementById("progress").style.width = `${msg.progress}%`;
  if (msg.refresh) refreshTable();
};

loadActiveFromServer().then(() => {
  buildActiveGrid();
});
handleAutoMatchToggle(true);
syncPauseState();
refreshTable();
setInterval(refreshTable, 10000);
</script>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if _is_logged_in() or _has_valid_remember_cookie():
            if _has_valid_remember_cookie():
                _login_user()
            return redirect(url_for("index"))
        return render_template_string(
            LOGIN_HTML,
            error=None,
            next_url=request.args.get("next", "/"),
        )

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    next_url = request.form.get("next") or "/"
    if not next_url.startswith("/"):
        next_url = "/"

    if username != AUTH_USERNAME or password != AUTH_PASSWORD:
        return (
            render_template_string(
                LOGIN_HTML,
                error="登录信息不正确",
                next_url=next_url,
            ),
            200,
        )

    _login_user()
    response = make_response(redirect(next_url))
    response.set_cookie(
        REMEMBER_COOKIE,
        _build_remember_token(),
        max_age=REMEMBER_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )
    return response


@app.route("/logout")
def logout():
    _logout_user()
    response = make_response(redirect(url_for("login")))
    response.delete_cookie(REMEMBER_COOKIE)
    return response


@app.route("/")
def index():
    db.init_db()
    return render_template_string(
        HTML,
        keywords=KEYWORDS,
        templates=template_store.load_templates(),
        default_max_per_keyword=DEFAULT_MAX_PER_KEYWORD,
        default_max_total=DEFAULT_MAX_TOTAL,
        real_send_enabled=ENABLE_REAL_REPLIES,
        real_send_notice="真实发送已开启" if ENABLE_REAL_REPLIES else "真实发送未开启，默认只做预演",
    )


@app.route("/api/leads")
def api_leads():
    db.init_db()
    return jsonify([_serialize_lead(lead) for lead in db.get_all_leads()])


@app.route("/api/keywords", methods=["GET"])
def api_keywords_get():
    return jsonify(keyword_store.load_keywords())


@app.route("/api/keywords", methods=["POST"])
def api_keywords_save():
    body = request.get_json(silent=True) or {}
    try:
        saved = keyword_store.save_keywords(body.get("keywords") or [])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(saved)


@app.route("/api/templates", methods=["GET"])
def api_templates():
    return jsonify(template_store.load_templates())


@app.route("/api/templates", methods=["POST"])
def api_add_template():
    body = request.get_json(silent=True) or {}
    try:
        templates = template_store.add_template(body.get("text", ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(templates)


@app.route("/api/export.csv")
def api_export_csv():
    db.init_db()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for lead in db.get_all_leads():
        lead = _serialize_lead(lead)
        writer.writerow([_csv_safe(lead.get(column)) for column in CSV_COLUMNS])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=weibo_leads.csv"},
    )


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    body = request.get_json(silent=True) or {}
    keywords = body.get("keywords") or KEYWORDS
    max_per_keyword = int(body.get("max_per_keyword") or DEFAULT_MAX_PER_KEYWORD)
    max_total = int(body.get("max_total") or DEFAULT_MAX_TOTAL)

    def task() -> None:
        try:
            def progress(keyword: str, step: int, total: int) -> None:
                event_queue.put(
                    {
                        "log": f"采集中：{keyword} ({step}/{total})",
                        "progress": int(step / total * 100),
                    }
                )

            count = run_scrape(
                keywords=keywords,
                max_per_keyword=max_per_keyword,
                max_total=max_total,
                progress_callback=progress,
            )
            event_queue.put(
                {
                    "log": f"采集完成，共找到 {count} 位意向用户",
                    "progress": 100,
                    "refresh": True,
                }
            )
        except Exception as exc:
            event_queue.put({"log": f"采集未启动：{exc}", "progress": 0, "refresh": True})

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/reply", methods=["POST"])
def api_reply():
    body = request.get_json(silent=True) or {}
    lead_ids = [int(lead_id) for lead_id in body.get("lead_ids", [])]
    templates = template_store.load_templates()
    reply_text = body.get("reply_text") or (templates[0] if templates else "")
    confirm_real_send = bool(body.get("confirm_real_send", False))
    auto_match = bool(body.get("auto_match", False))

    def task() -> None:
        def progress(lead: dict, ok: bool, current: int, total: int, info: str) -> None:
            pct = int(current / total * 100) if total else 100
            status = "完成" if ok else "失败"
            event_queue.put(
                {
                    "log": f"{lead['user_name']} {status} ({current}/{total})",
                    "progress": pct,
                    "refresh": True,
                }
            )

        count = run_reply(
            lead_ids=lead_ids,
            reply_text=reply_text,
            confirm_real_send=confirm_real_send,
            auto_match=auto_match,
            progress_callback=progress,
        )
        event_queue.put({"log": f"发送任务完成，处理 {count} 条", "progress": 100, "refresh": True})

    threading.Thread(target=task, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/retry/<int:lead_id>", methods=["POST"])
def api_retry(lead_id: int):
    db.update_lead_status(lead_id, "pending")
    return jsonify({"status": "reset"})


@app.route("/api/reply/pause", methods=["POST"])
def api_reply_pause():
    pause_run()
    return jsonify({"paused": True})


@app.route("/api/reply/resume", methods=["POST"])
def api_reply_resume():
    resume_run()
    return jsonify({"paused": False})


@app.route("/api/reply/cancel", methods=["POST"])
def api_reply_cancel():
    cancel_run()
    return jsonify({"cancelled": True})


@app.route("/api/reply/state")
def api_reply_state():
    return jsonify({"paused": is_paused()})


@app.route("/api/retry/batch", methods=["POST"])
def api_retry_batch():
    body = request.get_json(silent=True) or {}
    try:
        lead_ids = [int(lead_id) for lead_id in body.get("lead_ids", [])]
    except (TypeError, ValueError):
        return jsonify({"error": "invalid lead_ids"}), 400
    for lead_id in lead_ids:
        db.update_lead_status(lead_id, "pending")
    return jsonify({"reset": len(lead_ids)})


@app.route("/api/recall/<int:lead_id>", methods=["POST"])
def api_recall(lead_id: int):
    try:
        ok, info = recall_reply(lead_id)
    except Exception as exc:
        return jsonify({"ok": False, "info": str(exc)}), 500
    return jsonify({"ok": ok, "info": info})


@app.route("/api/leads/delete", methods=["POST"])
def api_delete_leads():
    body = request.get_json(silent=True) or {}
    raw_ids = body.get("lead_ids") or []
    try:
        lead_ids = [int(lead_id) for lead_id in raw_ids]
    except (TypeError, ValueError):
        return jsonify({"error": "invalid lead_ids"}), 400
    deleted = db.delete_leads(lead_ids)
    return jsonify({"deleted": deleted})


@app.route("/stream")
def stream():
    def generate():
        while True:
            try:
                msg = event_queue.get(timeout=30)
            except queue.Empty:
                msg = {}
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


def main() -> None:
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    open_browser = _env_bool("DASHBOARD_OPEN_BROWSER", True)
    db.init_db()
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

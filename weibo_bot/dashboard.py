from __future__ import annotations

import csv
import io
import json
import queue
import threading
import webbrowser

from flask import Flask, Response, jsonify, render_template_string, request

from . import db, template_store
from .config import (
    DEFAULT_MAX_PER_KEYWORD,
    DEFAULT_MAX_TOTAL,
    ENABLE_REAL_REPLIES,
    BEAUTY_TERMS,
    KEYWORDS,
)
from .replier import run_reply
from .scraper import run_scrape


app = Flask(__name__)
event_queue: queue.Queue[dict] = queue.Queue()

CSV_COLUMNS = [
    "user_name",
    "location",
    "comment_text",
    "comment_id",
    "post_id",
    "keyword",
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
  .brand { align-items: center; display: flex; gap: 12px; min-width: 0; }
  .brand-logo { display: block; height: 40px; max-width: 180px; object-fit: contain; }
  .brand-title { color: #c2185b; font-size: 20px; font-weight: 800; line-height: 1.3; overflow-wrap: anywhere; }
  h1 { margin: 0; font-size: 20px; line-height: 1.3; }
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
  <div id="credits">Credits：请在 Scrapfly Dashboard 查看</div>
</header>
<main>
  <section class="box">
    <h2>① 选择关键词</h2>
    <div class="kw-grid" id="kwGrid"></div>
    <div class="row" style="margin-bottom:10px">
      <button class="outline" onclick="selectAllKeywords()">全选</button>
      <button class="outline" onclick="clearAllKeywords()">清空</button>
      <a class="export" href="/api/export.csv">导出 CSV</a>
      <span class="notice" id="realSendNotice">{{ real_send_notice }}</span>
    </div>
    <textarea class="kw-extra" id="kwExtra" placeholder="手动追加关键词，每行一个"></textarea>
    <div class="row" style="margin-top:10px">
      <label>每个关键词最多采集 <input type="number" id="maxPerKw" value="{{ default_max_per_keyword }}" min="1" max="200"> 条</label>
      <label>总条数上限 <input type="number" id="maxTotal" value="{{ default_max_total }}" min="1" max="5000"> 条</label>
      <button class="scrape" id="scrapeBtn" onclick="startScrape()">开始采集</button>
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
  </section>

  <section class="box row">
    <button class="outline" onclick="selectAllPending()">全选可发送</button>
    <button class="outline" onclick="clearSelection()">清空勾选</button>
    <span id="selCount">已勾选 0 人</span>
    <button class="send" onclick="openModal([])">发送评论</button>
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
          <th>状态</th>
          <th>预演/发送话术</th>
          <th>操作</th>
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
const PRESETS = {{ keywords|tojson }};
let TEMPLATES = {{ templates|tojson }};
const BEAUTY_TERMS = {{ beauty_terms|tojson }};
const REAL_SEND_ENABLED = {{ real_send_enabled|tojson }};
const statusLabels = {
  pending: ["待回复", "pending"],
  reviewed: ["已预演", "reviewed"],
  replied: ["已回复", "replied"],
  failed: ["失败", "failed"]
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

function buildKwGrid() {
  const grid = document.getElementById("kwGrid");
  grid.replaceChildren();
  PRESETS.forEach(kw => {
    const label = document.createElement("label");
    label.className = "kw-chip";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "kw";
    input.value = kw;
    label.appendChild(input);
    label.appendChild(document.createTextNode(kw));
    grid.appendChild(label);
  });
}

function selectAllKeywords() { document.querySelectorAll("input[name=kw]").forEach(item => item.checked = true); }
function clearAllKeywords() { document.querySelectorAll("input[name=kw]").forEach(item => item.checked = false); }

function getSelectedKeywords() {
  const checked = [...document.querySelectorAll("input[name=kw]:checked")].map(item => item.value);
  const extra = document.getElementById("kwExtra").value.split("\\n").map(item => item.trim()).filter(Boolean);
  return [...new Set([...checked, ...extra])];
}

function isBeautyKeyword(keyword) {
  return BEAUTY_TERMS.some(term => keyword.includes(term));
}

function canSelectForReply(status) {
  return ["pending", "reviewed", "failed"].includes(status);
}

function canRetry(status) {
  return ["reviewed", "failed"].includes(status);
}

function startScrape() {
  const keywords = getSelectedKeywords();
  if (!keywords.length) {
    alert("请至少勾选一个关键词或手动输入关键词");
    return;
  }
  const extra = document.getElementById("kwExtra").value.split("\\n").map(item => item.trim()).filter(Boolean);
  const invalid = extra.filter(keyword => !isBeautyKeyword(keyword));
  if (invalid.length) {
    alert(`关键词不在美业领域范围内，已拦截：\\n\\n${invalid.join("、")}\\n\\n请修改后重试。`);
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
  fetch("/api/leads").then(r => r.json()).then(data => {
    document.getElementById("total").textContent = data.length;
    document.getElementById("pending").textContent = data.filter(d => d.status === "pending").length;
    document.getElementById("reviewed").textContent = data.filter(d => d.status === "reviewed").length;
    document.getElementById("replied").textContent = data.filter(d => d.status === "replied").length;
    document.getElementById("failed").textContent = data.filter(d => d.status === "failed").length;
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
      tr.appendChild(cell(label, cls));
      tr.appendChild(cell(row.reply_text));
      const action = document.createElement("td");
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
        action.appendChild(retry);
      }
      tr.appendChild(action);
      tbody.appendChild(tr);
    });
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

const stream = new EventSource("/stream");
stream.onmessage = event => {
  const msg = JSON.parse(event.data);
  if (msg.log) document.getElementById("log").textContent = msg.log;
  if (msg.progress !== undefined) document.getElementById("progress").style.width = `${msg.progress}%`;
  if (msg.refresh) refreshTable();
};

buildKwGrid();
handleAutoMatchToggle(true);
refreshTable();
setInterval(refreshTable, 10000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    db.init_db()
    return render_template_string(
        HTML,
        keywords=KEYWORDS,
        templates=template_store.load_templates(),
        beauty_terms=BEAUTY_TERMS,
        default_max_per_keyword=DEFAULT_MAX_PER_KEYWORD,
        default_max_total=DEFAULT_MAX_TOTAL,
        real_send_enabled=ENABLE_REAL_REPLIES,
        real_send_notice="真实发送已开启" if ENABLE_REAL_REPLIES else "真实发送未开启，默认只做预演",
    )


@app.route("/api/leads")
def api_leads():
    db.init_db()
    return jsonify(db.get_all_leads())


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
                    "log": f"采集完成，共找到 {count} 位华东用户",
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
    db.init_db()
    webbrowser.open("http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()

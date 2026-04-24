# 微博美业精准拓客面板（WB Scraper）

面向美业展会（CIBE 美博会）场景的微博评论精准触达工具。通过关键词定位意向用户、过滤垃圾/AI 内容、按关键词智能匹配展会话术、批量真实发送评论，并支持真实撤回。

> 适用场景：展会招商、培训招生、供应链/加盟、门票发放等需要定点触达精准用户的美业拓客场景。

---

## 核心能力

| 能力 | 说明 |
|---|---|
| 精准采集 | 按自定义关键词搜索微博热门帖，抓取评论；结合意向词打分，只入库高意向 B2B / 消费者评论 |
| 内容过滤 | 内置 **无关词 / 推广垃圾词 / AI 口吻模式** 三层过滤，避免给带货号、抽奖号、AI 机器人回评 |
| 智能话术 | 14 档关键词模板（加盟 / 培训 / 穿戴甲 / 采购 / 美睫 …） + 本地 LLM（Ollama qwen2.5）按评论生成针对性话术 |
| 真实发送 | 走 `m.weibo.cn/api/comments/reply` 官方移动端接口，每 N 条自动轮换 cookie，防账号封控 |
| 真实撤回 | 每条发送自动记录 `sent_comment_id`；撤回按钮调 `m.weibo.cn/comments/destroy`，从微博侧真实删除已发评论 |
| 同帖止损 | 对方关闭评论权限 → 同一 post_id 下其他待发评论自动跳过，节省 Scrapfly 积分和 cookie 额度 |
| 批量控制 | 批量发送 / 批量重试 / 批量删除 / 暂停&继续 / 单条撤回 / 勾选状态保留 |
| 数据落盘 | 所有采集 + 发送记录写入 `weibo.db`（SQLite）；前端可导出 UTF-8 BOM CSV，Excel 直开不乱码 |
| 关键词持久化 | 手动追加的采集关键词写入 `active_keywords.json`，跨会话保留 |

---

## 系统架构

```
浏览器 ──HTTP──►  Flask 面板 (weibo_bot.dashboard)
                       │
                       ├─► scraper.py  ──► Scrapfly (residential + ASP)  ──►  m.weibo.cn
                       │
                       ├─► replier.py  ──► requests (m.weibo.cn 官方接口，带 cookie)
                       │                      │
                       │                      ├─ POST /api/comments/reply  (发送)
                       │                      └─ POST /comments/destroy    (撤回)
                       │
                       ├─► local_llm.py ──► Ollama (本地 qwen2.5:3b)
                       │
                       └─► db.py  ──► weibo.db (SQLite 单文件)
```

- **采集**过 Scrapfly 代理（`asp + residential + country=cn,hk`），单请求 ≈ 25–30 积分
- **发送/撤回**不走 Scrapfly，用本地 `requests` 直连微博官方 API + 你的 cookie，不消耗采集积分
- **LLM 推理**完全本地，不外联；关键词兜底不依赖 LLM 也能工作

---

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/yuq7-Yang/WB_Scraper.git
cd WB_Scraper
python -m venv .venv
# Windows: .venv\Scripts\activate     Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 `.env`

```bash
cp .env.example .env
```

打开 `.env` 填写：

```ini
SCRAPFLY_KEY="你的 Scrapfly API Key"

# 微博 cookie，多账号用 || 分隔（建议至少 2 个账号轮换）
WEIBO_COOKIES="SUB=_2A25xxxx; ...;||SUB=_2A26yyyy; ...;"

# 真实发送开关：true 才会真发出去，false 只记录预演
ENABLE_REAL_REPLIES="true"

# 每 N 条评论换一个账号发送（默认 3）
REPLIES_PER_ACCOUNT=3

# 条间延迟秒数
REPLY_DELAY=3

# 本地 LLM（可选）：关闭则走 KEYWORD_REPLY_MAP 关键词匹配话术
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434
LOCAL_LLM_MODEL=qwen2.5:3b
LOCAL_LLM_TICKET_CTA="感兴趣可以找我免费领取门票链接。"
```

**如何获取微博 Cookie：**
Edge / Chrome 登录 https://m.weibo.cn → F12 → Application → Cookies → 复制 `SUB`、`SUBP`、`XSRF-TOKEN` 等所有项的完整串。

### 3. 本地 LLM（可选但推荐）

```bash
# https://ollama.com/download
ollama pull qwen2.5:3b
ollama serve   # 默认监听 127.0.0.1:11434
```

不装 Ollama 也能用——面板会退回 `config.py` 里的 `KEYWORD_REPLY_MAP` 关键词模板。

### 4. 启动

```bash
python -m weibo_bot.dashboard
```

浏览器自动打开 http://127.0.0.1:5000

---

## 面板使用流程

1. **选择关键词** —— 上方蓝色 chip 是 `config.py` 的建议关键词，点击加入"已选"；也可在文本框手动追加（须包含美业白名单词），点 **添加关键词** 入列；勾选后点击 **开始采集**。手动加的会存盘，下次还在。
2. **等待采集** —— 进度条实时更新。命中评论即时写入 SQLite，失败会提示原因。
3. **筛选目标用户** —— 表格里查看用户名、属地、评论内容、关键词、帖子链接；不合适的行可单删或批量删。
4. **批量发送**
   - 勾选若干行 → 点 **发送评论** → 弹窗默认开启"根据关键词自动匹配话术"（推荐），或改手动选话术。
   - 若 `.env` 开启了真实发送，还要再勾 **我确认真实发送评论**。
   - 发送中可 **暂停/继续**，或 **批量重试** 把失败/跳过的重置回 pending 再发。
5. **撤回** —— `已回复` 行会出现 **撤回** 按钮。点击后真实从微博删除已发评论，并把 lead 重置为 pending 可再次发送。
   - ⚠️ 撤回仅对**撤回功能上线后**发送的评论有效（需要 `sent_comment_id`，旧记录没有该字段时按钮灰掉）。

---

## 数据库

### 文件位置

`weibo.db`（项目根目录，SQLite 单文件），可通过 `WEIBO_DB_PATH` 环境变量改位置。

### 表结构（`leads`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INT PK | 自增 |
| `user_name`, `location`, `comment_text`, `comment_id`, `post_id` | TEXT | 评论原始信息 |
| `keyword` | TEXT | 命中的采集关键词 |
| `lead_type` | TEXT | `b2b` / `consumer` |
| `intent_score` | INT | 意向分（≥3 才入库，可在 .env 调） |
| `scraped_at` | TS | 采集时间（UTC） |
| `status` | TEXT | `pending` / `reviewed` / `replied` / `failed` / `skipped` |
| `reply_text` | TEXT | 发送或跳过时的话术/原因 |
| `replied_at` | TS | 发送/跳过时间 |
| `sent_comment_id` | TEXT | 真实发送后微博返回的新评论 ID（撤回凭据） |
| `cookie_index` | INT | 发送时使用的账号下标（撤回要用同一账号） |

### GUI 查看

- [DB Browser for SQLite](https://sqlitebrowser.org/) 免费跨平台
- VS Code 插件 **SQLite Viewer**
- 或命令行 `sqlite3 weibo.db "select * from leads limit 10"`

### 导出

面板顶部 **导出 CSV** 按钮，UTF-8 BOM 编码，Excel 直接打开。

---

## Scrapfly 积分消耗

采集的每次 API 调用（关键词搜索 / 评论翻页）**≈ 25-30 积分**：

```
1 (基础) + 5 (ASP) + 25 (residential proxy cn/hk) ≈ 30
```

每条入库评论摊销约 **40-120 积分**（取决于过滤通过率），以 Scrapfly Dashboard 真实计费为准。

**省积分的 3 种方法**（需自己改 `scraper.py` `SCRAPE_CONFIG`）：

1. 关闭 residential proxy（但会被风控）
2. 关闭 ASP（m.weibo.cn 一般不需要）
3. `fetch_comments(max_pages=1)` 只抓首屏

---

## 过滤策略（防乱发）

### 采集侧（`scraper.py`）

- **无关词**：奶茶/袜子/拖鞋/衣服/投诉等非美业上下文直接丢弃
- **垃圾推广词**：扫码/加V/戳我头像/转发抽奖/互粉等带货特征
- **AI 口吻**：`作为一名` `综上所述` `首先，其次，再者` `我们致力于` 等 22 条 AI 式开头
- **意向打分**：B2B（加盟/进货/供应链…） 和 消费者（推荐/链接/同款…）两个维度，达阈值才入库

### 发送侧（`local_llm.is_relevant_for_expo_reply`）

发送前再过一次 "展会场景相关性" 检查，比如"年度皮肤用物链接"这种非美甲美睫内容会被再次跳过（记为 `skipped`）。

---

## 真实发送的安全机制

默认 `.env` 里 `ENABLE_REAL_REPLIES="false"`，所有"发送"只会写 `status=reviewed` 做预演。真实发送必须同时满足：

1. `.env` 设置 `ENABLE_REAL_REPLIES="true"`
2. 面板话术弹窗勾选 **我确认真实发送评论**

缺任一条件都按预演处理。

---

## 部署到服务器（内网/团队）

### Linux + gunicorn + Nginx basic auth

1. `pip install gunicorn`
2. systemd 服务：
   ```ini
   # /etc/systemd/system/wbscraper.service
   [Service]
   User=wb
   WorkingDirectory=/home/wb/WB_Scraper
   Environment="PATH=/home/wb/WB_Scraper/.venv/bin"
   ExecStart=/home/wb/WB_Scraper/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 --timeout 300 "weibo_bot.dashboard:app"
   Restart=on-failure
   ```
   > `-w 2` 不要调高：SQLite 只有 1 个 writer，worker 多会锁表。
3. Nginx 反代 + `htpasswd` basic auth + certbot HTTPS
4. `cron` 每天凌晨备份 `weibo.db`
5. 团队多人共用一个 SQLite + 一组 cookie，SQLite 适合 ≤ 5 人低并发场景

详细步骤见 [部署流程说明](微博抓取发送流程说明.md)。对外开放给陌生人需改造为多租户 + PostgreSQL。

---

## 目录结构

```
WB_Scraper/
├── weibo_bot/
│   ├── dashboard.py      # Flask 面板 + SSE 进度 + REST API
│   ├── scraper.py        # Scrapfly 采集 + 意向打分 + 过滤
│   ├── replier.py        # 发送/撤回，cookie 轮换，批量控制
│   ├── local_llm.py      # Ollama 话术生成 + 展会相关性过滤
│   ├── db.py             # SQLite schema + CRUD
│   ├── config.py         # 关键词库、打分阈值、过滤词、模板
│   ├── keyword_store.py  # active_keywords.json 持久化
│   ├── template_store.py # reply_templates.json 持久化
│   └── static/           # logo 等静态资源
├── tests/                # pytest 单元测试
├── scripts/
│   └── setup_credentials.py  # 命令行录入 cookie 工具
├── docs/                 # 设计文档 / plan 记录
├── requirements.txt
├── .env.example          # 配置模板
├── weibo.db              # SQLite 数据库（gitignore）
├── reply_templates.json  # 自定义话术（gitignore）
├── active_keywords.json  # 已选采集关键词（gitignore）
└── README.md
```

---

## FAQ

**Q: 发送失败提示"由于对方的设置，你不能评论哦！"**
A: 对方微博博主关闭了陌生人评论权限（隐私设置），服务端强制拦截，代码无解。系统会自动把同一 post_id 下其他待发评论标记为 `skipped`，避免重复撞墙浪费 cookie。

**Q: 撤回按钮灰置**
A: 该条记录缺 `sent_comment_id`，说明是 2026-04-23 撤回功能上线前发的。只能通过"删除"把本地 lead 移除，微博侧那条评论需要你手动去微博客户端删。

**Q: Cookie 过期了怎么办**
A: 发送时会返回 `20003 账号未登录` 等错误。重新登录微博获取新 cookie，替换 `.env` 的 `WEIBO_COOKIES`，重启面板。

**Q: Scrapfly 积分扣得太快**
A: 检查是否重复采集同一关键词。`MAX_COMMENTS_PER_KEYWORD` 默认 2，`DEFAULT_MAX_TOTAL` 默认 20，首次跑完验证通过后再调大。

**Q: 多账号发送没轮换**
A: `REPLIES_PER_ACCOUNT` 按**批次内位置**计数（含 skipped）。前半批全是 skipped 会导致"看起来"没轮换到第二个 cookie。

---

## 合规提醒

- 本项目仅用于自有微博账号的合法展会营销触达。
- 使用前应确保遵守微博《用户服务使用协议》，不做大规模骚扰、不虚假宣传、不诱导点击。
- 真实发送功能默认关闭，开启前请自行承担账号风险。
- 严禁用于违法、欺诈、不正当竞争等场景。

---

## 许可

内部工具，暂无公开 License。请勿未经授权商用。

# 微博美业拓客面板

这是根据 `微博美甲美睫数据采集计划书.md` 搭建的第一版本地工具。当前版本默认采用安全模式：采集可以在配置 Scrapfly 和 Cookie 后运行，回复按钮只做 dry-run 预演，不会真实发送微博回复。

## 安装

```powershell
python -m pip install -r requirements.txt
```

## 配置

PowerShell 示例：

```powershell
$env:SCRAPFLY_KEY="你的 Scrapfly API Key"
$env:WEIBO_COOKIES="SUB=_2A25...第一个账号...;"
$env:DRY_RUN_REPLIES="true"
```

`WEIBO_COOKIES` 可以用 `||` 分隔多个 Cookie。1 个 Cookie 可以小范围测试，长期使用建议至少 2 个账号轮换。不要把真实 Cookie 写入仓库文件。

也可以运行本地录入脚本：

```powershell
python scripts/setup_credentials.py
```

## 启动

```powershell
python -m weibo_bot.dashboard
```

浏览器会打开 `http://127.0.0.1:5000`。

## 当前状态

- `开始采集`：需要 `SCRAPFLY_KEY` 和 `WEIBO_COOKIES`。
- `发送评论`：先勾选线索，再选择话术。默认只写入数据库，状态变为 `已预演`。
- `保存话术`：在话术弹窗里输入新话术并保存，下次重启仍可使用。
- `重试`：把失败记录重置为 `待处理`。
- `导出 CSV`：把 `weibo.db` 里的线索下载为 `weibo_leads.csv`。

默认测试采集模式：

```powershell
$env:DEFAULT_MAX_PER_KEYWORD="2"
$env:DEFAULT_MAX_TOTAL="20"
```

首次运行建议每个关键词最多 2 条、总上限 20 条。确认流程正常后，可以在面板里调大到每词 50 条、总上限 500 条。

## 真实发送开关

默认不会真实发送微博评论。要开启真实发送，需要同时满足两步：

1. `.env` 中设置：

```powershell
ENABLE_REAL_REPLIES="true"
```

2. 在面板话术弹窗里勾选“我确认真实发送评论”。

缺少任意一步都会按预演处理，只记录话术，不发微博。

## 自定义话术

新增话术会保存在本机：

```text
reply_templates.json
```

这个文件已加入 `.gitignore`，不会进入代码仓库。删除它后，面板会回到 `config.py` 里的默认话术。

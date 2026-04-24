# 阿里云 Ubuntu 8888 部署说明

这个项目的真实运行方式是：

- 入口：`weibo_bot.dashboard:app`
- Web 服务：Flask 面板
- 数据存储：SQLite + 本地 JSON 文件
- 配置来源：项目根目录 `.env`
- 对外访问端口：`8888`

这份说明按当前项目逻辑部署，不额外引入 Docker 或 Nginx。

## 1. 服务器准备

确保阿里云安全组已经放行 TCP `8888`。

推荐使用 Ubuntu 22.04 或更高版本。

## 2. 首次安装

登录服务器后执行：

```bash
sudo -i
cd /tmp
git clone https://github.com/yuq7-Yang/WB_Scraper.git
cd WB_Scraper
bash deploy/aliyun/install_ubuntu.sh
```

脚本会完成这些事情：

- 安装 `git`、`python3`、`python3-venv`
- 创建部署目录 `/opt/wb_scraper`
- 拉取 GitHub 仓库
- 创建运行目录 `data/`、`logs/`
- 创建 Python 虚拟环境
- 安装 `requirements.txt`
- 安装 `systemd` 服务文件

## 3. 编辑服务器环境变量

首次安装后，编辑：

```bash
nano /opt/wb_scraper/.env
```

至少要填这些值：

- `SCRAPFLY_KEY`
- `WEIBO_COOKIES`
- `DASHBOARD_SECRET_KEY`

建议保留这些部署值：

```ini
DASHBOARD_HOST="0.0.0.0"
DASHBOARD_PORT="8888"
DASHBOARD_OPEN_BROWSER="false"
WEIBO_DB_PATH="data/weibo.db"
ACTIVE_KEYWORDS_PATH="data/active_keywords.json"
REPLY_TEMPLATES_PATH="data/reply_templates.json"
```

## 4. 启动服务

```bash
sudo systemctl enable --now wbscraper
sudo systemctl status wbscraper
```

查看日志：

```bash
sudo journalctl -u wbscraper -f
```

## 5. 访问方式

直接用阿里云服务器公网 IP 访问：

```text
http://你的服务器公网IP:8888
```

现在项目已经带登录页，所以会先进入登录，再跳转到主面板。

## 6. 更新部署

以后本地代码推到 GitHub 后，服务器执行：

```bash
sudo bash /opt/wb_scraper/deploy/aliyun/update_ubuntu.sh
```

这个脚本会：

- 拉取 GitHub 最新代码
- 更新 Python 依赖
- 刷新 `systemd` 服务文件
- 重启服务

## 7. 数据文件说明

这些文件不会上传到 GitHub，而是保留在服务器本机：

- `data/weibo.db`
- `data/active_keywords.json`
- `data/reply_templates.json`
- `.env`

这样更新代码时，不会把你的业务数据和账号配置覆盖掉。

## 8. 常用命令

重启服务：

```bash
sudo systemctl restart wbscraper
```

停止服务：

```bash
sudo systemctl stop wbscraper
```

查看端口监听：

```bash
sudo ss -ltnp | grep 8888
```

## 9. 排错

如果浏览器打不开：

1. 先看服务状态：

```bash
sudo systemctl status wbscraper
```

2. 再看日志：

```bash
sudo journalctl -u wbscraper -n 200 --no-pager
```

3. 再检查安全组是否开放 `8888`

4. 再确认 `.env` 是否已填写 `SCRAPFLY_KEY`、`WEIBO_COOKIES`、`DASHBOARD_SECRET_KEY`

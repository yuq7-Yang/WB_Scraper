from weibo_bot import dashboard, db


class ImmediateThread:
    def __init__(self, target, daemon=False):
        self.target = target

    def start(self):
        self.target()


def build_logged_in_client():
    client = dashboard.app.test_client()
    client.post("/login", data={"username": "CIBE", "password": "cibe8888"})
    return client


def test_dashboard_requires_login_for_home_and_api():
    client = dashboard.app.test_client()

    home_response = client.get("/")
    api_response = client.get("/api/leads")

    assert home_response.status_code == 302
    assert "/login" in home_response.headers["Location"]
    assert api_response.status_code == 401
    assert api_response.get_json()["error"] == "auth_required"


def test_login_accepts_fixed_credentials_and_sets_remember_cookie():
    client = dashboard.app.test_client()

    response = client.post(
        "/login",
        data={"username": "CIBE", "password": "cibe8888"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    set_cookie = response.headers.get("Set-Cookie", "")
    assert "remember_login=" in set_cookie


def test_login_allows_access_after_success():
    client = dashboard.app.test_client()
    client.post("/login", data={"username": "CIBE", "password": "cibe8888"})

    response = client.get("/api/leads")

    assert response.status_code == 200


def test_remember_cookie_allows_access_without_session():
    client = dashboard.app.test_client()
    login_response = client.post(
        "/login",
        data={"username": "CIBE", "password": "cibe8888"},
        follow_redirects=False,
    )
    remember_cookie = login_response.headers.get("Set-Cookie", "").split(";", 1)[0]
    cookie_name, cookie_value = remember_cookie.split("=", 1)

    with client.session_transaction() as sess:
        sess.clear()
    client.set_cookie(cookie_name, cookie_value)

    response = client.get("/api/leads")

    assert response.status_code == 200


def test_login_rejects_invalid_credentials():
    client = dashboard.app.test_client()

    response = client.post(
        "/login",
        data={"username": "wrong", "password": "bad"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "登录信息不正确" in response.get_data(as_text=True)


def test_main_uses_runtime_env_settings(monkeypatch):
    calls = {}

    monkeypatch.setenv("DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("DASHBOARD_PORT", "8888")
    monkeypatch.setenv("DASHBOARD_OPEN_BROWSER", "false")
    monkeypatch.setattr(dashboard.db, "init_db", lambda: calls.setdefault("init_db", 0) or calls.__setitem__("init_db", 1))
    monkeypatch.setattr(dashboard.webbrowser, "open", lambda url: calls.setdefault("browser", []).append(url))

    def fake_run(**kwargs):
        calls["run"] = kwargs

    monkeypatch.setattr(dashboard.app, "run", fake_run)

    dashboard.main()

    assert calls["init_db"] == 1
    assert calls["run"]["host"] == "0.0.0.0"
    assert calls["run"]["port"] == 8888
    assert calls["run"]["debug"] is False
    assert calls["run"]["threaded"] is True
    assert calls.get("browser") in (None, [])


def test_api_leads_returns_inserted_rows(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "\u4e0a\u6d77", "\u6c42\u63a8\u8350", "1001", "\u7f8e\u7532\u5e97")
    client = build_logged_in_client()

    response = client.get("/api/leads")

    assert response.status_code == 200
    assert response.get_json()[0]["user_name"] == "alice"


def test_api_leads_sanitizes_comment_text_for_display(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead(
        "alice",
        "\u4e0a\u6d77",
        '\u60f3\u505a\u8fd9\u4e24\u4e2a <a href="https://example.com"><span class="surl-text">\u67e5\u770b\u56fe\u7247</span></a>',
        "1001",
        "\u7f8e\u7532\u6b3e\u5f0f",
    )
    client = build_logged_in_client()

    response = client.get("/api/leads")

    assert response.status_code == 200
    assert "<a href=" not in response.get_json()[0]["comment_text"]
    assert "<span" not in response.get_json()[0]["comment_text"]


def test_api_leads_includes_lead_type_and_intent_score(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead(
        "alice",
        "上海",
        "封层有没有推荐呀",
        "1001",
        "甲油胶推荐",
        comment_id="2001",
        lead_type="consumer",
        intent_score=4,
    )
    client = build_logged_in_client()

    response = client.get("/api/leads")

    payload = response.get_json()[0]
    assert payload["lead_type"] == "consumer"
    assert payload["intent_score"] == 4


def test_retry_resets_failed_row_to_pending(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "\u4e0a\u6d77", "\u6c42\u63a8\u8350", "1001", "\u7f8e\u7532\u5e97")
    lead = db.get_pending_leads(1)[0]
    db.update_lead_status(lead["id"], "failed", "network")
    client = build_logged_in_client()

    response = client.post(f"/api/retry/{lead['id']}")

    assert response.status_code == 200
    assert db.get_all_leads()[0]["status"] == "pending"


def test_retry_resets_reviewed_row_to_pending_and_clears_reply(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "\u4e0a\u6d77", "\u6c42\u63a8\u8350", "1001", "\u7f8e\u7532\u5e97")
    lead = db.get_pending_leads(1)[0]
    db.update_lead_status(lead["id"], "reviewed", "\u9884\u6f14\u8bdd\u672f")
    client = build_logged_in_client()

    response = client.post(f"/api/retry/{lead['id']}")

    row = db.get_all_leads()[0]
    assert response.status_code == 200
    assert row["status"] == "pending"
    assert row["reply_text"] is None
    assert row["replied_at"] is None


def test_export_csv_returns_database_rows(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "\u676d\u5dde", "=\u654f\u611f\u5f00\u5934", "1001", "\u7f8e\u7532", comment_id="2001")
    client = build_logged_in_client()

    response = client.get("/api/export.csv")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment; filename=weibo_leads.csv" in response.headers["Content-Disposition"]
    csv_text = response.get_data(as_text=True)
    assert "user_name,location,comment_text,comment_id,post_id,keyword,lead_type,intent_score,scraped_at,status,reply_text,replied_at" in csv_text
    assert "2001" in csv_text
    assert "alice" in csv_text
    assert "'=\u654f\u611f\u5f00\u5934" in csv_text


def test_dashboard_includes_post_link_column():
    client = build_logged_in_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "https://m.weibo.cn/detail/" in html
    assert "查看帖子" in html
    assert "用户名称" not in html


def test_dashboard_allows_retrying_reviewed_and_failed_rows():
    client = build_logged_in_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "function canSelectForReply(status)" in html
    assert '["pending", "reviewed", "failed", "skipped"].includes(status)' in html
    assert "function canRetry(status)" in html
    assert '["reviewed", "failed", "skipped"].includes(status)' in html


class TestApiReplyAutoMatch:
    def test_auto_match_true_is_passed_to_run_reply(self, monkeypatch):
        captured = {}

        def fake_run_reply(**kwargs):
            captured.update(kwargs)
            return 1

        monkeypatch.setattr(dashboard.threading, "Thread", ImmediateThread)
        monkeypatch.setattr(dashboard, "run_reply", fake_run_reply)
        client = build_logged_in_client()

        response = client.post(
            "/api/reply",
            json={
                "lead_ids": [1],
                "reply_text": "",
                "auto_match": True,
            },
        )

        assert response.status_code == 200
        assert captured.get("auto_match") is True

    def test_auto_match_defaults_false(self, monkeypatch):
        captured = {}

        def fake_run_reply(**kwargs):
            captured.update(kwargs)
            return 1

        monkeypatch.setattr(dashboard.threading, "Thread", ImmediateThread)
        monkeypatch.setattr(dashboard, "run_reply", fake_run_reply)
        client = build_logged_in_client()

        response = client.post(
            "/api/reply",
            json={
                "lead_ids": [1],
                "reply_text": "\u624b\u52a8\u8bdd\u672f",
            },
        )

        assert response.status_code == 200
        assert captured.get("auto_match") is False

from weibo_bot import dashboard, db


class ImmediateThread:
    def __init__(self, target, daemon=False):
        self.target = target

    def start(self):
        self.target()


def test_api_leads_returns_inserted_rows(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "\u4e0a\u6d77", "\u6c42\u63a8\u8350", "1001", "\u7f8e\u7532\u5e97")
    client = dashboard.app.test_client()

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
    client = dashboard.app.test_client()

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
    client = dashboard.app.test_client()

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
    client = dashboard.app.test_client()

    response = client.post(f"/api/retry/{lead['id']}")

    assert response.status_code == 200
    assert db.get_all_leads()[0]["status"] == "pending"


def test_retry_resets_reviewed_row_to_pending_and_clears_reply(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "\u4e0a\u6d77", "\u6c42\u63a8\u8350", "1001", "\u7f8e\u7532\u5e97")
    lead = db.get_pending_leads(1)[0]
    db.update_lead_status(lead["id"], "reviewed", "\u9884\u6f14\u8bdd\u672f")
    client = dashboard.app.test_client()

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
    client = dashboard.app.test_client()

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
    client = dashboard.app.test_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "https://m.weibo.cn/detail/" in html
    assert "lead_type" in html
    assert "intent_score" in html


def test_dashboard_allows_retrying_reviewed_and_failed_rows():
    client = dashboard.app.test_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "function canSelectForReply(status)" in html
    assert '["pending", "reviewed", "failed"].includes(status)' in html
    assert "function canRetry(status)" in html
    assert '["reviewed", "failed"].includes(status)' in html


class TestApiReplyAutoMatch:
    def test_auto_match_true_is_passed_to_run_reply(self, monkeypatch):
        captured = {}

        def fake_run_reply(**kwargs):
            captured.update(kwargs)
            return 1

        monkeypatch.setattr(dashboard.threading, "Thread", ImmediateThread)
        monkeypatch.setattr(dashboard, "run_reply", fake_run_reply)
        client = dashboard.app.test_client()

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
        client = dashboard.app.test_client()

        response = client.post(
            "/api/reply",
            json={
                "lead_ids": [1],
                "reply_text": "\u624b\u52a8\u8bdd\u672f",
            },
        )

        assert response.status_code == 200
        assert captured.get("auto_match") is False

from weibo_bot import dashboard, db


class ImmediateThread:
    def __init__(self, target, daemon=False):
        self.target = target

    def start(self):
        self.target()


def test_api_leads_returns_inserted_rows(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "求推荐", "1001", "美甲店")
    client = dashboard.app.test_client()

    response = client.get("/api/leads")

    assert response.status_code == 200
    assert response.get_json()[0]["user_name"] == "alice"


def test_retry_resets_failed_row_to_pending(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "求推荐", "1001", "美甲店")
    lead = db.get_pending_leads(1)[0]
    db.update_lead_status(lead["id"], "failed", "network")
    client = dashboard.app.test_client()

    response = client.post(f"/api/retry/{lead['id']}")

    assert response.status_code == 200
    assert db.get_all_leads()[0]["status"] == "pending"


def test_retry_resets_reviewed_row_to_pending_and_clears_reply(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "求推荐", "1001", "美甲店")
    lead = db.get_pending_leads(1)[0]
    db.update_lead_status(lead["id"], "reviewed", "预演话术")
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
    db.insert_lead("alice", "??", "=????", "1001", "???", comment_id="2001")
    client = dashboard.app.test_client()

    response = client.get("/api/export.csv")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment; filename=weibo_leads.csv" in response.headers["Content-Disposition"]
    csv_text = response.get_data(as_text=True)
    assert "user_name,location,comment_text,comment_id,post_id,keyword,scraped_at,status,reply_text,replied_at" in csv_text
    assert "2001" in csv_text
    assert "alice" in csv_text
    assert "'=????" in csv_text


def test_dashboard_includes_post_link_column():
    client = dashboard.app.test_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "帖子链接" in html
    assert "https://m.weibo.cn/detail/" in html
    assert "查看帖子" in html


def test_dashboard_allows_retrying_reviewed_and_failed_rows():
    client = dashboard.app.test_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "function canSelectForReply(status)" in html
    assert '["pending", "reviewed", "failed"].includes(status)' in html
    assert "function canRetry(status)" in html
    assert '["reviewed", "failed"].includes(status)' in html
    assert "全选可发送" in html


# -- /api/reply auto_match 透传 ---------------------------------------------
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
                "reply_text": "手动话术",
            },
        )

        assert response.status_code == 200
        assert captured.get("auto_match") is False

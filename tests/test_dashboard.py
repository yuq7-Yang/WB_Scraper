from weibo_bot import dashboard, db


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

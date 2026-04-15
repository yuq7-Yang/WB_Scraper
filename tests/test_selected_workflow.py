from weibo_bot import dashboard, db, replier, scraper
from weibo_bot.config import parse_env_file


class ImmediateThread:
    def __init__(self, target, daemon=False):
        self.target = target

    def start(self):
        self.target()


def test_parse_env_file_can_hold_real_reply_flag(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('ENABLE_REAL_REPLIES="true"\n', encoding="utf-8")

    values = parse_env_file(str(env_file))

    assert values["ENABLE_REAL_REPLIES"] == "true"


def test_run_scrape_limits_total_across_keywords(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "key")
    monkeypatch.setattr(scraper, "COOKIES", ["cookie"])
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper, "search_posts", lambda *args, **kwargs: ["1001"])
    monkeypatch.setattr(
        scraper,
        "fetch_comments",
        lambda *args, **kwargs: [
            {"source": "来自上海", "user": {"screen_name": "one"}, "text": "a"},
            {"source": "来自浙江", "user": {"screen_name": "two"}, "text": "b"},
            {"source": "来自江苏", "user": {"screen_name": "three"}, "text": "c"},
        ],
    )

    count = scraper.run_scrape(keywords=["kw1", "kw2"], max_per_keyword=10, max_total=3)

    assert count == 3
    assert len(db.get_all_leads()) == 3


def test_run_reply_selected_ids_records_selected_template_only(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "a", "1001", "kw")
    db.insert_lead("bob", "浙江", "b", "1002", "kw")
    selected_id = next(row["id"] for row in db.get_all_leads() if row["user_name"] == "alice")

    count = replier.run_reply(
        lead_ids=[selected_id],
        reply_text="chosen template",
        confirm_real_send=False,
    )

    rows = {row["user_name"]: row for row in db.get_all_leads()}
    assert count == 1
    assert rows["alice"]["status"] == "reviewed"
    assert rows["alice"]["reply_text"] == "chosen template"
    assert rows["bob"]["status"] == "pending"


def test_run_reply_does_not_real_send_without_env_and_confirmation(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "a", "1001", "kw")
    lead_id = db.get_all_leads()[0]["id"]
    monkeypatch.setattr(replier, "ENABLE_REAL_REPLIES", False, raising=False)
    monkeypatch.setattr(
        replier,
        "_send_real_reply",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("real send called")),
        raising=False,
    )

    count = replier.run_reply(
        lead_ids=[lead_id],
        reply_text="dry only",
        confirm_real_send=True,
    )

    lead = db.get_all_leads()[0]
    assert count == 1
    assert lead["status"] == "reviewed"
    assert lead["reply_text"] == "dry only"


def test_run_reply_real_send_requires_env_and_request_confirmation(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "a", "1001", "kw")
    lead_id = db.get_all_leads()[0]["id"]
    calls = []
    monkeypatch.setattr(replier, "ENABLE_REAL_REPLIES", True, raising=False)
    monkeypatch.setattr(
        replier,
        "_send_real_reply",
        lambda lead, reply_text, cookie_index=0: calls.append((lead["id"], reply_text)) or (True, reply_text),
        raising=False,
    )

    count = replier.run_reply(
        lead_ids=[lead_id],
        reply_text="real text",
        confirm_real_send=True,
    )

    lead = db.get_all_leads()[0]
    assert count == 1
    assert calls == [(lead_id, "real text")]
    assert lead["status"] == "replied"
    assert lead["reply_text"] == "real text"


def test_make_scenario_returns_scrapfly_list():
    scenario = replier._make_scenario("hello")

    assert isinstance(scenario, list)
    assert scenario[0]["scroll"]["element"] == "body"
    assert scenario[4]["fill"]["value"] == "hello"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.text = str(payload)

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, config_payload, post_payload):
        self.config_payload = config_payload
        self.post_payload = post_payload
        self.headers = {}
        self.post_calls = []

    def get(self, url, timeout=30):
        return FakeResponse(self.config_payload)

    def post(self, url, data=None, timeout=30):
        self.post_calls.append((url, data))
        return FakeResponse(self.post_payload)


def test_send_real_reply_uses_weibo_api_success(monkeypatch):
    session = FakeSession(
        {"data": {"login": True, "st": "token"}},
        {"ok": 1, "data": {"id": "comment-id"}},
    )
    monkeypatch.setattr(replier.requests, "Session", lambda: session)
    monkeypatch.setattr(replier, "COOKIES", ["cookie"], raising=False)

    ok, info = replier._send_real_reply({"post_id": "1001"}, "hello", cookie_index=0)

    assert ok is True
    assert info == "hello"
    assert session.post_calls == [
        ("https://m.weibo.cn/api/comments/create", {"content": "hello", "mid": "1001", "st": "token"})
    ]


def test_send_real_reply_uses_comment_reply_api_when_comment_id_exists(monkeypatch):
    session = FakeSession(
        {"data": {"login": True, "st": "token"}},
        {"ok": 1, "data": {"id": "reply-id"}},
    )
    monkeypatch.setattr(replier.requests, "Session", lambda: session)
    monkeypatch.setattr(replier, "COOKIES", ["cookie"], raising=False)

    ok, info = replier._send_real_reply(
        {"post_id": "1001", "comment_id": "2001"},
        "hello",
        cookie_index=0,
    )

    assert ok is True
    assert info == "hello"
    assert session.post_calls == [
        (
            "https://m.weibo.cn/api/comments/reply",
            {"content": "hello", "mid": "1001", "cid": "2001", "st": "token"},
        )
    ]


def test_send_real_reply_rejects_logged_out_cookie(monkeypatch):
    session = FakeSession({"data": {"login": False, "st": "token"}}, {"ok": 1})
    monkeypatch.setattr(replier.requests, "Session", lambda: session)
    monkeypatch.setattr(replier, "COOKIES", ["cookie"], raising=False)

    try:
        replier._send_real_reply({"post_id": "1001"}, "hello", cookie_index=0)
    except RuntimeError as exc:
        assert "not logged in" in str(exc)
    else:
        raise AssertionError("logged out cookie was accepted")


def test_api_scrape_accepts_selected_keywords_and_limits(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(dashboard, "run_scrape", lambda **kwargs: calls.append(kwargs) or 7)
    client = dashboard.app.test_client()

    response = client.post(
        "/api/scrape",
        json={"keywords": ["kw1", "kw2"], "max_per_keyword": 2, "max_total": 20},
    )

    assert response.status_code == 200
    assert calls[0]["keywords"] == ["kw1", "kw2"]
    assert calls[0]["max_per_keyword"] == 2
    assert calls[0]["max_total"] == 20


def test_api_reply_accepts_selected_leads_template_and_confirmation(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(dashboard, "run_reply", lambda **kwargs: calls.append(kwargs) or 2)
    client = dashboard.app.test_client()

    response = client.post(
        "/api/reply",
        json={"lead_ids": [1, 2], "reply_text": "selected text", "confirm_real_send": True},
    )

    assert response.status_code == 200
    assert calls[0]["lead_ids"] == [1, 2]
    assert calls[0]["reply_text"] == "selected text"
    assert calls[0]["confirm_real_send"] is True


def test_api_templates_returns_reply_templates():
    client = dashboard.app.test_client()

    response = client.get("/api/templates")

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)
    assert response.get_json()


def test_dashboard_includes_updated_controls_and_safety_copy():
    client = dashboard.app.test_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="kwGrid"' in html
    assert 'id="kwExtra"' in html
    assert 'id="maxPerKw"' in html
    assert 'id="maxTotal"' in html
    assert "全选待回复" in html
    assert "发送评论" in html
    assert 'id="modalMask"' in html
    assert 'id="confirmRealSend"' in html
    assert 'class="real-send-confirm"' in html
    assert ".real-send-confirm { align-items: center; display: flex;" in html
    assert "真实发送" in html

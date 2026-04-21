from weibo_bot import db
from weibo_bot import replier


def test_run_reply_dry_run_marks_pending_leads_reviewed(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "求款式", "1001", "美甲款式")
    monkeypatch.setattr(replier, "REPLY_TEMPLATES", ["欢迎了解"])

    count = replier.run_reply(limit=1, dry_run=True)

    lead = db.get_all_leads()[0]
    assert count == 1
    assert lead["status"] == "reviewed"
    assert lead["reply_text"] == "欢迎了解"


# -- auto_match + 账号轮换 ---------------------------------------------------
class TestAutoMatchAndRotation:
    def test_auto_match_uses_keyword_template(self, monkeypatch):
        fake_leads = [
            {
                "id": 1,
                "keyword": "美甲培训",
                "comment_id": "c1",
                "user_name": "u1",
                "status": "pending",
            },
            {
                "id": 2,
                "keyword": "进货",
                "comment_id": "c2",
                "user_name": "u2",
                "status": "pending",
            },
        ]
        monkeypatch.setattr(replier, "get_leads_by_ids", lambda ids: fake_leads)

        sent = []

        def fake_reply_to_lead(lead, reply_text, confirm_real_send=False, cookie_index=0):
            sent.append({"id": lead["id"], "text": reply_text})
            return True, reply_text

        monkeypatch.setattr(replier, "reply_to_lead", fake_reply_to_lead)
        monkeypatch.setattr(replier.time, "sleep", lambda seconds: None)

        count = replier.run_reply(
            lead_ids=[1, 2],
            reply_text="",
            confirm_real_send=False,
            auto_match=True,
        )

        assert count == 2
        assert "美甲板块" in sent[0]["text"]
        assert "供应商" in sent[1]["text"] or "品牌商" in sent[1]["text"]
        assert "私信我获取门票" in sent[0]["text"]
        assert "私信我获取门票" in sent[1]["text"]

    def test_manual_mode_uses_same_text(self, monkeypatch):
        fake_leads = [
            {
                "id": 1,
                "keyword": "美甲培训",
                "comment_id": "c1",
                "user_name": "u1",
                "status": "pending",
            },
            {
                "id": 2,
                "keyword": "进货",
                "comment_id": "c2",
                "user_name": "u2",
                "status": "pending",
            },
        ]
        monkeypatch.setattr(replier, "get_leads_by_ids", lambda ids: fake_leads)

        sent = []

        def fake_reply_to_lead(lead, reply_text, confirm_real_send=False, cookie_index=0):
            sent.append(reply_text)
            return True, reply_text

        monkeypatch.setattr(replier, "reply_to_lead", fake_reply_to_lead)
        monkeypatch.setattr(replier.time, "sleep", lambda seconds: None)

        count = replier.run_reply(
            lead_ids=[1, 2],
            reply_text="手动话术内容",
            confirm_real_send=False,
            auto_match=False,
        )

        assert count == 2
        assert sent == ["手动话术内容", "手动话术内容"]

    def test_get_cookie_for_index_cycles(self, monkeypatch):
        from weibo_bot import config

        monkeypatch.setattr(config, "WEIBO_COOKIES", "cookieA||cookieB||cookieC")

        assert replier._get_cookie_for_index(0) == 0
        assert replier._get_cookie_for_index(1) == 1
        assert replier._get_cookie_for_index(2) == 2
        assert replier._get_cookie_for_index(3) == 0
        assert replier._get_cookie_for_index(5) == 2

    def test_get_cookie_single_account(self, monkeypatch):
        from weibo_bot import config

        monkeypatch.setattr(config, "WEIBO_COOKIES", "onlyCookie")

        assert replier._get_cookie_for_index(0) == 0
        assert replier._get_cookie_for_index(9) == 0

    def test_account_rotates_every_3(self, monkeypatch):
        from weibo_bot import config

        monkeypatch.setattr(config, "WEIBO_COOKIES", "cookieA||cookieB")
        fake_leads = [
            {
                "id": index,
                "keyword": "美甲",
                "comment_id": f"c{index}",
                "user_name": f"u{index}",
                "status": "pending",
            }
            for index in range(1, 7)
        ]
        monkeypatch.setattr(replier, "get_leads_by_ids", lambda ids: fake_leads)

        used_cookie_indexes = []

        def fake_reply_to_lead(lead, reply_text, confirm_real_send=False, cookie_index=0):
            used_cookie_indexes.append(cookie_index)
            return True, reply_text

        monkeypatch.setattr(replier, "reply_to_lead", fake_reply_to_lead)
        monkeypatch.setattr(replier.time, "sleep", lambda seconds: None)

        count = replier.run_reply(
            lead_ids=list(range(1, 7)),
            reply_text="话术",
            confirm_real_send=False,
        )

        assert count == 6
        assert used_cookie_indexes[:3] == [0, 0, 0]
        assert used_cookie_indexes[3:] == [1, 1, 1]

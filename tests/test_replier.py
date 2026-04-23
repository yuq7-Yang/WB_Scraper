from weibo_bot import db, replier


def test_run_reply_dry_run_marks_pending_leads_reviewed(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "\u4e0a\u6d77", "\u6c42\u6b3e\u5f0f", "1001", "\u7f8e\u7532\u6b3e\u5f0f")
    monkeypatch.setattr(replier, "REPLY_TEMPLATES", ["\u6b22\u8fce\u4e86\u89e3"])

    count = replier.run_reply(limit=1, dry_run=True)

    lead = db.get_all_leads()[0]
    assert count == 1
    assert lead["status"] == "reviewed"
    assert lead["reply_text"] == "\u6b22\u8fce\u4e86\u89e3"


class TestAutoMatchAndRotation:
    def test_auto_match_uses_generated_reply(self, monkeypatch):
        fake_leads = [
            {
                "id": 1,
                "keyword": "\u7f8e\u7532\u57f9\u8bad",
                "comment_id": "c1",
                "user_name": "u1",
                "status": "pending",
            },
            {
                "id": 2,
                "keyword": "\u8fdb\u8d27",
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
        monkeypatch.setattr(
            replier,
            "generate_reply_for_lead",
            lambda lead: f"\u5b9a\u5236:{lead['keyword']}\uff0c\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002",
        )
        monkeypatch.setattr(replier.time, "sleep", lambda seconds: None)

        count = replier.run_reply(
            lead_ids=[1, 2],
            reply_text="",
            confirm_real_send=False,
            auto_match=True,
        )

        assert count == 2
        assert sent[0]["text"] == "\u5b9a\u5236:\u7f8e\u7532\u57f9\u8bad\uff0c\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002"
        assert sent[1]["text"] == "\u5b9a\u5236:\u8fdb\u8d27\uff0c\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002"

    def test_auto_match_skips_unrelated_comments(self, monkeypatch):
        fake_leads = [
            {
                "id": 1,
                "keyword": "\u732b\u773c\u7f8e\u7532\u63a8\u8350",
                "comment_id": "c1",
                "user_name": "u1",
                "status": "pending",
            }
        ]
        monkeypatch.setattr(replier, "get_leads_by_ids", lambda ids: fake_leads)

        sent = []
        updates = []

        def fake_reply_to_lead(lead, reply_text, confirm_real_send=False, cookie_index=0):
            sent.append(reply_text)
            return True, reply_text

        def fake_update(lead_id, status, reply_text=None):
            updates.append((lead_id, status, reply_text))

        monkeypatch.setattr(replier, "reply_to_lead", fake_reply_to_lead)
        monkeypatch.setattr(replier, "update_lead_status", fake_update)
        monkeypatch.setattr(replier, "generate_reply_for_lead", lambda lead: None)
        monkeypatch.setattr(replier.time, "sleep", lambda seconds: None)

        count = replier.run_reply(
            lead_ids=[1],
            reply_text="",
            confirm_real_send=False,
            auto_match=True,
        )

        assert count == 0
        assert sent == []
        assert updates == [(1, "failed", "comment not relevant for expo reply")]

    def test_manual_mode_uses_same_text(self, monkeypatch):
        fake_leads = [
            {
                "id": 1,
                "keyword": "\u7f8e\u7532\u57f9\u8bad",
                "comment_id": "c1",
                "user_name": "u1",
                "status": "pending",
            },
            {
                "id": 2,
                "keyword": "\u8fdb\u8d27",
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
            reply_text="\u624b\u52a8\u8bdd\u672f\u5185\u5bb9",
            confirm_real_send=False,
            auto_match=False,
        )

        assert count == 2
        assert sent == ["\u624b\u52a8\u8bdd\u672f\u5185\u5bb9", "\u624b\u52a8\u8bdd\u672f\u5185\u5bb9"]

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
                "keyword": "\u7f8e\u7532",
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
            reply_text="\u8bdd\u672f",
            confirm_real_send=False,
        )

        assert count == 6
        assert used_cookie_indexes[:3] == [0, 0, 0]
        assert used_cookie_indexes[3:] == [1, 1, 1]

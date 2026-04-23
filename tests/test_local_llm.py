from weibo_bot import db, local_llm, replier


def test_generate_reply_for_lead_uses_ollama_and_wraps_with_intro_and_cta(monkeypatch):
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434", raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_MODEL", "qwen2.5:3b", raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_TIMEOUT", 9.0, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "LOCAL_LLM_TICKET_CTA",
        "\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002",
        raising=False,
    )

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": "\u5c55\u4f1a\u73b0\u573a\u4f1a\u6709\u4e0d\u5c11\u5c01\u5c42\u548c\u7532\u6cb9\u80f6\u54c1\u724c\u53ef\u4ee5\u76f4\u63a5\u5bf9\u6bd4\u770b"
                }
            }

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(local_llm.requests, "post", fake_post)

    reply = local_llm.generate_reply_for_lead(
        {
            "keyword": "\u7532\u6cb9\u80f6\u63a8\u8350",
            "comment_text": "\u6709\u63a8\u8350\u7684\u5c01\u5c42\u5417<span>[doge]</span>",
        }
    )

    assert (
        reply
        == "\u6211\u8fd9\u8fb9\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684\uff0c\u5c55\u4f1a\u73b0\u573a\u4f1a\u6709\u4e0d\u5c11\u5c01\u5c42\u548c\u7532\u6cb9\u80f6\u54c1\u724c\u53ef\u4ee5\u76f4\u63a5\u5bf9\u6bd4\u770b\uff0c\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002"
    )
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["model"] == "qwen2.5:3b"
    assert captured["json"]["stream"] is False
    assert "\u6709\u63a8\u8350\u7684\u5c01\u5c42\u5417" in captured["json"]["messages"][1]["content"]
    assert "<span>" not in captured["json"]["messages"][1]["content"]


def test_generate_reply_for_lead_strips_duplicate_intro(monkeypatch):
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "LOCAL_LLM_TICKET_CTA",
        "\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002",
        raising=False,
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": "\u6211\u8fd9\u8fb9\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684\uff0c\u73b0\u573a\u4f1a\u6709\u4e0d\u5c11\u57f9\u8bad\u548c\u6750\u6599\u54c1\u724c\u53ef\u4ee5\u76f4\u63a5\u4e86\u89e3"
                }
            }

    monkeypatch.setattr(local_llm.requests, "post", lambda *args, **kwargs: FakeResponse())

    reply = local_llm.generate_reply_for_lead(
        {"keyword": "\u7f8e\u7532\u6559\u5b66", "comment_text": "\u6559\u7a0b\u592a\u7cbe\u81f4\u4e86"}
    )

    assert (
        reply
        == "\u6211\u8fd9\u8fb9\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684\uff0c\u73b0\u573a\u4f1a\u6709\u4e0d\u5c11\u57f9\u8bad\u548c\u6750\u6599\u54c1\u724c\u53ef\u4ee5\u76f4\u63a5\u4e86\u89e3\uff0c\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002"
    )


def test_generate_reply_for_lead_falls_back_to_keyword_template_on_failure(monkeypatch):
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "get_template_by_keyword",
        lambda keyword: f"fallback:{keyword}",
        raising=False,
    )
    monkeypatch.setattr(
        local_llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    reply = local_llm.generate_reply_for_lead(
        {"keyword": "\u7f8e\u7532\u5e97", "comment_text": "\u60f3\u5f00\u5e97"}
    )

    assert reply == "fallback:\u7f8e\u7532\u5e97"


def test_generate_reply_for_lead_returns_keyword_template_when_disabled(monkeypatch):
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", False, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "get_template_by_keyword",
        lambda keyword: f"fallback:{keyword}",
        raising=False,
    )

    reply = local_llm.generate_reply_for_lead(
        {"keyword": "\u7a7f\u6234\u7532", "comment_text": "\u60f3\u62ff\u8d27"}
    )

    assert reply == "fallback:\u7a7f\u6234\u7532"


def test_generate_reply_for_lead_returns_none_for_unrelated_comment(monkeypatch):
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)

    reply = local_llm.generate_reply_for_lead(
        {
            "keyword": "\u732b\u773c\u7f8e\u7532\u63a8\u8350",
            "comment_text": "\u4e3d\u4e3d\u4f60\u4e4b\u524d\u63a8\u8350\u7684\u889c\u5b50\u8fd8\u6709\u94fe\u63a5\u5417\uff08\u4e0d\u662f\u5206\u8dbe\u889c\uff09",
        }
    )

    assert reply is None


def test_run_reply_auto_match_uses_generated_local_reply(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead(
        "alice",
        "\u4e0a\u6d77",
        "\u6709\u63a8\u8350\u7684\u679c\u51bb\u80f6\u5417",
        "1001",
        "\u7532\u6cb9\u80f6\u63a8\u8350",
        comment_id="2001",
    )
    lead_id = db.get_all_leads()[0]["id"]

    monkeypatch.setattr(replier, "ENABLE_REAL_REPLIES", False, raising=False)
    monkeypatch.setattr(
        replier,
        "generate_reply_for_lead",
        lambda lead: "\u6211\u8fd9\u8fb9\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684\uff0c\u73b0\u573a\u4f1a\u6709\u4e0d\u5c11\u7532\u6cb9\u80f6\u548c\u5c01\u5c42\u54c1\u724c\u53ef\u4ee5\u76f4\u63a5\u5bf9\u6bd4\u770b\uff0c\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002",
        raising=False,
    )

    count = replier.run_reply(lead_ids=[lead_id], auto_match=True, confirm_real_send=False)

    lead = db.get_all_leads()[0]
    assert count == 1
    assert lead["status"] == "reviewed"
    assert (
        lead["reply_text"]
        == "\u6211\u8fd9\u8fb9\u662f\u7f8e\u4e1a\u5c55\u4f1a\u7684\uff0c\u73b0\u573a\u4f1a\u6709\u4e0d\u5c11\u7532\u6cb9\u80f6\u548c\u5c01\u5c42\u54c1\u724c\u53ef\u4ee5\u76f4\u63a5\u5bf9\u6bd4\u770b\uff0c\u611f\u5174\u8da3\u53ef\u4ee5\u627e\u6211\u514d\u8d39\u9886\u53d6\u95e8\u7968\u94fe\u63a5\u3002"
    )

from weibo_bot import db, local_llm, replier


def test_generate_reply_for_lead_uses_ollama_and_wraps_with_intro_and_cta(monkeypatch):
    monkeypatch.setattr(local_llm, "_reply_variant_index", 0, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434", raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_MODEL", "qwen2.5:3b", raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_TIMEOUT", 9.0, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "LOCAL_LLM_TICKET_CTA",
        "感兴趣可以私信我，或者找我免费领门票。",
        raising=False,
    )

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": "展会现场会有不少封层和甲油胶品牌可以直接对比看"
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
            "keyword": "甲油胶推荐",
            "comment_text": "有推荐的封层吗<span>[doge]</span>",
        }
    )

    assert "CIBE" not in reply
    assert "展会" in reply
    assert "免费领门票" in reply
    assert "私信我" in reply or "找我" in reply
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["model"] == "qwen2.5:3b"
    assert captured["json"]["stream"] is False
    assert "有推荐的封层吗" in captured["json"]["messages"][1]["content"]
    assert "<span>" not in captured["json"]["messages"][1]["content"]


def test_generate_reply_for_lead_strips_duplicate_intro(monkeypatch):
    monkeypatch.setattr(local_llm, "_reply_variant_index", 0, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "LOCAL_LLM_TICKET_CTA",
        "感兴趣可以私信我，或者找我免费领门票。",
        raising=False,
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": "我这边是美业展会的，现场会有不少培训和材料品牌可以直接了解"
                }
            }

    monkeypatch.setattr(local_llm.requests, "post", lambda *args, **kwargs: FakeResponse())

    reply = local_llm.generate_reply_for_lead(
        {"keyword": "美甲教学", "comment_text": "有教程推荐吗"}
    )

    assert reply.count("我这边是") <= 1
    assert "CIBE" not in reply
    assert "免费领门票" in reply


def test_generate_reply_for_lead_falls_back_to_keyword_template_on_failure(monkeypatch):
    monkeypatch.setattr(local_llm, "_reply_variant_index", 0, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "get_template_by_keyword",
        lambda keyword: "CIBE今年美甲区品牌比较全，有需要的话私信我获取门票。",
        raising=False,
    )
    monkeypatch.setattr(
        local_llm.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    reply = local_llm.generate_reply_for_lead(
        {"keyword": "美甲店", "comment_text": "想开店"}
    )

    assert "CIBE" not in reply
    assert "展会" in reply
    assert "免费领门票" in reply


def test_generate_reply_for_lead_returns_keyword_template_when_disabled(monkeypatch):
    monkeypatch.setattr(local_llm, "_reply_variant_index", 0, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", False, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "get_template_by_keyword",
        lambda keyword: "CIBE今年美甲区品牌比较全，有需要的话私信我获取门票。",
        raising=False,
    )

    reply = local_llm.generate_reply_for_lead(
        {"keyword": "穿戴甲", "comment_text": "想拿货"}
    )

    assert "CIBE" not in reply
    assert "展会" in reply
    assert "免费领门票" in reply


def test_generate_reply_for_lead_returns_none_for_unrelated_comment(monkeypatch):
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)

    reply = local_llm.generate_reply_for_lead(
        {
            "keyword": "猫眼美甲推荐",
            "comment_text": "丽丽你之前推荐的袜子还有链接吗（不是分趾袜）",
        }
    )

    assert reply is None


def test_generate_reply_for_lead_returns_none_without_clear_demand(monkeypatch):
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", True, raising=False)

    reply = local_llm.generate_reply_for_lead(
        {
            "keyword": "果冻胶",
            "comment_text": "这个颜色挺好看",
        }
    )

    assert reply is None


def test_generate_reply_for_lead_accepts_clear_demand_for_guodong_tie(monkeypatch):
    monkeypatch.setattr(local_llm, "_reply_variant_index", 0, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", False, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "get_template_by_keyword",
        lambda keyword: "CIBE现场有不少果冻胶相关品牌，有需要的话私信我获取门票。",
        raising=False,
    )

    reply = local_llm.generate_reply_for_lead(
        {
            "keyword": "果冻贴",
            "comment_text": "果冻贴有推荐的吗",
        }
    )

    assert "CIBE" not in reply
    assert "展会" in reply


def test_generate_reply_for_lead_rotates_auto_match_copy(monkeypatch):
    monkeypatch.setattr(local_llm, "_reply_variant_index", 0, raising=False)
    monkeypatch.setattr(local_llm._config, "LOCAL_LLM_ENABLED", False, raising=False)
    monkeypatch.setattr(
        local_llm._config,
        "get_template_by_keyword",
        lambda keyword: "CIBE展会现场品牌和材料都比较全，有需要的话私信我获取门票。",
        raising=False,
    )

    lead = {"keyword": "美甲", "comment_text": "有推荐的吗"}
    first = local_llm.generate_reply_for_lead(lead)
    second = local_llm.generate_reply_for_lead(lead)

    assert first != second
    assert "CIBE" not in first
    assert "CIBE" not in second
    assert "免费领门票" in first
    assert "免费领门票" in second


def test_run_reply_auto_match_uses_generated_local_reply(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead(
        "alice",
        "上海",
        "有推荐的果冻胶吗",
        "1001",
        "甲油胶推荐",
        comment_id="2001",
    )
    lead_id = db.get_all_leads()[0]["id"]

    monkeypatch.setattr(replier, "ENABLE_REAL_REPLIES", False, raising=False)
    monkeypatch.setattr(
        replier,
        "generate_reply_for_lead",
        lambda lead: "展会现场会有不少甲油胶和封层品牌可以直接对比，感兴趣可以私信我免费领门票。",
        raising=False,
    )

    count = replier.run_reply(lead_ids=[lead_id], auto_match=True, confirm_real_send=False)

    lead = db.get_all_leads()[0]
    assert count == 1
    assert lead["status"] == "reviewed"
    assert (
        lead["reply_text"]
        == "展会现场会有不少甲油胶和封层品牌可以直接对比，感兴趣可以私信我免费领门票。"
    )


def test_build_messages_asks_llm_to_avoid_repeating_same_copy():
    messages = local_llm._build_messages(
        {
            "keyword": "果冻胶",
            "comment_text": "果冻胶有推荐的吗",
        }
    )

    assert "不要和上一条回复使用几乎一样的表达" in messages[0]["content"]

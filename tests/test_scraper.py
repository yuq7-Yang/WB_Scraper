import pytest

from weibo_bot import db, scraper
from weibo_bot.scraper import extract_post_ids, has_intent, is_beauty_keyword, is_east_china


def test_analyze_intent_classifies_b2b_comment():
    result = scraper.analyze_intent("想开店的话加盟哪个品牌更稳", keyword="美甲店")

    assert result["matched"] is True
    assert result["lead_type"] == "b2b"
    assert result["intent_score"] >= 3


def test_analyze_intent_classifies_consumer_comment():
    result = scraper.analyze_intent("封层有没有推荐呀", keyword="甲油胶推荐")

    assert result["matched"] is True
    assert result["lead_type"] == "consumer"
    assert result["intent_score"] >= 3


def test_is_east_china_matches_known_regions():
    assert is_east_china("来自上海") is True
    assert is_east_china("来自广东") is False
    assert is_east_china("") is False


def test_extract_post_ids_reads_card_type_9_only():
    data = {
        "data": {
            "cards": [
                {"card_type": 9, "mblog": {"id": "101"}},
                {"card_type": 11, "mblog": {"id": "skip"}},
                {"card_type": 9, "mblog": {}},
            ]
        }
    }

    assert extract_post_ids(data) == ["101"]


def test_extract_post_ids_skips_posts_older_than_90_days(monkeypatch):
    class FrozenDatetime(scraper.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 16, tzinfo=tz)

    monkeypatch.setattr(scraper, "datetime", FrozenDatetime)
    data = {
        "data": {
            "cards": [
                {
                    "card_type": 9,
                    "mblog": {
                        "id": "recent",
                        "created_at": "Wed Apr 15 09:30:00 +0800 2026",
                    },
                },
                {
                    "card_type": 9,
                    "mblog": {
                        "id": "old",
                        "created_at": "Mon Jan 01 09:30:00 +0800 2024",
                    },
                },
            ]
        }
    }

    assert extract_post_ids(data) == ["recent"]


def test_is_beauty_keyword_uses_beauty_terms_whitelist():
    assert is_beauty_keyword("上海美甲店") is True
    for keyword in ["穿戴甲", "甲片", "饰品", "工具设备", "半永久", "美甲店加盟", "美睫进货", "果冻胶", "果冻贴推荐"]:
        assert is_beauty_keyword(keyword) is True
    assert is_beauty_keyword("周末露营") is False


def test_has_intent_uses_intent_keyword_whitelist():
    assert has_intent("想做美甲，怎么预约") is True
    for text in ["好美！种草！", "手机壳有链接吗", "下单啦，卸甲难不难", "正想要，感谢分享"]:
        assert has_intent(text) is True
    assert has_intent("这个颜色真好看") is False
    assert has_intent("") is False


def test_fetch_comments_follows_hotflow_pages(monkeypatch):
    requested_urls = []

    def fake_scrape_json(url, cookie_index=0, client=None):
        requested_urls.append(url)
        if "max_id=next-page" in url:
            return {
                "ok": 1,
                "data": {
                    "data": [{"id": "2", "text": "第二页"}],
                    "max_id": 0,
                },
            }
        return {
            "ok": 1,
            "data": {
                "data": [{"id": "1", "text": "第一页"}],
                "max_id": "next-page",
            },
        }

    monkeypatch.setattr(scraper, "_scrape_json", fake_scrape_json)

    comments = scraper.fetch_comments("1001", max_pages=2)

    assert [comment["id"] for comment in comments] == ["1", "2"]
    assert "max_id=next-page" in requested_urls[1]


def test_fetch_comments_uses_configured_page_delay(monkeypatch):
    requested_urls = []
    sleep_calls = []

    def fake_scrape_json(url, cookie_index=0, client=None):
        requested_urls.append(url)
        if "max_id=next-page" in url:
            return {
                "ok": 1,
                "data": {
                    "data": [{"id": "2", "text": "page2"}],
                    "max_id": 0,
                },
            }
        return {
            "ok": 1,
            "data": {
                "data": [{"id": "1", "text": "page1"}],
                "max_id": "next-page",
            },
        }

    monkeypatch.setattr(scraper, "_scrape_json", fake_scrape_json)
    monkeypatch.setattr(scraper, "SCRAPE_PAGE_DELAY", 0.25, raising=False)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    comments = scraper.fetch_comments("1001", max_pages=2)

    assert [comment["id"] for comment in comments] == ["1", "2"]
    assert "max_id=next-page" in requested_urls[1]
    assert sleep_calls == [0.25]


def test_run_scrape_requires_credentials(monkeypatch):
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "")
    monkeypatch.setattr(scraper, "COOKIES", [])

    with pytest.raises(RuntimeError, match="SCRAPFLY_KEY"):
        scraper.run_scrape()


def test_run_scrape_accepts_intent_comments_from_any_region(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "key")
    monkeypatch.setattr(scraper, "COOKIES", ["cookie"])
    monkeypatch.setattr(scraper, "KEYWORDS", ["美甲店"])
    monkeypatch.setattr(scraper, "MAX_COMMENTS_PER_KEYWORD", 2, raising=False)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper, "search_posts", lambda *args, **kwargs: ["1001", "1002"])
    monkeypatch.setattr(
        scraper,
        "fetch_comments",
        lambda *args, **kwargs: [
            {"source": "来自上海", "user": {"screen_name": "alice"}, "text": "想做美甲"},
            {"source": "来自广东", "user": {"screen_name": "bob"}, "text": "求推荐"},
            {"source": "来自江苏", "user": {"screen_name": "cathy"}, "text": "看款式"},
        ],
    )

    count = scraper.run_scrape()

    assert count == 2
    leads = db.get_all_leads()
    assert len(leads) == 2
    assert {lead["user_name"] for lead in leads} == {"alice", "bob"}
    assert any(lead["location"] == "来自广东" for lead in leads)


def test_run_scrape_skips_comments_without_intent(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "key")
    monkeypatch.setattr(scraper, "COOKIES", ["cookie"])
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper, "search_posts", lambda *args, **kwargs: ["1001"])
    monkeypatch.setattr(
        scraper,
        "fetch_comments",
        lambda *args, **kwargs: [
            {"source": "来自上海", "user": {"screen_name": "alice"}, "text": "这个颜色真好看"},
            {"source": "来自浙江", "user": {"screen_name": "bob"}, "text": "美甲培训多少钱"},
        ],
    )

    count = scraper.run_scrape(keywords=["美甲"], max_per_keyword=10, max_total=10)

    assert count == 1
    leads = db.get_all_leads()
    assert len(leads) == 1
    assert leads[0]["user_name"] == "bob"


def test_run_scrape_saves_weibo_comment_id(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "key")
    monkeypatch.setattr(scraper, "COOKIES", ["cookie"])
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper, "search_posts", lambda *args, **kwargs: ["1001"])
    monkeypatch.setattr(
        scraper,
        "fetch_comments",
        lambda *args, **kwargs: [
            {
                "id": "2001",
                "source": "来自上海",
                "user": {"screen_name": "alice"},
                "text": "想做美甲",
            }
        ],
    )

    count = scraper.run_scrape(keywords=["美甲"], max_per_keyword=1, max_total=1)

    lead = db.get_all_leads()[0]
    assert count == 1
    assert lead["comment_id"] == "2001"


def test_run_scrape_sanitizes_comment_html_before_saving(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "key")
    monkeypatch.setattr(scraper, "COOKIES", ["cookie"])
    monkeypatch.setattr(scraper, "has_intent", lambda text: True)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper, "search_posts", lambda *args, **kwargs: ["1001"])
    monkeypatch.setattr(
        scraper,
        "fetch_comments",
        lambda *args, **kwargs: [
            {
                "id": "2001",
                "source": "鏉ヨ嚜涓婃捣",
                "user": {"screen_name": "alice"},
                "text": '封层有没有推荐呀 <a href="https://example.com"><span class="surl-text">查看图片</span></a>',
            }
        ],
    )

    count = scraper.run_scrape(keywords=["甲油胶推荐"], max_per_keyword=1, max_total=1)

    lead = db.get_all_leads()[0]
    assert count == 1
    assert "<a href=" not in lead["comment_text"]
    assert "<span" not in lead["comment_text"]


def test_run_scrape_rejects_unrelated_comments_and_saves_lead_metadata(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "key")
    monkeypatch.setattr(scraper, "COOKIES", ["cookie"])
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scraper, "search_posts", lambda *args, **kwargs: ["1001"])
    monkeypatch.setattr(
        scraper,
        "fetch_comments",
        lambda *args, **kwargs: [
            {"source": "来自山东", "user": {"screen_name": "a"}, "text": "宝宝推荐一个奶茶好不好"},
            {"source": "来自江苏", "user": {"screen_name": "b"}, "text": "封层有没有推荐呀"},
            {"source": "来自上海", "user": {"screen_name": "c"}, "text": "想开店的话加盟哪个品牌更稳"},
        ],
    )

    count = scraper.run_scrape(keywords=["甲油胶推荐"], max_per_keyword=10, max_total=10)

    leads = db.get_all_leads()
    assert count == 2
    assert len(leads) == 2
    by_user = {lead["user_name"]: lead for lead in leads}
    assert "a" not in by_user
    assert by_user["b"]["lead_type"] == "consumer"
    assert by_user["b"]["intent_score"] >= 3
    assert by_user["c"]["lead_type"] == "b2b"
    assert by_user["c"]["intent_score"] >= 3


def test_run_scrape_uses_configured_post_and_keyword_delays(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    sleep_calls = []

    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "key")
    monkeypatch.setattr(scraper, "COOKIES", ["cookie"])
    monkeypatch.setattr(scraper, "SCRAPE_POST_DELAY", 0.2, raising=False)
    monkeypatch.setattr(scraper, "SCRAPE_KEYWORD_DELAY", 0.5, raising=False)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(scraper, "search_posts", lambda *args, **kwargs: ["1001"])
    monkeypatch.setattr(scraper, "fetch_comments", lambda *args, **kwargs: [])

    count = scraper.run_scrape(keywords=["kw1", "kw2"], max_per_keyword=1, max_total=10)

    assert count == 0
    assert sleep_calls == [0.2, 0.5, 0.2, 0.5]

import pytest

from weibo_bot import db, scraper
from weibo_bot.scraper import extract_post_ids, has_intent, is_beauty_keyword, is_east_china


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
    assert is_beauty_keyword("周末露营") is False


def test_has_intent_uses_intent_keyword_whitelist():
    assert has_intent("想做美甲，怎么预约") is True
    assert has_intent("这个颜色真好看") is False
    assert has_intent("") is False


def test_run_scrape_requires_credentials(monkeypatch):
    monkeypatch.setattr(scraper, "SCRAPFLY_KEY", "")
    monkeypatch.setattr(scraper, "COOKIES", [])

    with pytest.raises(RuntimeError, match="SCRAPFLY_KEY"):
        scraper.run_scrape()


def test_run_scrape_limits_east_china_comments_per_keyword(tmp_path, monkeypatch):
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
            {"source": "来自浙江", "user": {"screen_name": "bob"}, "text": "求推荐"},
            {"source": "来自江苏", "user": {"screen_name": "cathy"}, "text": "看款式"},
        ],
    )

    count = scraper.run_scrape()

    assert count == 2
    leads = db.get_all_leads()
    assert len(leads) == 2
    assert [lead["user_name"] for lead in leads] == ["bob", "alice"]


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

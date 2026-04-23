from weibo_bot import db, replier, scraper


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


def test_run_reply_rotates_cookies_every_three_replies_and_uses_reply_delay(tmp_path, monkeypatch):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    for idx in range(4):
        db.insert_lead(f"user{idx}", "上海", f"comment-{idx}", f"{1000 + idx}", "美甲", comment_id=f"{2000 + idx}")

    cookie_calls = []
    sleep_calls = []

    monkeypatch.setattr(replier, "ENABLE_REAL_REPLIES", True, raising=False)
    monkeypatch.setattr(replier, "REPLIES_PER_ACCOUNT", 3, raising=False)
    monkeypatch.setattr(replier, "REPLY_DELAY", 3, raising=False)
    monkeypatch.setattr(replier, "ACCOUNT_SWITCH_DELAY", 5, raising=False)
    monkeypatch.setattr(
        replier,
        "_send_real_reply",
        lambda lead, reply_text, cookie_index=0: cookie_calls.append((lead["id"], cookie_index)) or (True, reply_text),
        raising=False,
    )
    monkeypatch.setattr(replier.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    count = replier.run_reply(
        lead_ids=[row["id"] for row in db.get_all_leads()],
        reply_text="hello",
        confirm_real_send=True,
    )

    assert count == 4
    assert [cookie_index for _, cookie_index in cookie_calls] == [0, 0, 0, 1]
    assert sleep_calls == [3, 3, 5]

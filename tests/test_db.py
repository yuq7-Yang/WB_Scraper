from weibo_bot import db


def test_insert_lead_ignores_duplicate_post_user(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()

    first = db.insert_lead("alice", "上海", "想做美甲", "1001", "美甲店")
    second = db.insert_lead("alice", "上海", "想做美甲", "1001", "美甲店")

    assert first is True
    assert second is False
    assert len(db.get_all_leads()) == 1


def test_update_status_records_reply_text(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "浙江", "求推荐", "1002", "美睫店")

    lead = db.get_pending_leads(limit=1)[0]
    db.update_lead_status(lead["id"], "reviewed", "欢迎了解")

    updated = db.get_all_leads()[0]
    assert updated["status"] == "reviewed"
    assert updated["reply_text"] == "欢迎了解"
    assert updated["replied_at"]


def test_init_db_migrates_and_insert_lead_stores_comment_id(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()

    inserted = db.insert_lead(
        "alice",
        "上海",
        "想做美甲",
        "1001",
        "美甲店",
        comment_id="2001",
    )

    lead = db.get_all_leads()[0]
    assert inserted is True
    assert lead["comment_id"] == "2001"

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

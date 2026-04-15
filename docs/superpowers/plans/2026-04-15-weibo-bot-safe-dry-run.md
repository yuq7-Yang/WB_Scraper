# Weibo Bot Safe Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working local version of the Weibo beauty lead dashboard with safe dry-run reply handling.

**Architecture:** Use a small Python package under `weibo_bot/`. Flask serves the dashboard and JSON APIs, SQLite stores leads, Scrapfly-backed collection is isolated in `scraper.py`, and reply handling records previews instead of sending real messages.

**Tech Stack:** Python 3, Flask, SQLite, Scrapfly SDK, pytest.

---

## File Structure

- Create: `requirements.txt` for runtime and test dependencies.
- Create: `README.md` for local setup and safe operating notes.
- Create: `weibo_bot/__init__.py` to mark the app package.
- Create: `weibo_bot/config.py` for environment-backed settings.
- Create: `weibo_bot/db.py` for SQLite access.
- Create: `weibo_bot/scraper.py` for collection helpers and Scrapfly calls.
- Create: `weibo_bot/replier.py` for dry-run reply preview flow.
- Create: `weibo_bot/dashboard.py` for Flask routes and HTML panel.
- Create: `tests/test_db.py` for database behavior.
- Create: `tests/test_scraper.py` for region filtering and parsing.
- Create: `tests/test_replier.py` for dry-run behavior.
- Create: `tests/test_dashboard.py` for Flask API behavior.

### Task 1: Tests First

**Files:**
- Create: `tests/test_db.py`
- Create: `tests/test_scraper.py`
- Create: `tests/test_replier.py`
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing database tests**

```python
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
```

- [ ] **Step 2: Write failing scraper tests**

```python
from weibo_bot.scraper import extract_post_ids, is_east_china

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
```

- [ ] **Step 3: Write failing dry-run reply tests**

```python
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
```

- [ ] **Step 4: Write failing dashboard API tests**

```python
from weibo_bot import dashboard, db

def test_api_leads_returns_inserted_rows(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "求推荐", "1001", "美甲店")
    client = dashboard.app.test_client()
    response = client.get("/api/leads")
    assert response.status_code == 200
    assert response.get_json()[0]["user_name"] == "alice"

def test_retry_resets_failed_row_to_pending(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    db.insert_lead("alice", "上海", "求推荐", "1001", "美甲店")
    lead = db.get_pending_leads(1)[0]
    db.update_lead_status(lead["id"], "failed", "network")
    client = dashboard.app.test_client()
    response = client.post(f"/api/retry/{lead['id']}")
    assert response.status_code == 200
    assert db.get_all_leads()[0]["status"] == "pending"
```

- [ ] **Step 5: Run tests to verify RED**

Run: `python -m pytest -q`

Expected: import failures for missing `weibo_bot` modules.

### Task 2: Implement Core Modules

**Files:**
- Create: `weibo_bot/__init__.py`
- Create: `weibo_bot/config.py`
- Create: `weibo_bot/db.py`
- Create: `weibo_bot/scraper.py`
- Create: `weibo_bot/replier.py`

- [ ] **Step 1: Implement config**

`config.py` reads `SCRAPFLY_KEY`, `WEIBO_COOKIES`, and `DRY_RUN_REPLIES` from environment variables. Defaults keep replies dry-run and collection disabled until credentials exist.

- [ ] **Step 2: Implement SQLite helpers**

`db.configure()` switches the database path for tests. `insert_lead()` returns `True` when a row is inserted and `False` for a duplicate.

- [ ] **Step 3: Implement scraper helpers**

`extract_post_ids()` parses already-loaded JSON dictionaries. `run_scrape()` imports Scrapfly lazily so tests can run without credentials.

- [ ] **Step 4: Implement dry-run replier**

`run_reply()` gets pending leads, chooses reply templates, and calls `update_lead_status(..., "reviewed", reply_text)` when `dry_run=True`.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_db.py tests/test_scraper.py tests/test_replier.py -q`

Expected: all selected tests pass.

### Task 3: Implement Dashboard

**Files:**
- Create: `weibo_bot/dashboard.py`
- Create: `requirements.txt`
- Create: `README.md`

- [ ] **Step 1: Implement Flask routes**

Routes:

- `GET /` renders the local dashboard.
- `GET /api/leads` returns all database rows.
- `POST /api/scrape` starts collection in a background thread.
- `POST /api/reply` starts dry-run reply review in a background thread.
- `POST /api/retry/<lead_id>` resets a row to `pending`.
- `GET /stream` returns server-sent progress events.

- [ ] **Step 2: Run dashboard tests**

Run: `python -m pytest tests/test_dashboard.py -q`

Expected: dashboard API tests pass.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -q`

Expected: all tests pass.

### Task 4: Manual Startup Check

**Files:**
- Modify: none unless verification finds a defect.

- [ ] **Step 1: Check imports**

Run: `python -m compileall weibo_bot tests`

Expected: command exits with status 0.

- [ ] **Step 2: Start app when dependencies are available**

Run: `python -m weibo_bot.dashboard`

Expected: Flask starts on `http://127.0.0.1:5000` and the dashboard opens in a browser.

## Self-Review

- The plan covers the requested written plan and safer dry-run implementation.
- It does not enable real automated replies.
- It includes tests before production code.
- It keeps secrets out of source files.

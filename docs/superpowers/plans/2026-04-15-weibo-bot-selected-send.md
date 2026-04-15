# Weibo Bot Selected Send Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the updated plan's keyword selection and selected-user send workflow while keeping real replies behind a two-step safety gate.

**Architecture:** Extend the existing Flask package. `config.py` owns the real-send flag, `scraper.py` accepts runtime keyword/limit parameters, `replier.py` accepts selected lead IDs and reply text with a dry-run default, and `dashboard.py` renders the richer control panel and JSON APIs.

**Tech Stack:** Python 3, Flask, SQLite, Scrapfly SDK, pytest.

---

### Task 1: Capture New Behavior With Tests

**Files:**
- Modify: `tests/test_scraper.py`
- Modify: `tests/test_replier.py`
- Modify: `tests/test_dashboard.py`
- Modify: `tests/test_config.py`

- [ ] Add tests for scrape caps and selected keyword API payload.
- [ ] Add tests for selected reply IDs and selected template text.
- [ ] Add tests proving real send is blocked unless both `ENABLE_REAL_REPLIES` and `confirm_real_send` are true.
- [ ] Add dashboard HTML tests for keyword controls, selection controls, and template modal.
- [ ] Run focused tests and confirm failures.

### Task 2: Implement Runtime Settings

**Files:**
- Modify: `weibo_bot/config.py`
- Modify: `.env.example`
- Modify: `README.md`

- [ ] Add `ENABLE_REAL_REPLIES`, `DEFAULT_MAX_PER_KEYWORD`, and `DEFAULT_MAX_TOTAL`.
- [ ] Document that real sends require `.env` opt-in plus modal confirmation.

### Task 3: Implement Scrape API Shape

**Files:**
- Modify: `weibo_bot/scraper.py`
- Modify: `weibo_bot/dashboard.py`

- [ ] Update `run_scrape(keywords=None, max_per_keyword=..., max_total=...)`.
- [ ] Update `/api/scrape` to parse JSON and pass runtime limits.
- [ ] Keep credential validation and progress callbacks.

### Task 4: Implement Selected Reply Flow

**Files:**
- Modify: `weibo_bot/replier.py`
- Modify: `weibo_bot/dashboard.py`

- [ ] Add selected-lead lookup.
- [ ] Update `run_reply(lead_ids, reply_text, confirm_real_send=False)`.
- [ ] Add real-send implementation behind `ENABLE_REAL_REPLIES and confirm_real_send`.
- [ ] Keep dry-run status as `reviewed`.

### Task 5: Implement Dashboard UI

**Files:**
- Modify: `weibo_bot/dashboard.py`

- [ ] Render keyword chips, custom keyword textarea, and scrape limit inputs.
- [ ] Render row checkboxes, all-pending selection, clear selection, single-send buttons.
- [ ] Render template modal and explicit confirmation checkbox.
- [ ] Keep CSV export and post links.

### Task 6: Verify and Restart

**Files:**
- None unless verification finds a defect.

- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m compileall weibo_bot tests scripts`.
- [ ] Restart the Flask panel.
- [ ] Smoke-test `/`, `/api/leads`, `/api/templates`, and `/api/export.csv`.

# Intent Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve scrape quality by classifying leads into B2B and consumer intent, scoring relevance, and filtering out weak or unrelated comments before they enter the reply workflow.

**Architecture:** Keep the existing Scrapfly scrape flow, but replace the single `has_intent()` gate with a small intent-analysis pipeline. The pipeline will sanitize comment text, reject unrelated content, assign a `lead_type` and `intent_score`, and only insert comments that pass a configurable threshold. Dashboard APIs will surface the new fields for operators.

**Tech Stack:** Python, Flask, SQLite, pytest

---

### Task 1: Define intent model and config

**Files:**
- Modify: `weibo_bot/config.py`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: Write the failing tests for classification thresholds**

```python
def test_analyze_intent_classifies_b2b_comment():
    result = scraper.analyze_intent("想开店的话加盟哪个品牌更稳")
    assert result["matched"] is True
    assert result["lead_type"] == "b2b"
    assert result["intent_score"] >= 3


def test_analyze_intent_classifies_consumer_comment():
    result = scraper.analyze_intent("封层有没有推荐呀")
    assert result["matched"] is True
    assert result["lead_type"] == "consumer"
    assert result["intent_score"] >= 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scraper.py -k analyze_intent -q`  
Expected: FAIL because `analyze_intent` does not exist yet.

- [ ] **Step 3: Add explicit intent config in `weibo_bot/config.py`**

Add grouped term lists and thresholds:

```python
B2B_INTENT_TERMS = [...]
CONSUMER_INTENT_TERMS = [...]
UNRELATED_COMMENT_TERMS = [...]
MIN_B2B_INTENT_SCORE = _env_int("MIN_B2B_INTENT_SCORE", 3)
MIN_CONSUMER_INTENT_SCORE = _env_int("MIN_CONSUMER_INTENT_SCORE", 3)
```

- [ ] **Step 4: Run tests again**

Run: `pytest tests/test_scraper.py -k analyze_intent -q`  
Expected: still FAIL, but now only on missing scraper logic.

- [ ] **Step 5: Commit**

```bash
git add weibo_bot/config.py tests/test_scraper.py
git commit -m "feat: add intent filter config groups"
```

### Task 2: Replace weak scrape gating with scored intent analysis

**Files:**
- Modify: `weibo_bot/scraper.py`
- Modify: `weibo_bot/local_llm.py`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: Write failing scrape tests for unrelated rejection and lead typing**

```python
def test_run_scrape_rejects_unrelated_comments(tmp_path, monkeypatch):
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
        ],
    )

    count = scraper.run_scrape(keywords=["甲油胶推荐"], max_per_keyword=10, max_total=10)

    leads = db.get_all_leads()
    assert count == 1
    assert len(leads) == 1
    assert leads[0]["user_name"] == "b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scraper.py -k "unrelated or lead_type" -q`  
Expected: FAIL because scrape still inserts weak or unrelated comments.

- [ ] **Step 3: Implement `analyze_intent()` in `weibo_bot/scraper.py`**

Add:

```python
def analyze_intent(text: str | None, keyword: str | None = None) -> dict[str, Any]:
    clean_text = sanitize_comment_text(text)
    clean_keyword = sanitize_comment_text(keyword)
    ...
    return {
        "matched": passed,
        "lead_type": lead_type,
        "intent_score": score,
        "clean_text": clean_text,
    }
```

- [ ] **Step 4: Use `analyze_intent()` inside `run_scrape()`**

Insert only when `matched` is true, and pass `clean_text` into `insert_lead(...)`.

- [ ] **Step 5: Keep local reply gating aligned**

Update `weibo_bot/local_llm.py` to reuse the same “unrelated” logic or import shared helpers so scrape and reply do not drift.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_scraper.py tests/test_local_llm.py -q`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add weibo_bot/scraper.py weibo_bot/local_llm.py tests/test_scraper.py tests/test_local_llm.py
git commit -m "feat: score and classify scrape intent"
```

### Task 3: Persist lead type and score in SQLite

**Files:**
- Modify: `weibo_bot/db.py`
- Test: `tests/test_db.py`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: Write failing DB migration tests**

```python
def test_init_db_adds_lead_type_and_intent_score_columns(tmp_path):
    db.configure(str(tmp_path / "weibo.db"))
    db.init_db()
    rows = db.get_all_leads()
    assert rows == []
```

Add an explicit PRAGMA check in the real test body for `lead_type` and `intent_score`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -k lead_type -q`  
Expected: FAIL because columns do not exist.

- [ ] **Step 3: Extend schema and insert API**

Update `init_db()` and `insert_lead()`:

```python
lead_type TEXT,
intent_score INTEGER DEFAULT 0,
```

and:

```python
def insert_lead(..., lead_type: str | None = None, intent_score: int = 0) -> bool:
```

- [ ] **Step 4: Pass classification fields from scraper**

Update scraper call sites so saved rows include `lead_type` and `intent_score`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_db.py tests/test_scraper.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add weibo_bot/db.py tests/test_db.py tests/test_scraper.py
git commit -m "feat: persist lead intent metadata"
```

### Task 4: Surface lead type and score in dashboard APIs and table

**Files:**
- Modify: `weibo_bot/dashboard.py`
- Test: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing dashboard tests**

```python
def test_api_leads_includes_lead_type_and_intent_score(tmp_path):
    ...
    payload = response.get_json()[0]
    assert payload["lead_type"] == "consumer"
    assert payload["intent_score"] == 4
```

Also add an HTML assertion for the table headers.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard.py -k "lead_type or intent_score" -q`  
Expected: FAIL because the API/table does not include the new fields.

- [ ] **Step 3: Update API serialization and table rendering**

Add the new fields to `/api/leads`, CSV export, and table columns in the inline HTML script:

```javascript
tr.appendChild(cell(row.lead_type || ""));
tr.appendChild(cell(String(row.intent_score ?? "")));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add weibo_bot/dashboard.py tests/test_dashboard.py
git commit -m "feat: show intent type and score in dashboard"
```

### Task 5: Full regression and live smoke verification

**Files:**
- Modify: none unless regression reveals a gap
- Test: `tests/test_scraper.py`
- Test: `tests/test_dashboard.py`
- Test: `tests/test_local_llm.py`
- Test: `tests/test_replier.py`

- [ ] **Step 1: Run full automated test suite**

Run: `pytest -q`  
Expected: PASS

- [ ] **Step 2: Run a live scrape smoke test**

Run:

```powershell
@'
import sys
sys.path.insert(0, r'D:\美甲美睫\wb_scraper')
from weibo_bot.scraper import run_scrape
count = run_scrape(keywords=['甲油胶推荐'], max_per_keyword=3, max_total=3)
print('COUNT', count)
'@ | python -
```

Expected: returns a small positive count and inserts cleaner comments than before.

- [ ] **Step 3: Restart dashboard and verify API shape**

Run:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*-m weibo_bot.dashboard*' -and $_.Name -like 'python*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Process -FilePath python -ArgumentList '-m','weibo_bot.dashboard' -WorkingDirectory 'D:\美甲美睫\wb_scraper'
Start-Sleep -Seconds 3
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/api/leads
```

Expected: HTTP 200 and JSON rows that include `lead_type` and `intent_score`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: tighten lead intent filtering"
```

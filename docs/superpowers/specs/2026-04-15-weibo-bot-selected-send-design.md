# Weibo Bot Selected Send Design

**Goal:** Match the updated operating plan with keyword selection, bounded scraping, selected-user reply flow, and a real-send safety gate.

## Approved Approach

Use方案 B: implement the updated dashboard and API shape, but keep real Weibo replies disabled unless two independent confirmations are present:

- `.env` contains `ENABLE_REAL_REPLIES=true`.
- The dashboard request includes `confirm_real_send=true`.

When either condition is missing, replies stay in dry-run mode and are recorded locally as `reviewed`.

## Behavior

The dashboard shows preset keyword chips from `KEYWORDS`, an extra keyword textarea, per-keyword and total scrape limits, row checkboxes, "全选待回复", "清空勾选", single-send buttons, a template picker modal, and existing CSV export.

`POST /api/scrape` accepts JSON:

```json
{
  "keywords": ["美甲店"],
  "max_per_keyword": 2,
  "max_total": 20
}
```

`POST /api/reply` accepts JSON:

```json
{
  "lead_ids": [1, 2],
  "reply_text": "您好，欢迎了解",
  "confirm_real_send": false
}
```

The reply runner records selected replies in dry-run mode and only calls Scrapfly browser automation when `ENABLE_REAL_REPLIES=true` and `confirm_real_send=true`.

## Safety

The app defaults to dry-run. The visible dashboard copy says "真实发送未开启" unless the environment flag is enabled. The request-level confirmation prevents accidental real sends if a user simply clicks the modal.

## Tests

Tests cover:

- Scrape API passes selected keywords and limits to `run_scrape`.
- Scraper enforces per-keyword and total caps.
- Reply API passes selected lead ids and chosen reply text.
- Dry-run reply records selected text and marks rows `reviewed`.
- Real-send path is blocked without both confirmations.
- Dashboard HTML includes keyword controls, row-selection controls, template modal, and real-send safety copy.

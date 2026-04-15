# Weibo Bot Safe Dry-Run Design

**Goal:** Build a local Flask and SQLite control panel for collecting Weibo beauty leads, while keeping reply automation in dry-run mode by default.

**Approved Approach:** The project starts from the written plan and implements the safer version first. Collection can call Scrapfly when credentials are configured. Reply actions do not send real Weibo messages in this phase; they record a preview reply and mark the row as `reviewed`.

## Architecture

The application lives under `weibo_bot/` and is split into small modules:

- `config.py` owns runtime settings, keywords, regions, reply templates, and safety flags.
- `db.py` owns SQLite schema creation and lead status updates.
- `scraper.py` owns Weibo search/comment parsing and Scrapfly-backed collection.
- `replier.py` owns reply preview selection and dry-run status updates.
- `dashboard.py` owns the Flask routes, SSE progress stream, and browser panel.

The database stores leads with a simple status flow:

- `pending`: collected and awaiting review.
- `reviewed`: a dry-run reply was selected and recorded.
- `failed`: an operation failed and can be reset to `pending`.

## Safety

Real reply sending is not enabled in this phase. The reply runner uses `DRY_RUN_REPLIES = True` and records the selected reply text locally. A later real-send phase should require explicit user confirmation, current platform terms review, and a separate implementation path.

Secrets stay out of source control. `config.py` reads `SCRAPFLY_KEY`, `WEIBO_COOKIES`, and optional `DRY_RUN_REPLIES` from environment variables, while still providing editable defaults for keywords and templates.

## Data Flow

1. The dashboard calls `/api/scrape`.
2. `scraper.run_scrape()` searches Weibo by keyword, fetches comments, filters `source` by East China region, and inserts matching leads.
3. The dashboard table reads `/api/leads`.
4. The dashboard calls `/api/reply`.
5. `replier.run_reply()` selects pending leads, records reply previews, and marks them `reviewed`.
6. A failed row can be reset through `/api/retry/<id>`.

## Testing

Tests cover:

- East China source filtering.
- SQLite lead insertion, duplicate handling, pending selection, and status updates.
- Dry-run reply behavior without network calls.
- Flask API shape for `/api/leads` and retry reset.

The tests use temporary SQLite files and dependency injection where needed, so they do not require Scrapfly credentials or Weibo network access.

## Scope Notes

This phase creates a working local skeleton and safe reply preview mode. It does not perform real automated replies. Credit balance display is kept as configurable text until a verified Scrapfly account API integration is added.

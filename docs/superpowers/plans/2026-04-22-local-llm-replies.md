# Local LLM Replies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only Ollama/Qwen reply generator that customizes each reply from the scraped comment while always ending with a fixed private-message ticket CTA.

**Architecture:** Keep Scrapfly residential proxy scraping unchanged. Add a local LLM adapter in the reply pipeline that is only used for auto-match replies; if generation fails or is disabled, fall back to the existing keyword-template path. Surface the local-LLM status in the dashboard so the operator knows whether replies are using the local model or template fallback.

**Tech Stack:** Python, Flask, requests, SQLite, Ollama local HTTP API

---

### Task 1: Add local LLM configuration

**Files:**
- Modify: `weibo_bot/config.py`
- Test: `tests/test_selected_workflow.py`

- [ ] Add env-backed settings for local LLM enablement, base URL, model name, timeout, and fixed ticket CTA.
- [ ] Keep defaults local-only and safe: disabled by default, `http://127.0.0.1:11434`, model `qwen2.5`.
- [ ] Add a small parsing test if needed through existing config coverage.

### Task 2: Add local reply generator with fallback

**Files:**
- Modify: `weibo_bot/replier.py`
- Test: `tests/test_local_llm.py`

- [ ] Write failing tests for:
  - successful Ollama generation
  - generated reply always ending with the fixed CTA
  - failure falling back to `get_template_by_keyword`
  - `auto_match=False` continuing to respect manual/template replies
- [ ] Add a local Ollama adapter using the local HTTP API.
- [ ] Build a prompt from `keyword` and cleaned `comment_text`, requiring short, natural Chinese copy with no markdown.
- [ ] Normalize model output and append the fixed CTA in code.
- [ ] Route `auto_match=True` through the local generator first, then keyword-template fallback.

### Task 3: Show local reply mode in the dashboard

**Files:**
- Modify: `weibo_bot/dashboard.py`
- Test: `tests/test_dashboard.py`

- [ ] Add template context showing whether local LLM generation is enabled.
- [ ] Update modal/help copy so the operator knows auto-match can use local AI.
- [ ] Keep existing batch send flow unchanged.

### Task 4: Verify end to end

**Files:**
- Test: `tests/test_local_llm.py`
- Test: `tests/test_dashboard.py`
- Test: `tests/test_selected_workflow.py`

- [ ] Run targeted tests first.
- [ ] Run full `pytest -q`.
- [ ] Restart the dashboard so it picks up the new env-backed settings.

import importlib

from weibo_bot import keyword_store


def test_keyword_store_loads_active_keywords_path_from_env_file(tmp_path, monkeypatch):
    configured_path = tmp_path / "data" / "active_keywords.json"
    configured_path.parent.mkdir()
    configured_path.write_text('["from-env-file"]', encoding="utf-8")
    (tmp_path / ".env").write_text(
        f'ACTIVE_KEYWORDS_PATH="{configured_path}"\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ACTIVE_KEYWORDS_PATH", raising=False)
    importlib.reload(keyword_store)

    try:
        assert keyword_store.KEYWORDS_PATH == configured_path
        assert keyword_store.load_keywords() == ["from-env-file"]
    finally:
        keyword_store.configure("active_keywords.json")

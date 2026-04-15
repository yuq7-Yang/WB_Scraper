from scripts.setup_credentials import build_env_content


def test_build_env_content_accepts_one_cookie():
    content = build_env_content("key", ["SUB=one;"])

    assert 'SCRAPFLY_KEY="key"' in content
    assert 'WEIBO_COOKIES="SUB=one;"' in content
    assert 'DRY_RUN_REPLIES="true"' in content

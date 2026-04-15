from weibo_bot.config import parse_env_file


def test_parse_env_file_reads_simple_key_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'SCRAPFLY_KEY="abc123"\nWEIBO_COOKIES=SUB=one;||SUB=two;\n',
        encoding="utf-8",
    )

    values = parse_env_file(str(env_file))

    assert values["SCRAPFLY_KEY"] == "abc123"
    assert values["WEIBO_COOKIES"] == "SUB=one;||SUB=two;"

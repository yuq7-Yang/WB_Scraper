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


def test_parse_env_file_strips_utf8_bom_from_first_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        '\ufeffSCRAPFLY_KEY="abc123"\nWEIBO_COOKIES=SUB=one;\n',
        encoding="utf-8",
    )

    values = parse_env_file(str(env_file))

    assert values["SCRAPFLY_KEY"] == "abc123"
    assert values["WEIBO_COOKIES"] == "SUB=one;"


# -- 关键词话术匹配 ---------------------------------------------------------
class TestGetTemplateByKeyword:
    def test_nail_learn_exact(self):
        from weibo_bot import config

        result = config.get_template_by_keyword("美甲培训")

        assert "美甲板块" in result
        assert "私信我获取门票" in result

    def test_nail_learn_substring(self):
        """采集词「上海美甲培训班」包含「美甲培训」，应命中美甲培训话术。"""
        from weibo_bot import config

        result = config.get_template_by_keyword("上海美甲培训班")

        assert "美甲板块" in result

    def test_pressnail(self):
        from weibo_bot import config

        result = config.get_template_by_keyword("穿戴甲")

        assert "穿戴甲" in result
        assert "私信我获取门票" in result

    def test_nail_franchise(self):
        from weibo_bot import config

        result = config.get_template_by_keyword("美甲店加盟")

        assert "连锁品牌" in result
        assert "私信我获取门票" in result

    def test_nail_accessories(self):
        """甲片/饰品/工具设备应命中美甲泛兴趣话术。"""
        from weibo_bot import config

        for keyword in ["甲片", "饰品", "工具设备"]:
            result = config.get_template_by_keyword(keyword)
            assert "私信我获取门票" in result, f"failed for keyword: {keyword}"

    def test_supply(self):
        from weibo_bot import config

        result = config.get_template_by_keyword("美睫进货")

        assert "供应商" in result or "品牌商" in result
        assert "私信我获取门票" in result

    def test_matches_comment_text_when_keyword_is_generic(self):
        from weibo_bot import config

        result = config.get_template_by_keyword("宠物展", "想开店的话加盟哪个品牌更稳")

        assert "加盟" in result
        assert "私信我获取门票" in result

    def test_open_shop(self):
        from weibo_bot import config

        result = config.get_template_by_keyword("开美甲店")

        assert "加盟" in result
        assert "私信我获取门票" in result

    def test_fallback(self):
        """无匹配关键词返回兜底话术。"""
        from weibo_bot import config

        result = config.get_template_by_keyword("完全不相关xyz")

        assert "私信我获取门票" in result
        assert len(result) > 15

from weibo_bot import dashboard, template_store


def build_logged_in_client():
    client = dashboard.app.test_client()
    client.post("/login", data={"username": "CIBE", "password": "cibe8888"})
    return client


def test_add_template_saves_locally_and_deduplicates(tmp_path):
    template_store.configure(str(tmp_path / "reply_templates.json"))

    first = template_store.add_template("hello template")
    second = template_store.add_template("hello template")

    assert first == second
    assert first.count("hello template") == 1
    assert template_store.load_templates().count("hello template") == 1


def test_add_template_rejects_blank(tmp_path):
    template_store.configure(str(tmp_path / "reply_templates.json"))

    try:
        template_store.add_template("   ")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("blank template was accepted")


def test_template_api_adds_and_returns_saved_template(tmp_path):
    template_store.configure(str(tmp_path / "reply_templates.json"))
    client = build_logged_in_client()

    response = client.post("/api/templates", json={"text": "new saved template"})

    assert response.status_code == 200
    assert "new saved template" in response.get_json()
    assert "new saved template" in client.get("/api/templates").get_json()


def test_dashboard_includes_custom_template_controls():
    client = build_logged_in_client()

    response = client.get("/")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="newTemplateText"' in html
    assert 'id="saveTemplateBtn"' in html
    assert "保存话术" in html

from sqlalchemy import inspect


def test_removed_content_tables_are_not_part_of_the_current_schema(db):
    tables = set(inspect(db.bind).get_table_names())

    assert "banners" not in tables
    assert "articles" not in tables
    assert "static_pages" in tables


def test_removed_content_routes_are_not_available(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    for path in ("/api/v1/banners", "/api/v1/articles", "/api/v1/admin/banners", "/api/v1/admin/articles", "/api/v1/admin/pages"):
        assert client.get(path, headers=headers).status_code == 404

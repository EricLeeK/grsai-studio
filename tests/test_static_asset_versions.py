import os
import re
import time

from fastapi.testclient import TestClient


def test_static_url_uses_file_mtime(monkeypatch, tmp_path):
    import app.templating as templating

    static_dir = tmp_path / "static"
    asset = static_dir / "js" / "app.js"
    asset.parent.mkdir(parents=True)
    asset.write_text("console.log('first');")
    timestamp = int(time.time()) - 30
    monkeypatch.setattr(templating, "STATIC_DIR", static_dir)
    monkeypatch.setattr(templating, "STATIC_DIR_RESOLVED", static_dir.resolve())
    monkeypatch.setattr(templating, "_STATIC_URL_CACHE", {})

    os.utime(asset, (timestamp, timestamp))

    assert templating.static_url("js/app.js") == f"/static/js/app.js?v={timestamp}"


def test_pages_use_automatic_static_versions():
    from app.main import app

    client = TestClient(app)
    pages = {
        "/": ["css/style.css", "js/app.js"],
        "/apps": ["css/style.css"],
        "/comic": ["css/style.css", "css/comic.css", "js/comic.js"],
        "/publisher": ["css/publisher.css", "js/publisher.js"],
    }

    for path, assets in pages.items():
        response = client.get(path)

        assert response.status_code == 200
        html = response.text
        assert "{{ static_url" not in html
        assert re.search(r"/static/img/favicon\.svg\?v=\d+", html)
        for asset in assets:
            assert re.search(rf"/static/{re.escape(asset)}\?v=\d+", html)

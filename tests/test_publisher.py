from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def test_converter_posts_markdown_to_gemini_and_extracts_html():
    from app.services.converter import convert_markdown_to_wechat_html

    calls = []

    def fake_post_json(url, payload, headers, timeout):
        calls.append((url, payload, headers, timeout))
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "```html\n<section style=\"color:#111\"><h1>Title</h1></section>\n```"
                            }
                        ]
                    }
                }
            ]
        }

    html = convert_markdown_to_wechat_html(
        "# Title",
        style="tech",
        api_key="gemini-key",
        base_url="https://example.test/v1beta",
        model="gemini-test",
        post_json=fake_post_json,
    )

    assert html == '<section style="color:#111"><h1>Title</h1></section>'
    url, payload, headers, timeout = calls[0]
    assert url == "https://example.test/v1beta/models/gemini-test:generateContent"
    assert headers["x-goog-api-key"] == "gemini-key"
    prompt = payload["contents"][0]["parts"][0]["text"]
    assert "# Title" in prompt
    assert "科技" in prompt
    assert "不得摘要" in prompt
    assert "不得删减" in prompt
    assert "原文每一句" in prompt
    assert "主题色" in prompt
    assert "十六进制颜色" in prompt
    assert "不要使用 rgba" in prompt
    assert "background-color" in prompt
    assert payload["generationConfig"]["maxOutputTokens"] == 65536
    assert timeout == 60


def test_converter_reports_when_gemini_hits_output_limit():
    from app.services.converter import ConverterError, convert_markdown_to_wechat_html

    def fake_post_json(url, payload, headers, timeout):
        return {
            "candidates": [
                {
                    "finishReason": "MAX_TOKENS",
                    "content": {"parts": [{"text": "<section>partial"}]},
                }
            ]
        }

    try:
        convert_markdown_to_wechat_html(
            "# Long article",
            api_key="gemini-key",
            post_json=fake_post_json,
        )
    except ConverterError as exc:
        assert "output token limit" in str(exc)
    else:
        raise AssertionError("Expected ConverterError")


def test_wechat_client_caches_token_and_creates_draft_payload(tmp_path):
    from app.services.wechat import WeChatClient

    requests = []

    def fake_get_json(url, params, timeout):
        requests.append(("get", url, params, timeout))
        return {"access_token": "token-1", "expires_in": 7200}

    def fake_post_json(url, payload, params, timeout):
        requests.append(("post", url, payload, params, timeout))
        return {"media_id": "draft-media"}

    client = WeChatClient(
        appid="appid",
        secret="secret",
        get_json=fake_get_json,
        post_json=fake_post_json,
        now=lambda: 1000,
    )

    assert client.get_access_token() == "token-1"
    assert client.get_access_token() == "token-1"
    draft_id = client.create_draft(
        title="Article",
        content_html="<section>Body</section>",
        cover_media_id="cover-media",
        author="GRSai",
        digest="Digest",
    )

    assert draft_id == "draft-media"
    assert [req[0] for req in requests].count("get") == 1
    post_request = requests[-1]
    assert post_request[1].endswith("/cgi-bin/draft/add")
    assert post_request[3]["access_token"] == "token-1"
    article = post_request[2]["articles"][0]
    assert article["title"] == "Article"
    assert article["thumb_media_id"] == "cover-media"
    assert article["content"] == "<section>Body</section>"
    assert article["need_open_comment"] == 0


def test_wechat_upload_image_uses_media_endpoint(tmp_path):
    from app.services.wechat import WeChatClient

    image = tmp_path / "cover.png"
    image.write_bytes(b"fake-png")
    calls = []

    def fake_get_json(url, params, timeout):
        return {"access_token": "token-1", "expires_in": 7200}

    def fake_post_file(url, file_path, params, timeout):
        calls.append((url, file_path, params, timeout))
        return {"media_id": "cover-media"}

    client = WeChatClient(
        appid="appid",
        secret="secret",
        get_json=fake_get_json,
        post_file=fake_post_file,
    )

    assert client.upload_image(image) == "cover-media"
    url, file_path, params, timeout = calls[0]
    assert url.endswith("/cgi-bin/material/add_material")
    assert file_path == image
    assert params == {"access_token": "token-1", "type": "image"}
    assert timeout == 90


def test_publisher_routes_convert_and_render(monkeypatch):
    import app.routers.publisher as publisher
    from app.main import app

    monkeypatch.setattr(
        publisher,
        "convert_markdown_to_wechat_html",
        lambda markdown, style="minimal": f"<section>{style}:{markdown}</section>",
    )

    client = TestClient(app)

    page = client.get("/publisher")
    assert page.status_code == 200
    assert "WeChat Publisher" in page.text

    response = client.post(
        "/api/publisher/convert",
        json={"markdown": "# Hello", "style": "business"},
    )
    assert response.status_code == 200
    assert response.json() == {"html": "<section>business:# Hello</section>"}


def test_publisher_cover_generation_creates_visible_task(monkeypatch):
    import app.routers.publisher as publisher
    from app.database import Base, get_db
    from app.main import app
    from app.models import Task

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    submitted = []

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(publisher, "submit_task", lambda task_id: submitted.append(task_id))
    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/publisher/generate-cover-task",
            json={
                "prompt": "A clean editorial cover",
                "model": "gpt-image-2-vip",
                "size": "2048x1152",
                "quality": "high",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["prompt"] == "A clean editorial cover"
        assert data["params"]["publisher_cover"] is True
        assert submitted == [data["id"]]

        db = TestingSession()
        try:
            task = db.query(Task).filter(Task.id == data["id"]).one()
            assert task.params["publisher_cover"] is True
        finally:
            db.close()
    finally:
        app.dependency_overrides.clear()


def test_publisher_upload_cover_from_finished_task(monkeypatch, tmp_path):
    import app.routers.publisher as publisher
    from app.database import Base, get_db
    from app.main import app
    from app.models import GeneratedImage, Task

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"fake-image")

    db = TestingSession()
    task = Task(
        status="succeeded",
        prompt="cover",
        model="gpt-image-2-vip",
        params={"publisher_cover": True},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    db.add(GeneratedImage(task_id=task.id, image_path=str(cover)))
    db.commit()
    task_id = task.id
    db.close()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    class FakeWeChatClient:
        def upload_image(self, file_path):
            assert Path(file_path) == cover
            return "cover-media-id"

    monkeypatch.setattr(publisher, "WeChatClient", FakeWeChatClient)
    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/publisher/upload-cover-from-task",
            json={"task_id": task_id},
        )
        assert response.status_code == 200
        assert response.json() == {"media_id": "cover-media-id", "image_path": str(cover)}
    finally:
        app.dependency_overrides.clear()

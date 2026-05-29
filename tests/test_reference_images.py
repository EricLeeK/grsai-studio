from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def make_test_client(monkeypatch):
    import app.routers.tasks as tasks
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(tasks, "submit_task", lambda task_id: None)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), app, TestingSession


def test_reference_image_upload_lists_and_deletes_persisted_file(monkeypatch, tmp_path):
    import app.routers.reference_images as reference_images

    monkeypatch.setattr(reference_images, "REFERENCE_IMAGE_DIR", tmp_path)
    client, app, _ = make_test_client(monkeypatch)

    try:
        response = client.post(
            "/api/reference-images",
            files={"image": ("brand.png", b"fake-png", "image/png")},
        )

        assert response.status_code == 201
        item = response.json()
        assert item["original_filename"] == "brand.png"
        assert item["image_url"].startswith("/reference-images/")
        assert (tmp_path / item["stored_filename"]).exists()

        list_response = client.get("/api/reference-images")
        assert list_response.status_code == 200
        assert [img["id"] for img in list_response.json()] == [item["id"]]

        delete_response = client.delete(f"/api/reference-images/{item['id']}")
        assert delete_response.status_code == 204
        assert not (tmp_path / item["stored_filename"]).exists()
        assert client.get("/api/reference-images").json() == []
    finally:
        app.dependency_overrides.clear()


def test_task_creation_uses_selected_reference_library_images(monkeypatch, tmp_path):
    import app.routers.reference_images as reference_images
    from app.models import Task

    monkeypatch.setattr(reference_images, "REFERENCE_IMAGE_DIR", tmp_path)
    client, app, TestingSession = make_test_client(monkeypatch)

    try:
        upload_response = client.post(
            "/api/reference-images",
            files={"image": ("ip.png", b"fake-png", "image/png")},
        )
        ref_id = upload_response.json()["id"]

        response = client.post(
            "/api/tasks",
            json={
                "prompt": "Use my brand IP",
                "model": "gpt-image-2-vip",
                "reference_image_ids": [ref_id],
            },
        )

        assert response.status_code == 201
        task = response.json()
        assert len(task["params"]["ref_image_paths"]) == 1
        assert task["params"]["ref_image_paths"][0].startswith(str(tmp_path))

        db = TestingSession()
        try:
            stored = db.query(Task).filter(Task.id == task["id"]).one()
            assert stored.params["reference_image_ids"] == [ref_id]
        finally:
            db.close()
    finally:
        app.dependency_overrides.clear()


def test_task_upload_keeps_reused_reference_paths(monkeypatch, tmp_path):
    from app.models import Task

    client, app, TestingSession = make_test_client(monkeypatch)
    reused = tmp_path / "old-reference.png"
    reused.write_bytes(b"old-image")

    try:
        response = client.post(
            "/api/tasks/upload",
            data={
                "prompt": "Same style again",
                "model": "gpt-image-2-vip",
                "ref_image_paths": str(reused),
            },
        )

        assert response.status_code == 201
        task = response.json()
        assert task["params"]["ref_image_paths"] == [str(reused)]

        db = TestingSession()
        try:
            stored = db.query(Task).filter(Task.id == task["id"]).one()
            assert stored.params["ref_image_paths"] == [str(reused)]
        finally:
            db.close()
    finally:
        app.dependency_overrides.clear()


def test_uploaded_task_reference_files_are_saved_persistently(monkeypatch, tmp_path):
    import app.routers.tasks as tasks_router

    monkeypatch.setattr(tasks_router, "TASK_REFERENCE_DIR", tmp_path)
    client, app, _ = make_test_client(monkeypatch)

    try:
        response = client.post(
            "/api/tasks/upload",
            data={"prompt": "With pasted reference", "model": "gpt-image-2-vip"},
            files={"ref_images": ("paste.png", b"fake-png", "image/png")},
        )

        assert response.status_code == 201
        task = response.json()
        [saved_path] = task["params"]["ref_image_paths"]
        assert saved_path.startswith(str(tmp_path))
        assert "paste.png" in saved_path
        assert not saved_path.startswith("/var/")
    finally:
        app.dependency_overrides.clear()

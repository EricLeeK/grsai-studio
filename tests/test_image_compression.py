from pathlib import Path

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


def test_compress_generated_image_creates_new_image_for_same_task(monkeypatch, tmp_path):
    import app.routers.tasks as tasks_router
    from app.models import GeneratedImage, Task

    source = tmp_path / "source.png"
    source.write_bytes(b"source-image")

    def fake_compress(image_path: Path, quality: int = 75) -> Path:
        assert image_path == source
        assert quality == 75
        output = tmp_path / "source.compressed-q75-abcd1234.jpg"
        output.write_bytes(b"compressed-image")
        return output

    monkeypatch.setattr(tasks_router, "compress_image", fake_compress)
    client, app, TestingSession = make_test_client(monkeypatch)

    db = TestingSession()
    try:
        task = Task(status="succeeded", prompt="compress me", model="gpt-image-2-vip")
        db.add(task)
        db.commit()
        db.refresh(task)
        image = GeneratedImage(task_id=task.id, image_path=str(source))
        db.add(image)
        db.commit()
        db.refresh(image)
        image_id = image.id
        task_id = task.id
    finally:
        db.close()

    try:
        response = client.post(f"/api/tasks/images/{image_id}/compress")

        assert response.status_code == 201
        compressed = response.json()
        assert compressed["task_id"] == task_id
        assert compressed["image_path"].endswith(".compressed-q75-abcd1234.jpg")
        assert client.get(f"/api/tasks/{task_id}").json()["images"][-1]["id"] == compressed["id"]
    finally:
        app.dependency_overrides.clear()

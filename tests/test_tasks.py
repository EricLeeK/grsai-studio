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


def test_delete_failed_tasks_removes_only_failed_tasks_and_files(monkeypatch, tmp_path):
    import app.config as config
    import app.routers.tasks as tasks_router
    from app.models import GeneratedImage, Task

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    client, app, TestingSession = make_test_client(monkeypatch)

    failed_image = tmp_path / "failed.png"
    succeeded_image = tmp_path / "succeeded.png"
    failed_image.write_bytes(b"failed")
    succeeded_image.write_bytes(b"succeeded")

    db = TestingSession()
    try:
        failed = Task(status="failed", prompt="bad", model="gpt-image-2-vip")
        succeeded = Task(status="succeeded", prompt="good", model="gpt-image-2-vip")
        running = Task(status="running", prompt="busy", model="gpt-image-2-vip")
        db.add_all([failed, succeeded, running])
        db.commit()
        db.refresh(failed)
        db.refresh(succeeded)
        db.add_all(
            [
                GeneratedImage(task_id=failed.id, image_path=str(failed_image)),
                GeneratedImage(task_id=succeeded.id, image_path=str(succeeded_image)),
            ]
        )
        db.commit()
        failed_id = failed.id
        succeeded_id = succeeded.id
        running_id = running.id
    finally:
        db.close()

    failed_output = config.OUTPUT_DIR / str(failed_id)
    succeeded_output = config.OUTPUT_DIR / str(succeeded_id)
    failed_output.mkdir(parents=True)
    succeeded_output.mkdir(parents=True)

    try:
        response = client.delete("/api/tasks/failed")

        assert response.status_code == 200
        assert response.json() == {"deleted": 1}
        assert not failed_image.exists()
        assert not failed_output.exists()
        assert succeeded_image.exists()
        assert succeeded_output.exists()

        remaining = {task["id"]: task["status"] for task in client.get("/api/tasks").json()}
        assert remaining == {succeeded_id: "succeeded", running_id: "running"}
    finally:
        app.dependency_overrides.clear()


def test_list_tasks_is_paginated_and_ordered(monkeypatch):
    from app.models import Task

    client, app, TestingSession = make_test_client(monkeypatch)
    db = TestingSession()
    try:
        for i in range(65):
            db.add(Task(status="succeeded", prompt=f"task {i}", model="gpt-image-2-vip"))
        db.commit()
    finally:
        db.close()

    try:
        first_page = client.get("/api/tasks").json()
        second_page = client.get("/api/tasks?limit=20&offset=50").json()

        assert len(first_page) == 50
        assert first_page[0]["prompt"] == "task 64"
        assert first_page[-1]["prompt"] == "task 15"
        assert [task["prompt"] for task in second_page] == [f"task {i}" for i in range(14, -1, -1)]
    finally:
        app.dependency_overrides.clear()


def test_list_tasks_filters_by_status(monkeypatch):
    from app.models import Task

    client, app, TestingSession = make_test_client(monkeypatch)
    db = TestingSession()
    try:
        db.add_all(
            [
                Task(status="succeeded", prompt="done", model="gpt-image-2-vip"),
                Task(status="pending", prompt="queued", model="gpt-image-2-vip"),
                Task(status="running", prompt="busy", model="gpt-image-2-vip"),
            ]
        )
        db.commit()
    finally:
        db.close()

    try:
        active = client.get("/api/tasks?status=pending&status=running").json()

        assert [task["status"] for task in active] == ["running", "pending"]
        assert [task["prompt"] for task in active] == ["busy", "queued"]
    finally:
        app.dependency_overrides.clear()

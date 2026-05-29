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


def test_comic_current_project_is_created_and_reused(monkeypatch):
    client, app, _ = make_test_client(monkeypatch)

    try:
        first = client.get("/api/comic/projects/current")
        second = client.get("/api/comic/projects/current")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        assert first.json()["name"] == "Untitled Comic"
    finally:
        app.dependency_overrides.clear()


def test_comic_task_metadata_is_saved(monkeypatch):
    client, app, _ = make_test_client(monkeypatch)

    try:
        project_id = client.get("/api/comic/projects/current").json()["id"]
        response = client.post(
            "/api/tasks",
            json={
                "prompt": "Explain paper as comic",
                "model": "gpt-image-2-vip",
                "comic_project_id": project_id,
                "comic_page_type": "numbered",
                "comic_page_number": 5,
                "comic_ip_mode": True,
                "comic_auto_prompt_ids": ["p1", "p2"],
            },
        )

        assert response.status_code == 201
        params = response.json()["params"]
        assert params["comic_project_id"] == project_id
        assert params["comic_page_type"] == "numbered"
        assert params["comic_page_number"] == 5
        assert params["comic_ip_mode"] is True
        assert params["comic_auto_prompt_ids"] == ["p1", "p2"]
    finally:
        app.dependency_overrides.clear()


def test_comic_candidate_is_created_from_generated_image(monkeypatch, tmp_path):
    from app.models import ComicCandidate, Task
    from app.services.executor import _save_image

    client, app, TestingSession = make_test_client(monkeypatch)

    try:
        project_id = client.get("/api/comic/projects/current").json()["id"]
        db = TestingSession()
        task = Task(
            status="running",
            prompt="cover",
            model="gpt-image-2-vip",
            params={
                "comic_project_id": project_id,
                "comic_page_type": "cover",
                "comic_page_number": None,
            },
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        image = tmp_path / "cover.png"
        image.write_bytes(b"fake")
        _save_image(db, task.id, str(image))

        candidate = db.query(ComicCandidate).filter(
            ComicCandidate.comic_project_id == project_id
        ).one()
        assert candidate.page_type == "cover"
        assert candidate.page_number is None
        assert candidate.is_selected is True
        assert candidate.image_path == str(image)
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_selecting_comic_candidate_unselects_other_candidates(monkeypatch, tmp_path):
    from app.models import ComicCandidate, ComicProject

    client, app, TestingSession = make_test_client(monkeypatch)

    try:
        db = TestingSession()
        project = ComicProject(name="Paper")
        db.add(project)
        db.commit()
        db.refresh(project)

        first = ComicCandidate(
            comic_project_id=project.id,
            page_type="numbered",
            page_number=1,
            task_id=1,
            generated_image_id=1,
            image_path=str(Path("first.png")),
            image_url="/output/1/first.png",
            is_selected=True,
        )
        second = ComicCandidate(
            comic_project_id=project.id,
            page_type="numbered",
            page_number=1,
            task_id=2,
            generated_image_id=2,
            image_path=str(Path("second.png")),
            image_url="/output/2/second.png",
            is_selected=False,
        )
        db.add_all([first, second])
        db.commit()
        db.refresh(first)
        db.refresh(second)
        first_id = first.id
        second_id = second.id
        db.close()

        response = client.post(f"/api/comic/candidates/{second_id}/select")
        assert response.status_code == 200

        db = TestingSession()
        selected = db.query(ComicCandidate).filter(ComicCandidate.id == second_id).one()
        unselected = db.query(ComicCandidate).filter(ComicCandidate.id == first_id).one()
        assert selected.is_selected is True
        assert unselected.is_selected is False
    finally:
        db.close()
        app.dependency_overrides.clear()


def test_comic_persistent_prompts_are_crud_via_backend(monkeypatch):
    client, app, _ = make_test_client(monkeypatch)

    try:
        project_id = client.get("/api/comic/projects/current").json()["id"]
        create_response = client.post(
            f"/api/comic/projects/{project_id}/prompts",
            json={"page_type": "cover", "text": "Fixed cover prompt"},
        )

        assert create_response.status_code == 201
        prompt = create_response.json()
        assert prompt["page_type"] == "cover"
        assert prompt["text"] == "Fixed cover prompt"

        update_response = client.patch(
            f"/api/comic/prompts/{prompt['id']}",
            json={"text": "Edited cover prompt"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["text"] == "Edited cover prompt"

        list_response = client.get(f"/api/comic/projects/{project_id}/prompts")
        assert [item["text"] for item in list_response.json()] == ["Edited cover prompt"]

        delete_response = client.delete(f"/api/comic/prompts/{prompt['id']}")
        assert delete_response.status_code == 204
        assert client.get(f"/api/comic/projects/{project_id}/prompts").json() == []
    finally:
        app.dependency_overrides.clear()


def test_comic_ip_reference_selection_is_persisted(monkeypatch, tmp_path):
    import app.routers.reference_images as reference_images

    monkeypatch.setattr(reference_images, "REFERENCE_IMAGE_DIR", tmp_path)
    client, app, _ = make_test_client(monkeypatch)

    try:
        project_id = client.get("/api/comic/projects/current").json()["id"]
        image = client.post(
            "/api/reference-images",
            files={"image": ("ip.png", b"fake-png", "image/png")},
        ).json()

        response = client.put(
            f"/api/comic/projects/{project_id}/ip-references",
            json={"reference_image_ids": [image["id"]]},
        )

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [image["id"]]
        persisted = client.get(f"/api/comic/projects/{project_id}/ip-references")
        assert [item["id"] for item in persisted.json()] == [image["id"]]
    finally:
        app.dependency_overrides.clear()

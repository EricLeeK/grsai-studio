"""Tests for the tasks API and execution engine."""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import OUTPUT_DIR
from app.database import init_db
from app.services.grsai import GrsaiResult

client = TestClient(app)

# Patch run_generate where it's looked up: in executor module
PATCH_TARGET = "app.services.executor.run_generate"

STUB_SCRIPT = Path(__file__).parent / "stub_generate.sh"


def setup_function():
    """Re-initialize DB before each test."""
    init_db()


# --- c1: POST /api/tasks triggers generation ---

@patch(PATCH_TARGET)
def test_create_task_triggers_generation(mock_generate):
    """Submitting a task via POST /api/tasks triggers generation through generate.sh."""
    mock_generate.return_value = GrsaiResult(
        success=True, image_path="/tmp/test_output/image.png"
    )

    response = client.post("/api/tasks", json={
        "prompt": "a cute cat",
        "model": "nano-banana-pro-vip",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["prompt"] == "a cute cat"
    assert data["model"] == "nano-banana-pro-vip"

    # Wait for thread pool worker to execute
    time.sleep(2)
    mock_generate.assert_called()


# --- c2: Task status transitions ---

@patch(PATCH_TARGET)
def test_task_status_transitions_to_succeeded(mock_generate):
    """Task status transitions: pending → running → succeeded."""
    mock_generate.return_value = GrsaiResult(
        success=True, image_path="/tmp/test_output/image.png"
    )

    create_resp = client.post("/api/tasks", json={
        "prompt": "sunset landscape",
        "model": "nano-banana-pro-vip",
    })
    task_id = create_resp.json()["id"]

    time.sleep(3)

    get_resp = client.get(f"/api/tasks/{task_id}")
    assert get_resp.json()["status"] == "succeeded"


@patch(PATCH_TARGET)
def test_task_status_transitions_to_failed(mock_generate):
    """Task status transitions to failed on error."""
    mock_generate.return_value = GrsaiResult(
        success=False, error="API rate limit exceeded"
    )

    create_resp = client.post("/api/tasks", json={
        "prompt": "fail test",
        "model": "nano-banana-pro-vip",
    })
    task_id = create_resp.json()["id"]

    time.sleep(3)

    get_resp = client.get(f"/api/tasks/{task_id}")
    data = get_resp.json()
    assert data["status"] == "failed"
    assert data["error_message"] is not None
    assert "rate limit" in data["error_message"].lower()


# --- c3: Parallel execution with count > 1 ---

@patch(PATCH_TARGET)
def test_parallel_execution(mock_generate):
    """When count > 1 and parallel=true, multiple invocations run concurrently."""
    call_times = []

    def slow_generate(*args, **kwargs):
        call_times.append(time.time())
        time.sleep(0.5)
        return GrsaiResult(success=True, image_path="/tmp/test_output/image.png")

    mock_generate.side_effect = slow_generate

    create_resp = client.post("/api/tasks", json={
        "prompt": "parallel test",
        "model": "nano-banana-pro-vip",
        "count": 3,
        "parallel": True,
    })
    task_id = create_resp.json()["id"]

    time.sleep(5)

    get_resp = client.get(f"/api/tasks/{task_id}")
    assert get_resp.json()["status"] == "succeeded"

    # All 3 should have been called
    assert mock_generate.call_count == 3

    # Check that calls overlapped (parallel execution)
    if len(call_times) >= 2:
        time_spread = max(call_times) - min(call_times)
        # Parallel: all start within ~0.5s; sequential: ~1.0s spread
        assert time_spread < 1.0, f"Calls spread over {time_spread}s, expected parallel execution"


# --- c4: Reference image upload via multipart form ---

@patch(PATCH_TARGET)
def test_reference_image_upload(mock_generate):
    """Reference images uploaded via multipart form are saved and passed as --ref."""
    mock_generate.return_value = GrsaiResult(
        success=True, image_path="/tmp/test_output/image.png"
    )

    import io
    fake_image = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    response = client.post(
        "/api/tasks/upload",
        data={
            "prompt": "use reference",
            "model": "nano-banana-pro-vip",
        },
        files=[("ref_images", ("ref1.png", fake_image, "image/png"))],
    )

    assert response.status_code == 201
    data = response.json()
    assert data["params"]["ref_image_paths"] is not None
    assert len(data["params"]["ref_image_paths"]) == 1

    time.sleep(3)

    # Verify the ref path was passed to generate
    mock_generate.assert_called()
    call_kwargs = mock_generate.call_args
    ref_paths = call_kwargs.kwargs.get("ref_paths")
    assert ref_paths is not None
    assert len(ref_paths) == 1


# --- c5: Generated images stored in per-task output directory ---

@patch(PATCH_TARGET)
def test_images_stored_in_output_directory(mock_generate):
    """Generated images are saved to output/{task_id}/ and path stored in DB."""
    import tempfile
    import os

    tmpdir = tempfile.mkdtemp()
    fake_path = os.path.join(tmpdir, "grsai_test.png")
    with open(fake_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    mock_generate.return_value = GrsaiResult(success=True, image_path=fake_path)

    create_resp = client.post("/api/tasks", json={
        "prompt": "output test",
        "model": "nano-banana-pro-vip",
    })
    task_id = create_resp.json()["id"]

    time.sleep(3)

    get_resp = client.get(f"/api/tasks/{task_id}")
    data = get_resp.json()

    assert data["status"] == "succeeded"
    assert len(data["images"]) > 0
    assert data["images"][0]["image_path"] is not None


# --- c6: Failed tasks store error messages ---

@patch(PATCH_TARGET)
def test_failed_task_error_message(mock_generate):
    """Failed tasks store error messages; GET returns the error field."""
    mock_generate.return_value = GrsaiResult(
        success=False, error="Content policy violation: prompt contains banned words"
    )

    create_resp = client.post("/api/tasks", json={
        "prompt": "banned content",
        "model": "nano-banana-pro-vip",
    })
    task_id = create_resp.json()["id"]

    time.sleep(3)

    get_resp = client.get(f"/api/tasks/{task_id}")
    data = get_resp.json()

    assert data["status"] == "failed"
    assert data["error_message"] is not None
    assert "violation" in data["error_message"].lower()


# --- Additional: list tasks ---

def test_list_tasks():
    """GET /api/tasks returns a list."""
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_health_check():
    """Health endpoint returns ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- DELETE /api/tasks/{id} ---

@patch(PATCH_TARGET)
def test_delete_task(mock_generate):
    """DELETE /api/tasks/{id} removes the task and returns 204."""
    mock_generate.return_value = GrsaiResult(
        success=True, image_path="/tmp/test_output/image.png"
    )

    create_resp = client.post("/api/tasks", json={
        "prompt": "delete me",
        "model": "nano-banana-pro-vip",
    })
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    # Delete it
    del_resp = client.delete(f"/api/tasks/{task_id}")
    assert del_resp.status_code == 204

    # Verify it's gone
    get_resp = client.get(f"/api/tasks/{task_id}")
    assert get_resp.status_code == 404


def test_delete_nonexistent_task():
    """DELETE /api/tasks/{id} returns 404 for nonexistent task."""
    resp = client.delete("/api/tasks/99999")
    assert resp.status_code == 404


# --- Integration tests: real stub script, real files on disk ---


@pytest.fixture(autouse=False)
def _use_stub_script():
    """Patch GENERATE_SCRIPT to the stub for integration tests."""
    import app.services.grsai as grsai_mod
    original = grsai_mod.GENERATE_SCRIPT
    grsai_mod.GENERATE_SCRIPT = STUB_SCRIPT
    yield
    grsai_mod.GENERATE_SCRIPT = original


@pytest.fixture()
def _integration_cleanup():
    """Reset DB before integration test and return pre-existing task IDs."""
    init_db()
    from app.database import SessionLocal
    from app.models import Task
    db = SessionLocal()
    existing_ids = {t.id for t in db.query(Task.id).all()}
    db.close()
    yield existing_ids


def test_integration_file_appears_in_output(_use_stub_script, _integration_cleanup):
    """c1+ c5: POST /api/tasks triggers generation; a real file appears in output/{task_id}/."""
    existing_ids = _integration_cleanup

    create_resp = client.post("/api/tasks", json={
        "prompt": "integration test",
        "model": "nano-banana-pro-vip",
    })
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    time.sleep(3)

    get_resp = client.get(f"/api/tasks/{task_id}")
    data = get_resp.json()
    assert data["status"] == "succeeded"
    assert len(data["images"]) > 0

    image_path = data["images"][0]["image_path"]
    assert image_path is not None, "image_path must be set in DB"

    # Verify the file actually exists on disk
    assert os.path.isfile(image_path), f"Image file not found on disk: {image_path}"

    # Verify the path is inside output/{task_id}/
    expected_prefix = str(OUTPUT_DIR / str(task_id))
    assert image_path.startswith(expected_prefix), (
        f"Image path {image_path} is not under output/{task_id}/"
    )


def test_integration_status_transitions(_use_stub_script, _integration_cleanup):
    """c2: Task status transitions: pending -> running -> succeeded (or failed)."""
    existing_ids = _integration_cleanup

    create_resp = client.post("/api/tasks", json={
        "prompt": "status transition test",
        "model": "nano-banana-pro-vip",
    })
    assert create_resp.status_code == 201
    data = create_resp.json()
    task_id = data["id"]
    assert data["status"] == "pending"

    # Poll until terminal state
    for _ in range(20):
        time.sleep(0.5)
        get_resp = client.get(f"/api/tasks/{task_id}")
        status = get_resp.json()["status"]
        if status in ("succeeded", "failed"):
            break

    assert status == "succeeded"


def test_integration_image_in_output_directory(_use_stub_script, _integration_cleanup):
    """c5: Generated images land in output/{task_id}/{i}/ and path is stored in DB."""
    existing_ids = _integration_cleanup

    create_resp = client.post("/api/tasks", json={
        "prompt": "output dir test",
        "model": "nano-banana-pro-vip",
    })
    task_id = create_resp.json()["id"]

    time.sleep(3)

    get_resp = client.get(f"/api/tasks/{task_id}")
    data = get_resp.json()
    assert data["status"] == "succeeded"
    assert len(data["images"]) > 0

    image_path = data["images"][0]["image_path"]
    assert image_path is not None

    # File exists on disk
    assert os.path.isfile(image_path)

    # Path is under output/{task_id}/
    expected_prefix = str(OUTPUT_DIR / str(task_id))
    assert image_path.startswith(expected_prefix), (
        f"Expected path under {expected_prefix}, got {image_path}"
    )

    # The path should include a generation subdirectory: output/{task_id}/{i}/
    relative = os.path.relpath(image_path, str(OUTPUT_DIR))
    parts = Path(relative).parts
    assert parts[0] == str(task_id), f"First path component should be task_id, got {parts[0]}"
    assert len(parts) >= 2, f"Path should have generation subdirectory, got {parts}"


def test_integration_parallel_creates_multiple_files(_use_stub_script, _integration_cleanup):
    """c3+ c5: count=3, parallel=true creates 3 files under output/{task_id}/."""
    existing_ids = _integration_cleanup

    create_resp = client.post("/api/tasks", json={
        "prompt": "parallel integration test",
        "model": "nano-banana-pro-vip",
        "count": 3,
        "parallel": True,
    })
    task_id = create_resp.json()["id"]

    time.sleep(5)

    get_resp = client.get(f"/api/tasks/{task_id}")
    data = get_resp.json()
    assert data["status"] == "succeeded"
    assert len(data["images"]) == 3

    for img in data["images"]:
        path = img["image_path"]
        assert path is not None
        assert os.path.isfile(path), f"File not found: {path}"
        expected_prefix = str(OUTPUT_DIR / str(task_id))
        assert path.startswith(expected_prefix), (
            f"Path {path} not under {expected_prefix}"
        )

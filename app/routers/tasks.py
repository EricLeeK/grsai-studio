import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import TASK_REFERENCE_DIR
from app.database import get_db
from app.models import Task, GeneratedImage, ReferenceImage
from app.schemas import TaskCreate, TaskOut
from app.services.executor import submit_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _reference_image_paths(db: Session, image_ids: list[int] | None) -> list[str]:
    if not image_ids:
        return []
    images = db.query(ReferenceImage).filter(ReferenceImage.id.in_(image_ids)).all()
    found_ids = {img.id for img in images}
    missing_ids = [image_id for image_id in image_ids if image_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Reference image not found: {missing_ids[0]}",
        )
    by_id = {img.id: img.image_path for img in images}
    return [by_id[image_id] for image_id in image_ids]


@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    """Create a generation task and submit it to the executor."""
    selected_ref_paths = _reference_image_paths(db, body.reference_image_ids)
    ref_image_paths = (body.ref_image_paths or []) + selected_ref_paths
    params = {
        "ratio": body.ratio,
        "size": body.size,
        "quality": body.quality,
        "count": body.count,
        "parallel": body.parallel,
        "ref_image_paths": ref_image_paths or None,
        "reference_image_ids": body.reference_image_ids,
        "comic_project_id": body.comic_project_id,
        "comic_page_type": body.comic_page_type,
        "comic_page_number": body.comic_page_number,
        "comic_ip_mode": body.comic_ip_mode,
        "comic_auto_prompt_ids": body.comic_auto_prompt_ids,
    }
    task = Task(prompt=body.prompt, model=body.model, params=params, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)

    # Submit to thread pool for execution
    submit_task(task.id)

    return task


@router.post("/upload", response_model=TaskOut, status_code=201)
def create_task_with_upload(
    prompt: str = Form(...),
    model: str = Form(...),
    ratio: str = Form(None),
    size: str = Form(None),
    quality: str = Form(None),
    count: int = Form(1),
    parallel: bool = Form(False),
    reference_image_ids: list[int] = Form(default=[]),
    ref_image_paths: list[str] = Form(default=[]),
    comic_project_id: int | None = Form(None),
    comic_page_type: str | None = Form(None),
    comic_page_number: int | None = Form(None),
    comic_ip_mode: bool = Form(False),
    comic_auto_prompt_ids: list[str] = Form(default=[]),
    ref_images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    """Create a task with reference images uploaded via multipart form."""
    # Save uploaded reference images to a temp directory
    saved_ref_paths: list[str] = []
    if ref_images:
        ref_dir = TASK_REFERENCE_DIR / uuid.uuid4().hex
        ref_dir.mkdir(parents=True, exist_ok=True)
        for upload in ref_images:
            filename = Path(upload.filename or "reference.png").name
            dest = ref_dir / filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            saved_ref_paths.append(str(dest))
            logger.info("Saved reference image: %s", dest)

    selected_ref_paths = _reference_image_paths(db, reference_image_ids)
    all_ref_image_paths = ref_image_paths + selected_ref_paths + saved_ref_paths

    params = {
        "ratio": ratio,
        "size": size,
        "quality": quality,
        "count": count,
        "parallel": parallel,
        "ref_image_paths": all_ref_image_paths or None,
        "reference_image_ids": reference_image_ids or None,
        "comic_project_id": comic_project_id,
        "comic_page_type": comic_page_type,
        "comic_page_number": comic_page_number,
        "comic_ip_mode": comic_ip_mode,
        "comic_auto_prompt_ids": comic_auto_prompt_ids or None,
    }
    task = Task(prompt=prompt, model=model, params=params, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)

    submit_task(task.id)

    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(Task).order_by(Task.created_at.desc()).all()


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete image files from disk
    for img in (task.images or []):
        if img.image_path:
            p = Path(img.image_path)
            if p.exists():
                p.unlink()

    # Delete the output directory for this task
    from app.config import OUTPUT_DIR
    task_output = OUTPUT_DIR / str(task_id)
    if task_output.exists():
        shutil.rmtree(task_output, ignore_errors=True)

    # Delete from DB (cascade deletes images)
    db.delete(task)
    db.commit()
    return None

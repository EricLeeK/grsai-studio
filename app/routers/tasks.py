import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import TASK_REFERENCE_DIR
from app import config
from app.database import get_db
from app.models import Task, GeneratedImage, ReferenceImage
from app.schemas import ImageOut, TaskCreate, TaskOut
from app.services.executor import submit_task
from app.services.image_compression import ImageCompressionError, compress_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _delete_task_files(task: Task) -> None:
    """Remove generated files and the task output directory."""
    for img in (task.images or []):
        if img.image_path:
            p = Path(img.image_path)
            if p.exists():
                p.unlink()

    task_output = config.OUTPUT_DIR / str(task.id)
    if task_output.exists():
        shutil.rmtree(task_output, ignore_errors=True)


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
def list_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Task)
    if status:
        query = query.filter(Task.status.in_(status))
    return (
        query.order_by(Task.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/images/{image_id}/compress", response_model=ImageOut, status_code=201)
def compress_generated_image(image_id: int, db: Session = Depends(get_db)):
    image = db.query(GeneratedImage).filter(GeneratedImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not image.image_path:
        raise HTTPException(status_code=400, detail="Image path is empty")

    try:
        compressed_path = compress_image(Path(image.image_path), quality=75)
    except ImageCompressionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    compressed = GeneratedImage(task_id=image.task_id, image_path=str(compressed_path))
    db.add(compressed)
    db.commit()
    db.refresh(compressed)
    return compressed


@router.delete("/failed")
def delete_failed_tasks(db: Session = Depends(get_db)):
    failed_tasks = db.query(Task).filter(Task.status == "failed").all()
    deleted = len(failed_tasks)

    for task in failed_tasks:
        _delete_task_files(task)
        db.delete(task)

    db.commit()
    return {"deleted": deleted}


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    _delete_task_files(task)
    db.delete(task)
    db.commit()
    return None

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task, GeneratedImage
from app.schemas import TaskCreate, TaskOut
from app.services.executor import submit_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    """Create a generation task and submit it to the executor."""
    params = {
        "ratio": body.ratio,
        "size": body.size,
        "quality": body.quality,
        "count": body.count,
        "parallel": body.parallel,
        "ref_image_paths": body.ref_image_paths,
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
    ref_images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    """Create a task with reference images uploaded via multipart form."""
    # Save uploaded reference images to a temp directory
    saved_ref_paths: list[str] = []
    if ref_images:
        ref_dir = Path(tempfile.mkdtemp(prefix="grsai_ref_"))
        for upload in ref_images:
            dest = ref_dir / upload.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            saved_ref_paths.append(str(dest))
            logger.info("Saved reference image: %s", dest)

    params = {
        "ratio": ratio,
        "size": size,
        "quality": quality,
        "count": count,
        "parallel": parallel,
        "ref_image_paths": saved_ref_paths if saved_ref_paths else None,
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

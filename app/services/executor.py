"""Thread pool task executor for Grsai image generation."""

import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import OUTPUT_DIR
from app.database import SessionLocal
from app.models import GeneratedImage, Task
from app.services.grsai import run_generate

logger = logging.getLogger(__name__)

# Module-level executor – survives across requests
_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """Return the shared thread pool, creating it on first call."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="grsai")
    return _executor


def shutdown_executor(wait: bool = True) -> None:
    """Shut down the thread pool (called on app shutdown)."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None


def submit_task(task_id: int) -> None:
    """Submit a task for execution in the thread pool.

    Args:
        task_id: The database ID of the task to execute.
    """
    executor = get_executor()
    executor.submit(_execute_task, task_id)


def _execute_task(task_id: int) -> None:
    """Execute a task: run generate.sh, update DB with results.

    This runs in a worker thread, so it creates its own DB session.

    Args:
        task_id: The database ID of the task to execute.
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error("Task %d not found", task_id)
            return

        # Mark as running
        task.status = "running"
        db.commit()

        params = task.params or {}
        count = params.get("count", 1)
        parallel = params.get("parallel", False)
        ratio = params.get("ratio")
        size = params.get("size")
        quality = params.get("quality")
        ref_paths = params.get("ref_image_paths")

        # Create per-task output directory
        task_output_dir = OUTPUT_DIR / str(task_id)
        task_output_dir.mkdir(parents=True, exist_ok=True)

        if count > 1 and parallel:
            _execute_parallel(task, task_id, task_output_dir, count, db,
                              ratio, size, quality, ref_paths)
        else:
            _execute_sequential(task, task_id, task_output_dir, count, db,
                                ratio, size, quality, ref_paths)

    except Exception as e:
        logger.exception("Task %d failed with exception", task_id)
        _mark_failed(db, task_id, str(e))
    finally:
        db.close()


def _execute_sequential(
    task: Task,
    task_id: int,
    output_dir: Path,
    count: int,
    db: Session,
    ratio: str | None,
    size: str | None,
    quality: str | None,
    ref_paths: list[str] | None,
) -> None:
    """Execute count generations sequentially in the current thread."""
    success_count = 0
    last_error = None

    for i in range(count):
        # Each generation gets its own sub-output dir to avoid filename collisions
        gen_dir = output_dir / str(i)
        gen_dir.mkdir(parents=True, exist_ok=True)

        result = run_generate(
            prompt=task.prompt,
            model=task.model,
            output_dir=str(gen_dir),
            ratio=ratio,
            size=size,
            quality=quality,
            ref_paths=ref_paths,
        )

        if result.success and result.image_path:
            _save_image(db, task_id, result.image_path)
            success_count += 1
        else:
            last_error = result.error

    if success_count > 0:
        task.status = "succeeded"
        db.commit()
    else:
        _mark_failed(db, task_id, last_error or "All generations failed")


def _execute_parallel(
    task: Task,
    task_id: int,
    output_dir: Path,
    count: int,
    db: Session,
    ratio: str | None,
    size: str | None,
    quality: str | None,
    ref_paths: list[str] | None,
) -> None:
    """Execute count generations in parallel using sub-threads."""
    inner_executor = ThreadPoolExecutor(max_workers=count, thread_name_prefix=f"grsai-{task_id}")
    futures = {}

    for i in range(count):
        gen_dir = output_dir / str(i)
        gen_dir.mkdir(parents=True, exist_ok=True)

        future = inner_executor.submit(
            run_generate,
            prompt=task.prompt,
            model=task.model,
            output_dir=str(gen_dir),
            ratio=ratio,
            size=size,
            quality=quality,
            ref_paths=ref_paths,
        )
        futures[future] = i

    success_count = 0
    last_error = None

    for future in as_completed(futures):
        try:
            result = future.result()
            if result.success and result.image_path:
                _save_image(db, task_id, result.image_path)
                success_count += 1
            else:
                last_error = result.error
        except Exception as e:
            logger.exception("Sub-task %d/%d failed", task_id, futures[future])
            last_error = str(e)

    inner_executor.shutdown(wait=False)

    if success_count > 0:
        task.status = "succeeded"
        db.commit()
    else:
        _mark_failed(db, task_id, last_error or "All parallel generations failed")


def _save_image(db: Session, task_id: int, image_path: str) -> None:
    """Save a generated image record to the database."""
    img = GeneratedImage(task_id=task_id, image_path=image_path)
    db.add(img)
    db.commit()
    logger.info("Saved image for task %d: %s", task_id, image_path)


def _mark_failed(db: Session, task_id: int, error: str) -> None:
    """Mark a task as failed with an error message."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.status = "failed"
        task.error_message = error
        db.commit()
    logger.error("Task %d failed: %s", task_id, error)

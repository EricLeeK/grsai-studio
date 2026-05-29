"""Publisher page and API routes."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import Task
from app.schemas import TaskOut
from app.services.converter import ConverterError, convert_markdown_to_wechat_html
from app.services.grsai import generate_image_direct
from app.services.executor import submit_task
from app.services.wechat import WeChatClient, WeChatError

router = APIRouter(tags=["publisher"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
PUBLISHER_OUTPUT_DIR = config.OUTPUT_DIR / "publisher"


class ConvertRequest(BaseModel):
    markdown: str = Field(..., min_length=1)
    style: str = "minimal"


class ConvertResponse(BaseModel):
    html: str


class DraftRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content_html: str = Field(..., min_length=1)
    cover_media_id: str = Field(..., min_length=1)
    author: str = ""
    digest: str = ""


class DraftResponse(BaseModel):
    media_id: str
    draft_url: str


class CoverTaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = "gpt-image-2-vip"
    ratio: str | None = "16:9"
    size: str | None = "2048x1152"
    quality: str | None = "high"


class UploadCoverFromTaskRequest(BaseModel):
    task_id: int


@router.get("/publisher")
def serve_publisher():
    return FileResponse(TEMPLATES_DIR / "publisher.html")


@router.post("/api/publisher/convert", response_model=ConvertResponse)
def convert_markdown(body: ConvertRequest):
    try:
        html = convert_markdown_to_wechat_html(body.markdown, style=body.style)
        return ConvertResponse(html=html)
    except ConverterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/publisher/upload-cover")
def upload_cover(
    cover: UploadFile | None = File(default=None),
    prompt: str | None = Form(default=None),
    model: str = Form(default="gpt-image-2-vip"),
    ratio: str | None = Form(default="16:9"),
    size: str | None = Form(default="2048x1152"),
    quality: str | None = Form(default="high"),
):
    image_path: Path | None = None
    temp_dir: Path | None = None
    try:
        if cover and cover.filename:
            temp_dir = Path(tempfile.mkdtemp(prefix="publisher_cover_"))
            suffix = Path(cover.filename).suffix or ".png"
            image_path = temp_dir / f"cover{suffix}"
            with open(image_path, "wb") as file:
                shutil.copyfileobj(cover.file, file)
        elif prompt and prompt.strip():
            PUBLISHER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            result = generate_image_direct(
                prompt=prompt.strip(),
                model=model,
                output_dir=str(PUBLISHER_OUTPUT_DIR),
                ratio=ratio,
                size=size,
                quality=quality,
            )
            if not result.success or not result.image_path:
                raise HTTPException(status_code=400, detail=result.error or "Cover generation failed")
            image_path = Path(result.image_path)
        else:
            raise HTTPException(status_code=400, detail="Upload a cover file or provide a prompt")

        media_id = WeChatClient().upload_image(image_path)
        return {"media_id": media_id, "image_path": str(image_path)}
    except WeChatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/api/publisher/generate-cover-task", response_model=TaskOut, status_code=201)
def generate_cover_task(body: CoverTaskRequest, db: Session = Depends(get_db)):
    params = {
        "ratio": body.ratio,
        "size": body.size,
        "quality": body.quality,
        "count": 1,
        "parallel": False,
        "ref_image_paths": None,
        "publisher_cover": True,
    }
    task = Task(
        prompt=body.prompt.strip(),
        model=body.model,
        params=params,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    submit_task(task.id)
    return task


@router.post("/api/publisher/upload-cover-from-task")
def upload_cover_from_task(body: UploadCoverFromTaskRequest, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == body.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "succeeded":
        raise HTTPException(status_code=400, detail="Cover task has not succeeded yet")
    if not task.images:
        raise HTTPException(status_code=400, detail="Cover task has no generated image")

    image_path = task.images[0].image_path
    if not image_path:
        raise HTTPException(status_code=400, detail="Cover task image path is empty")

    try:
        media_id = WeChatClient().upload_image(Path(image_path))
        return {"media_id": media_id, "image_path": image_path}
    except WeChatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/publisher/draft", response_model=DraftResponse)
def create_draft(body: DraftRequest):
    try:
        media_id = WeChatClient().create_draft(
            title=body.title,
            content_html=body.content_html,
            cover_media_id=body.cover_media_id,
            author=body.author,
            digest=body.digest,
        )
        return DraftResponse(media_id=media_id, draft_url="https://mp.weixin.qq.com/")
    except WeChatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

import datetime
from typing import Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    prompt: str
    model: str
    ratio: Optional[str] = None
    size: Optional[str] = None
    quality: Optional[str] = None
    count: int = 1
    parallel: bool = False
    ref_image_paths: Optional[list[str]] = None


class ImageOut(BaseModel):
    id: int
    task_id: int
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    status: str
    prompt: str
    model: str
    params: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    images: list[ImageOut] = []

    model_config = {"from_attributes": True}

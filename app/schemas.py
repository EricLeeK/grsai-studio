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
    reference_image_ids: Optional[list[int]] = None
    comic_project_id: Optional[int] = None
    comic_page_type: Optional[str] = None
    comic_page_number: Optional[int] = None
    comic_ip_mode: bool = False
    comic_auto_prompt_ids: Optional[list[str]] = None


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


class ReferenceImageOut(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    image_path: str
    image_url: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ComicProjectCreate(BaseModel):
    name: str = "Untitled Comic"


class ComicProjectOut(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ComicCandidateOut(BaseModel):
    id: int
    comic_project_id: int
    page_type: str
    page_number: Optional[int] = None
    task_id: int
    generated_image_id: int
    image_path: str
    image_url: Optional[str] = None
    is_selected: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

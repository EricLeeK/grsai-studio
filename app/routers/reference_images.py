import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import REFERENCE_IMAGE_DIR
from app.database import get_db
from app.models import ReferenceImage
from app.schemas import ReferenceImageOut

router = APIRouter(prefix="/api/reference-images", tags=["reference-images"])

ALLOWED_EXTENSIONS = {
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}


def _safe_extension(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    return suffix


@router.get("", response_model=list[ReferenceImageOut])
def list_reference_images(db: Session = Depends(get_db)):
    return db.query(ReferenceImage).order_by(ReferenceImage.created_at.desc()).all()


@router.post("", response_model=ReferenceImageOut, status_code=201)
def upload_reference_image(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    suffix = _safe_extension(image.filename or "")
    REFERENCE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}{suffix}"
    dest = REFERENCE_IMAGE_DIR / stored_filename

    with open(dest, "wb") as f:
        shutil.copyfileobj(image.file, f)

    item = ReferenceImage(
        original_filename=image.filename or stored_filename,
        stored_filename=stored_filename,
        image_path=str(dest),
        image_url=f"/reference-images/{stored_filename}",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{image_id}", status_code=204)
def delete_reference_image(image_id: int, db: Session = Depends(get_db)):
    item = db.query(ReferenceImage).filter(ReferenceImage.id == image_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Reference image not found")

    path = Path(item.image_path)
    if path.exists():
        path.unlink()

    db.delete(item)
    db.commit()
    return None

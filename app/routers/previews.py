"""Small cached previews; full-resolution files remain untouched."""
import hashlib
import os
import tempfile
from pathlib import Path
from threading import BoundedSemaphore
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import GeneratedImage, ReferenceImage

router = APIRouter(prefix="/api/previews", tags=["previews"])
# Bound cold-cache decoding memory when a page requests many 4K images at once.
_decode_slots = BoundedSemaphore(2)


@router.get("/{kind}/{image_id}")
def preview(kind: Literal["generated", "reference"], image_id: int,
            request: Request, db: Session = Depends(get_db)):
    model = GeneratedImage if kind == "generated" else ReferenceImage
    row = db.get(model, image_id)
    if row is None or not row.image_path:
        raise HTTPException(404, "Image not found")
    source = Path(row.image_path)
    try:
        stat = source.stat()
    except OSError as exc:
        raise HTTPException(404, "Image file not found") from exc

    key = hashlib.sha256(
        f"v1:{source.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode()
    ).hexdigest()
    headers = {"ETag": f'"{key}"', "Cache-Control": "private, max-age=0, must-revalidate"}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    directory = config.DATA_DIR / "previews"
    target = directory / f"{key}.jpg"
    if not target.exists():
        with _decode_slots:
            if not target.exists():
                directory.mkdir(parents=True, exist_ok=True)
                temporary = None
                try:
                    with Image.open(source) as original:
                        original.draft("RGB", (320, 320))
                        image = ImageOps.exif_transpose(original)
                        image.thumbnail((320, 320), Image.Resampling.LANCZOS)
                        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                            rgba = image.convert("RGBA")
                            image = Image.new("RGB", rgba.size, "white")
                            image.paste(rgba, mask=rgba.getchannel("A"))
                        else:
                            image = image.convert("RGB")
                        with tempfile.NamedTemporaryFile(dir=directory, suffix=".jpg", delete=False) as file:
                            temporary = Path(file.name)
                        image.save(temporary, "JPEG", quality=75, optimize=True)
                        os.replace(temporary, target)
                except (OSError, ValueError, UnidentifiedImageError) as exc:
                    raise HTTPException(415, "Cannot create image preview") from exc
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
    return FileResponse(target, media_type="image/jpeg", headers=headers)

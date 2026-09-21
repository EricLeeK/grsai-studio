"""poster-studio integration.

poster-studio is a vendored Next.js + Fabric.js canvas editor that runs at root
on its own port (:8100, started by the launcher alongside FastAPI). This module
exposes:

* ``GET /studio``           -> redirect to the canvas (convenience entry).
* ``POST /api/poster/generate`` -> Grsai-backed image generation for the canvas.

The canvas reaches generation via poster-studio's "custom compatible provider"
(server-to-server), configured in ``poster-studio/.env.local`` to point here.
"""

import asyncio
import base64
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app import config
from app.services import grsai

logger = logging.getLogger(__name__)

router = APIRouter(tags=["poster"])


@router.get("/studio")
async def studio_redirect() -> RedirectResponse:
    """Convenience entry: ``/studio`` on FastAPI -> the canvas on :8100."""
    return RedirectResponse(url=config.POSTER_STUDIO_UPSTREAM, status_code=302)


# Image extensions surfaced in the GRS AI generated-image library.
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@router.get("/api/poster/library")
async def poster_library() -> dict:
    """List every generated image under ``output/``, newest first.

    The canvas image-picker fetches this to show the "GRS AI 已生图库" tab.
    URLs are absolute (``:8099/output/...``) and CORS-enabled so the canvas
    (on :8100) can load and export them.
    """
    output_root = config.OUTPUT_DIR.resolve()
    images: list[dict] = []
    for path in output_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _IMAGE_EXTS:
            continue
        try:
            rel = path.resolve().relative_to(output_root)
        except ValueError:
            continue
        stat = path.stat()
        rel_posix = rel.as_posix()
        images.append(
            {
                "id": rel_posix,
                "url": f"{config.POSTER_STUDIO_PUBLIC_ORIGIN}/output/{rel_posix}",
                "name": path.name,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "size": stat.st_size,
            }
        )
    images.sort(key=lambda item: item["created_at"], reverse=True)
    return {"images": images, "total": len(images)}


# --------------------------------------------------------------------------- #
# Grsai-backed image generation for the canvas.
#
# poster-studio calls this via its "custom compatible provider". It POSTs the
# seedream-format payload and expects an OpenAI-style response:
#   { "data": [{ "url": "..." }] }   (or b64_json)
# --------------------------------------------------------------------------- #


class PosterGenerateRequest(BaseModel):
    prompt: str
    model: str | None = None
    size: str | None = None
    image: str | list[str] | None = None


def _resolve_model(model: str | None) -> str:
    """Use the request model unless it is the placeholder, else the configured default."""
    if model and model.strip() and model.strip().lower() != "grsai":
        return model.strip()
    return config.POSTER_STUDIO_MODEL


def _data_url_to_file(data_url: str) -> str:
    """Persist a ``data:<mime>;base64,...`` URL to a temp file and return its path."""
    header, _, b64 = data_url.partition(",")
    ext = "png"
    if "image/jpeg" in header:
        ext = "jpg"
    elif "image/webp" in header:
        ext = "webp"
    dest = config.TASK_REFERENCE_DIR / f"poster_ref_{uuid.uuid4().hex}.{ext}"
    dest.write_bytes(base64.b64decode(b64))
    return str(dest)


def _collect_ref_paths(image: str | list[str] | None) -> list[str]:
    """Turn the request's ``image`` field into Grsai ref paths.

    Data URLs are saved to disk (Grsai reads ref images from file paths); http
    URLs are passed through (Grsai fetches them).
    """
    if not image:
        return []
    items = image if isinstance(image, list) else [image]
    paths: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item:
            continue
        if item.startswith("data:"):
            paths.append(_data_url_to_file(item))
        elif item.startswith("http"):
            paths.append(item)
    return paths


@router.post("/api/poster/generate")
async def poster_generate(body: PosterGenerateRequest) -> dict:
    """Generate an image via Grsai and return a URL the canvas can load.

    The URL points at FastAPI's ``/output`` mount. CORS is enabled for the
    canvas origin so Fabric can load it (``crossOrigin="anonymous"``) without
    tainting the canvas on export.
    """
    if not body.prompt or not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    model = _resolve_model(body.model)
    ref_paths = _collect_ref_paths(body.image)

    output_dir = config.OUTPUT_DIR / "poster"
    output_dir.mkdir(parents=True, exist_ok=True)

    # grsai.run_generate is blocking (urllib + subprocess); run off the loop.
    result = await asyncio.to_thread(
        grsai.run_generate,
        prompt=body.prompt,
        model=model,
        output_dir=str(output_dir),
        size=body.size,
        ratio=None,
        quality=None,
        ref_paths=ref_paths or None,
    )

    if not result.success or not result.image_path:
        logger.warning("poster generate failed: %s", result.error)
        raise HTTPException(status_code=502, detail=result.error or "generation failed")

    try:
        rel = Path(result.image_path).resolve().relative_to(config.OUTPUT_DIR.resolve())
    except ValueError:
        rel = Path(result.image_path).name
    url = f"{config.POSTER_STUDIO_PUBLIC_ORIGIN}/output/{rel.as_posix()}"

    # Response shape expected by poster-studio's extractImageUrl().
    return {"data": [{"url": url, "original_url": url}]}


# Extensions accepted for pasted/uploaded images.
_UPLOAD_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@router.post("/api/poster/upload")
async def poster_upload(
    file: UploadFile = File(...),
    fileName: str | None = Form(default=None),
) -> dict:
    """Save a pasted/uploaded image to ``output/`` and return its URL.

    Replaces Qiniu for the canvas (clipboard paste, local upload, base64) so no
    cloud keys are required. Files land in ``output/poster/uploads/`` and thus
    also appear in the GRS AI 已生图库. CORS lets the canvas (:8100) POST here.
    """
    raw_name = (fileName or file.filename or "upload").strip()
    stem = "".join(c for c in (Path(raw_name).stem or "upload") if c.isalnum() or c in "-_")[:40]
    if not stem:
        stem = "upload"
    ext = "".join(c for c in Path(raw_name).suffix.lower() if c.isalnum() or c == ".")
    if ext not in _UPLOAD_EXTS:
        ext = ".png"

    dest_dir = config.OUTPUT_DIR / "poster" / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{stem}_{uuid.uuid4().hex[:8]}{ext}"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    dest.write_bytes(content)

    try:
        rel = dest.resolve().relative_to(config.OUTPUT_DIR.resolve())
    except ValueError:
        rel = dest.name
    url = f"{config.POSTER_STUDIO_PUBLIC_ORIGIN}/output/{rel.as_posix()}"
    return {"url": url}

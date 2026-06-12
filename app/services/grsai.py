"""Grsai image generation helpers."""

import base64
import json
import logging
import mimetypes
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config

logger = logging.getLogger(__name__)

GENERATE_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "generate.sh"
GRSAI_DEFAULT_BASE_URLS = ("https://grsai.dakka.com.cn", "https://grsaiapi.com")


@dataclass
class GrsaiResult:
    success: bool
    image_path: str | None = None
    error: str | None = None


def _image_to_data_url(path: str) -> str:
    image_path = Path(path)
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _request_json(url: str, payload: dict[str, Any], timeout: int = 1000) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {config.GRSAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, timeout: int = 60) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {config.GRSAI_API_KEY}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _base_urls() -> list[str]:
    urls = [config.GRSAI_BASE_URL, *GRSAI_DEFAULT_BASE_URLS]
    normalized: list[str] = []
    seen = set()
    for url in urls:
        clean_url = (url or "").rstrip("/")
        if clean_url and clean_url not in seen:
            normalized.append(clean_url)
            seen.add(clean_url)
    return normalized


def _is_connection_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return False
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, OSError))


def generate_image_direct(
    prompt: str,
    model: str,
    output_dir: str,
    ratio: str | None = None,
    size: str | None = None,
    quality: str | None = None,
    ref_paths: list[str] | None = None,
) -> GrsaiResult:
    """Generate an image by calling the Grsai API directly from the app."""
    if not config.GRSAI_API_KEY:
        return GrsaiResult(success=False, error="GRSAI_API_KEY is not configured")

    last_connection_error = None
    try:
        images = []
        for ref in ref_paths or []:
            images.append(ref if ref.startswith("http") else _image_to_data_url(ref))

        aspect = size if model.startswith("gpt-image-2") and size and "x" in size else (ratio or "auto")
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "images": images,
            "aspectRatio": aspect,
            "replyType": "json",
            "quality": quality or "auto",
        }
        if not model.startswith("gpt-image-2"):
            payload["imageSize"] = size or "2K"

        response = None
        used_base_url = None
        for base_url in _base_urls():
            try:
                response = _request_json(f"{base_url}/v1/api/generate", payload)
                used_base_url = base_url
                break
            except Exception as exc:
                if not _is_connection_error(exc):
                    raise
                last_connection_error = exc
                logger.warning("Grsai generate connection failed via %s: %s", base_url, exc)

        if response is None:
            return GrsaiResult(success=False, error=str(last_connection_error or "All Grsai API nodes failed"))

        if response.get("status") == "running":
            task_id = response.get("id")
            if not task_id:
                return GrsaiResult(success=False, error="Grsai async response missing task id")
            response = _poll_result(task_id, preferred_base_url=used_base_url)

        if response.get("status") in {"failed", "violation"}:
            return GrsaiResult(success=False, error=response.get("error") or "Grsai generation failed")

        results = response.get("results") or []
        image_url = results[0].get("url") if results else ""
        if not image_url:
            return GrsaiResult(success=False, error="No image URL in Grsai response")

        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        extension = image_url.split("?", 1)[0].rsplit(".", 1)[-1]
        if not extension or "/" in extension or len(extension) > 5:
            extension = "png"
        image_path = output / f"grsai_{time.strftime('%Y%m%d_%H%M%S')}.{extension}"
        urllib.request.urlretrieve(image_url, image_path)
        if not image_path.exists() or image_path.stat().st_size == 0:
            return GrsaiResult(success=False, error="Failed to download generated image")
        return GrsaiResult(success=True, image_path=str(image_path))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("Grsai HTTP error: %s", detail)
        return GrsaiResult(success=False, error=detail)
    except Exception as exc:
        logger.error("Unexpected Grsai direct generation error: %s", exc)
        return GrsaiResult(success=False, error=str(exc))


def _poll_result(task_id: str, preferred_base_url: str | None = None) -> dict[str, Any]:
    base_urls = _base_urls()
    if preferred_base_url:
        preferred_base_url = preferred_base_url.rstrip("/")
        base_urls = [preferred_base_url] + [url for url in base_urls if url != preferred_base_url]

    last_connection_error = None
    for _ in range(200):
        time.sleep(5)
        response = None
        for base_url in base_urls:
            try:
                response = _get_json(f"{base_url}/v1/api/result?id={task_id}")
                break
            except Exception as exc:
                if not _is_connection_error(exc):
                    raise
                last_connection_error = exc
                logger.warning("Grsai polling connection failed via %s: %s", base_url, exc)
        if response is None:
            return {"status": "failed", "error": str(last_connection_error or "All Grsai API nodes failed")}

        status = response.get("status")
        if status == "succeeded":
            return response
        if status in {"failed", "violation"}:
            return response
    return {"status": "failed", "error": f"Grsai task timed out: {task_id}"}


def run_generate(
    prompt: str,
    model: str,
    output_dir: str,
    ratio: str | None = None,
    size: str | None = None,
    quality: str | None = None,
    ref_paths: list[str] | None = None,
) -> GrsaiResult:
    """Generate an image and return the result.

    Args:
        prompt: The generation prompt.
        model: Grsai model name.
        output_dir: Directory to save generated image.
        ratio: Aspect ratio (e.g. "16:9").
        size: Resolution (e.g. "2K", "2048x2048").
        quality: Image quality (auto/low/medium/high).
        ref_paths: Reference image file paths.

    Returns:
        GrsaiResult with success status, image path, or error message.
    """
    direct_result = generate_image_direct(
        prompt=prompt,
        model=model,
        output_dir=output_dir,
        ratio=ratio,
        size=size,
        quality=quality,
        ref_paths=ref_paths,
    )
    if direct_result.success:
        return direct_result

    logger.warning("Direct Grsai generation failed, falling back to generate.sh: %s", direct_result.error)

    cmd = ["bash", str(GENERATE_SCRIPT)]

    cmd.extend(["--model", model])
    cmd.extend(["--output", output_dir])

    if ratio:
        cmd.extend(["--ratio", ratio])
    if size:
        cmd.extend(["--size", size])
    if quality:
        cmd.extend(["--quality", quality])
    if ref_paths:
        cmd.extend(["--ref", ",".join(ref_paths)])

    cmd.append(prompt)

    logger.info("Running generate.sh: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1100,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "generate.sh exited with non-zero status"
            logger.error("generate.sh failed: %s", error_msg)
            return GrsaiResult(success=False, error=error_msg)

        # The last line of stdout is the image path
        output_lines = result.stdout.strip().split("\n")
        image_path = output_lines[-1].strip() if output_lines else ""

        if not image_path:
            error_msg = result.stderr.strip() or "No output from generate.sh"
            logger.error("generate.sh produced no image path: %s", error_msg)
            return GrsaiResult(success=False, error=error_msg)

        logger.info("Generated image: %s", image_path)
        return GrsaiResult(success=True, image_path=image_path)

    except subprocess.TimeoutExpired:
        logger.error("generate.sh timed out after 1100s")
        return GrsaiResult(success=False, error="Generation timed out after 1100 seconds")
    except Exception as e:
        logger.error("Unexpected error running generate.sh: %s", e)
        return GrsaiResult(success=False, error=str(e))

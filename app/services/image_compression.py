import shutil
import subprocess
import uuid
from pathlib import Path


class ImageCompressionError(Exception):
    pass


def _compressed_output_path(image_path: Path, quality: int) -> Path:
    suffix = uuid.uuid4().hex[:8]
    return image_path.with_name(f"{image_path.stem}.compressed-q{quality}-{suffix}.jpg")


def compress_image(image_path: Path, quality: int = 75) -> Path:
    if not image_path.exists():
        raise ImageCompressionError("Source image file not found")

    sips = shutil.which("sips")
    if not sips:
        raise ImageCompressionError("Image compression requires macOS sips or a MozJPEG encoder")

    output_path = _compressed_output_path(image_path, quality)
    result = subprocess.run(
        [
            sips,
            "-s",
            "format",
            "jpeg",
            "-s",
            "formatOptions",
            str(quality),
            str(image_path),
            "--out",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0 or not output_path.exists():
        detail = result.stderr.strip() or result.stdout.strip() or "Image compression failed"
        raise ImageCompressionError(detail)

    return output_path

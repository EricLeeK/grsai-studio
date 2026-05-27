"""Wrapper around the Grsai generate.sh script."""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

GENERATE_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "generate.sh"


@dataclass
class GrsaiResult:
    success: bool
    image_path: str | None = None
    error: str | None = None


def run_generate(
    prompt: str,
    model: str,
    output_dir: str,
    ratio: str | None = None,
    size: str | None = None,
    quality: str | None = None,
    ref_paths: list[str] | None = None,
) -> GrsaiResult:
    """Invoke generate.sh and return the result.

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

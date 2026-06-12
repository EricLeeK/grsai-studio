import re
from pathlib import Path
from urllib.parse import quote

from fastapi.responses import HTMLResponse


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR_RESOLVED = STATIC_DIR.resolve()
_STATIC_URL_CACHE: dict[str, tuple[int, str]] = {}
_STATIC_URL_PATTERN = re.compile(
    r"\{\{\s*static_url\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
)


def static_url(asset_path: str) -> str:
    clean_path = asset_path.lstrip("/")
    path = (STATIC_DIR / clean_path).resolve()
    if not path.is_relative_to(STATIC_DIR_RESOLVED):
        raise ValueError(f"Static asset path escapes static directory: {asset_path}")
    stat = path.stat()
    version = stat.st_mtime_ns
    cached = _STATIC_URL_CACHE.get(clean_path)
    if cached and cached[0] == version:
        return cached[1]

    url = f"/static/{quote(clean_path)}?v={int(stat.st_mtime)}"
    _STATIC_URL_CACHE[clean_path] = (version, url)
    return url


def render_template(template_name: str) -> HTMLResponse:
    template_path = (TEMPLATES_DIR / template_name).resolve()
    if not template_path.is_relative_to(TEMPLATES_DIR.resolve()):
        raise ValueError(f"Template path escapes templates directory: {template_name}")

    html = template_path.read_text()
    html = _STATIC_URL_PATTERN.sub(lambda match: static_url(match.group(1)), html)
    return HTMLResponse(html)

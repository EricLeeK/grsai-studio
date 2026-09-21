import os
from pathlib import Path

# Load .env file if present
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
REFERENCE_IMAGE_DIR = DATA_DIR / "reference_images"
TASK_REFERENCE_DIR = DATA_DIR / "task_references"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
REFERENCE_IMAGE_DIR.mkdir(exist_ok=True)
TASK_REFERENCE_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'grsai.db'}"

# Grsai API config (from environment / .env)
GRSAI_API_KEY = os.environ.get("GRSAI_API_KEY", "")
GRSAI_BASE_URL = os.environ.get("GRSAI_BASE_URL", "https://grsai.dakka.com.cn")

# WeChat Official Account config
WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_SECRET = os.environ.get("WECHAT_SECRET", "")

# Gemini converter config
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# poster-studio (vendored Next.js canvas editor), reverse-proxied at /studio.
POSTER_STUDIO_DIR = BASE_DIR / "poster-studio"
POSTER_STUDIO_UPSTREAM = os.environ.get("POSTER_STUDIO_UPSTREAM", "http://127.0.0.1:8100")
POSTER_STUDIO_BASE_PATH = "/studio"

# Grsai generation used by the poster-studio canvas (/api/poster/generate).
POSTER_STUDIO_PUBLIC_ORIGIN = os.environ.get(
    "POSTER_STUDIO_PUBLIC_ORIGIN", "http://127.0.0.1:8099"
)
POSTER_STUDIO_MODEL = os.environ.get("POSTER_STUDIO_MODEL", "gpt-image-2-vip")

# Origins allowed to load generated images cross-origin (the canvas runs on its
# own port). Needed so Fabric can load /output images with crossOrigin anonymous.
POSTER_STUDIO_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "POSTER_STUDIO_CORS_ORIGINS",
        "http://127.0.0.1:8100,http://localhost:8100",
    ).split(",")
    if o.strip()
]

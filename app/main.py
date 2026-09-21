from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config
from app.database import init_db
from app.routers import comic, poster, previews, publisher, reference_images, tasks
from app.services.executor import shutdown_executor
from app.templating import render_template

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Grsai Studio", version="0.1.0")

# Allow the poster-studio canvas (separate port) to load generated images and
# call generation cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.POSTER_STUDIO_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(previews.router)
app.include_router(publisher.router)
app.include_router(reference_images.router)
app.include_router(comic.router)
app.include_router(poster.router)

# Mount static assets
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Mount output directory for serving generated images
output_dir = BASE_DIR.parent / "output"
output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")

reference_image_dir = BASE_DIR.parent / "data" / "reference_images"
reference_image_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/reference-images",
    StaticFiles(directory=str(reference_image_dir)),
    name="reference-images",
)

# Mount task-scoped reference images (clipboard / per-task uploads) so reused
# reference paths can be previewed in the browser.
task_reference_dir = BASE_DIR.parent / "data" / "task_references"
task_reference_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/task-references",
    StaticFiles(directory=str(task_reference_dir)),
    name="task-references",
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.on_event("shutdown")
def on_shutdown():
    shutdown_executor(wait=True)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def serve_index():
    return render_template("index.html")


@app.get("/apps")
def serve_apps():
    return render_template("apps.html")


@app.get("/comic")
def serve_comic():
    return render_template("comic.html")

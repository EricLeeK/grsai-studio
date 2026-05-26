from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import tasks
from app.services.executor import shutdown_executor

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Grsai Studio", version="0.1.0")

app.include_router(tasks.router)

# Mount static assets
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Mount output directory for serving generated images
output_dir = BASE_DIR.parent / "output"
output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")


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
    return FileResponse(BASE_DIR / "templates" / "index.html")

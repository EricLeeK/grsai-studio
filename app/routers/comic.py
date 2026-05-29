from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ComicCandidate, ComicProject
from app.schemas import ComicCandidateOut, ComicProjectCreate, ComicProjectOut

router = APIRouter(prefix="/api/comic", tags=["comic"])


@router.get("/projects", response_model=list[ComicProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(ComicProject).order_by(ComicProject.updated_at.desc()).all()


@router.post("/projects", response_model=ComicProjectOut, status_code=201)
def create_project(body: ComicProjectCreate, db: Session = Depends(get_db)):
    project = ComicProject(name=body.name.strip() or "Untitled Comic")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/current", response_model=ComicProjectOut)
def get_current_project(db: Session = Depends(get_db)):
    project = db.query(ComicProject).order_by(ComicProject.updated_at.desc()).first()
    if not project:
        project = ComicProject(name="Untitled Comic")
        db.add(project)
        db.commit()
        db.refresh(project)
    return project


@router.get(
    "/projects/{project_id}/candidates",
    response_model=list[ComicCandidateOut],
)
def list_candidates(project_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ComicCandidate)
        .filter(ComicCandidate.comic_project_id == project_id)
        .order_by(ComicCandidate.created_at.asc(), ComicCandidate.id.asc())
        .all()
    )


@router.post("/candidates/{candidate_id}/select", response_model=ComicCandidateOut)
def select_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(ComicCandidate).filter(ComicCandidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Comic candidate not found")

    siblings = (
        db.query(ComicCandidate)
        .filter(ComicCandidate.comic_project_id == candidate.comic_project_id)
        .filter(ComicCandidate.page_type == candidate.page_type)
        .filter(ComicCandidate.page_number.is_(candidate.page_number) if candidate.page_number is None else ComicCandidate.page_number == candidate.page_number)
        .all()
    )
    for sibling in siblings:
        sibling.is_selected = sibling.id == candidate.id
    db.commit()
    db.refresh(candidate)
    return candidate

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ComicCandidate, ComicIPReference, ComicProject, ComicPrompt, ReferenceImage
from app.schemas import (
    ComicCandidateOut,
    ComicIPReferencesUpdate,
    ComicProjectCreate,
    ComicProjectOut,
    ComicPromptCreate,
    ComicPromptOut,
    ComicPromptUpdate,
    ReferenceImageOut,
)

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


@router.get("/projects/{project_id}/prompts", response_model=list[ComicPromptOut])
def list_prompts(project_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ComicPrompt)
        .filter(ComicPrompt.comic_project_id == project_id)
        .order_by(ComicPrompt.created_at.asc(), ComicPrompt.id.asc())
        .all()
    )


@router.post(
    "/projects/{project_id}/prompts",
    response_model=ComicPromptOut,
    status_code=201,
)
def create_prompt(
    project_id: int,
    body: ComicPromptCreate,
    db: Session = Depends(get_db),
):
    prompt = ComicPrompt(
        comic_project_id=project_id,
        page_type=body.page_type,
        text=body.text.strip(),
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.patch("/prompts/{prompt_id}", response_model=ComicPromptOut)
def update_prompt(
    prompt_id: int,
    body: ComicPromptUpdate,
    db: Session = Depends(get_db),
):
    prompt = db.query(ComicPrompt).filter(ComicPrompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Comic prompt not found")
    prompt.text = body.text.strip()
    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/prompts/{prompt_id}", status_code=204)
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    prompt = db.query(ComicPrompt).filter(ComicPrompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Comic prompt not found")
    db.delete(prompt)
    db.commit()
    return None


@router.get(
    "/projects/{project_id}/ip-references",
    response_model=list[ReferenceImageOut],
)
def list_ip_references(project_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(ReferenceImage)
        .join(ComicIPReference, ComicIPReference.reference_image_id == ReferenceImage.id)
        .filter(ComicIPReference.comic_project_id == project_id)
        .order_by(ComicIPReference.created_at.asc(), ComicIPReference.id.asc())
        .all()
    )
    return rows


@router.put(
    "/projects/{project_id}/ip-references",
    response_model=list[ReferenceImageOut],
)
def update_ip_references(
    project_id: int,
    body: ComicIPReferencesUpdate,
    db: Session = Depends(get_db),
):
    db.query(ComicIPReference).filter(
        ComicIPReference.comic_project_id == project_id
    ).delete()
    for image_id in body.reference_image_ids:
        db.add(ComicIPReference(comic_project_id=project_id, reference_image_id=image_id))
    db.commit()
    return list_ip_references(project_id, db)


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

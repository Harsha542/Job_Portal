
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import Application, Job, User
from schemas import (
    ApplicantResponse,
    ApplicationResponse,
    ApplicationStatusUpdate,
)

router = APIRouter(prefix="/applications", tags=["Applications"])

RESUME_DIR = Path(__file__).resolve().parents[1] / "uploads" / "resumes"
MAX_RESUME_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def get_application_or_404(application_id: int, db: Session) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def check_recruiter_job_permission(job: Job, user: User) -> None:
    if user.role != "admin" and job.recruiter_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only manage applicants for your own jobs",
        )


def application_to_response(application: Application) -> dict:
    return {
        "id": application.id,
        "candidate_id": application.candidate_id,
        "job_id": application.job_id,
        "job_title": application.job.title,
        "job_location": application.job.location,
        "status": application.status,
        "applied_at": application.applied_at,
        "resume_available": bool(application.resume_path),
    }


def applicant_to_response(application: Application) -> dict:
    return {
        "id": application.id,
        "candidate_id": application.candidate.id,
        "candidate_name": application.candidate.full_name,
        "candidate_email": application.candidate.email,
        "job_id": application.job.id,
        "job_title": application.job.title,
        "status": application.status,
        "applied_at": application.applied_at,
        "resume_available": bool(application.resume_path),
    }


def validate_resume(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Upload a PDF or DOCX resume",
        )

    if not content:
        raise HTTPException(status_code=400, detail="The uploaded resume is empty")

    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    if extension == ".docx" and not content.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Invalid DOCX file")

    return extension


@router.post(
    "/jobs/{job_id}/apply",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_for_job(
    job_id: int,
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("candidate")),
):
    job = db.get(Job, job_id)

    if job is None or not job.is_active:
        raise HTTPException(status_code=404, detail="Active job not found")

    existing = (
        db.query(Application)
        .filter(
            Application.candidate_id == current_user.id,
            Application.job_id == job_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You have already applied for this job",
        )

    filename = resume.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        await resume.close()
        raise HTTPException(status_code=400, detail="Upload a PDF or DOCX resume")

    content = await resume.read(MAX_RESUME_SIZE + 1)
    await resume.close()

    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Resume must not exceed 5 MB",
        )

    extension = validate_resume(filename, content)

    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{extension}"
    resume_path = RESUME_DIR / stored_filename
    resume_path.write_bytes(content)

    application = Application(
        candidate_id=current_user.id,
        job_id=job.id,
        resume_path=stored_filename,
        status="Applied",
    )

    try:
        db.add(application)
        db.commit()
        db.refresh(application)
    except IntegrityError:
        db.rollback()
        resume_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="You have already applied for this job",
        )
    except Exception:
        db.rollback()
        resume_path.unlink(missing_ok=True)
        raise

    return application_to_response(application)


@router.get("/my", response_model=list[ApplicationResponse])
def get_my_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("candidate")),
):
    applications = (
        db.query(Application)
        .filter(Application.candidate_id == current_user.id)
        .order_by(Application.applied_at.desc())
        .all()
    )
    return [application_to_response(item) for item in applications]


@router.get("/jobs/{job_id}", response_model=list[ApplicantResponse])
def get_job_applicants(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recruiter", "admin")),
):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    check_recruiter_job_permission(job, current_user)

    applications = (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(Application.applied_at.desc())
        .all()
    )
    return [applicant_to_response(item) for item in applications]


@router.patch("/{application_id}/status", response_model=ApplicantResponse)
def update_application_status(
    application_id: int,
    data: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recruiter", "admin")),
):
    application = get_application_or_404(application_id, db)
    check_recruiter_job_permission(application.job, current_user)

    application.status = data.status
    db.commit()
    db.refresh(application)

    return applicant_to_response(application)


@router.get("/{application_id}/resume")
def download_resume(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = get_application_or_404(application_id, db)

    if current_user.role == "candidate":
        if application.candidate_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot access another candidate's resume",
            )
    elif current_user.role == "recruiter":
        check_recruiter_job_permission(application.job, current_user)
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    if not application.resume_path:
        raise HTTPException(
            status_code=404,
            detail="No resume is attached to this application",
        )

    resume_path = RESUME_DIR / Path(application.resume_path).name

    if not resume_path.is_file():
        raise HTTPException(status_code=404, detail="Resume file not found")

    extension = resume_path.suffix.lower()
    media_type = (
        "application/pdf"
        if extension == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    return FileResponse(
        path=resume_path,
        media_type=media_type,
        filename=f"candidate_resume{extension}",
    )
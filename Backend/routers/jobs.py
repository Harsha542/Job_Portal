
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models import Job, User
from schemas import JobCreate, JobUpdate, JobResponse
from auth import get_current_user, require_role

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def get_job_or_404(job_id: int, db: Session) -> Job:
    job = db.get(Job, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return job


def check_job_permission(job: Job, user: User):
    if user.role != "admin" and job.recruiter_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own job postings",
        )


# Create a job
@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recruiter", "admin")),
):
    job = Job(
        **data.model_dump(),
        recruiter_id=current_user.id,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


# Recruiter's own jobs — keep this before /{job_id}
@router.get("/my", response_model=list[JobResponse])
def get_my_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recruiter", "admin")),
):
    query = db.query(Job)

    if current_user.role != "admin":
        query = query.filter(Job.recruiter_id == current_user.id)

    return query.order_by(Job.created_at.desc()).all()


# Browse and search active jobs
@router.get("", response_model=list[JobResponse])
def list_jobs(
    q: str | None = Query(default=None, max_length=100),
    location: str | None = Query(default=None, max_length=150),
    skills: str | None = Query(default=None, max_length=200),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter(Job.is_active.is_(True))

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Job.title.ilike(term),
                Job.description.ilike(term),
            )
        )

    if location and location.strip():
        query = query.filter(
            Job.location.ilike(f"%{location.strip()}%")
        )

    if skills and skills.strip():
        query = query.filter(
            Job.required_skills.ilike(f"%{skills.strip()}%")
        )

    return (
        query.order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# View a specific active job
@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    job = get_job_or_404(job_id, db)

    if not job.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return job


# Update a job
@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recruiter", "admin")),
):
    job = get_job_or_404(job_id, db)
    check_job_permission(job, current_user)

    if not job.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Closed jobs cannot be updated",
        )

    updates = data.model_dump(exclude_unset=True)

    # Validate the combined salary range, including unchanged values.
    new_min = updates.get("salary_min", job.salary_min)
    new_max = updates.get("salary_max", job.salary_max)

    if (
        new_min is not None
        and new_max is not None
        and new_max < new_min
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum salary must be greater than or equal to minimum salary",
        )

    for field, value in updates.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)

    return job


# Close a job
@router.patch("/{job_id}/close", response_model=JobResponse)
def close_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("recruiter", "admin")),
):
    job = get_job_or_404(job_id, db)
    check_job_permission(job, current_user)

    if not job.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is already closed",
        )

    job.is_active = False
    db.commit()
    db.refresh(job)

    return job
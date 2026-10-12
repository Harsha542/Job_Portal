
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Application, Interview, Job, User


router = APIRouter(prefix="/interviews", tags=["Interviews"])

# Interview dates entered by the frontend use Indian Standard Time.
IST = timezone(timedelta(hours=5, minutes=30))


# -------------------------
# Request schemas
# -------------------------

class InterviewCreate(BaseModel):
    scheduled_at: datetime
    interview_type: Literal["Online", "In-person", "Phone"] = "Online"
    meeting_details: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class InterviewUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    interview_type: Optional[Literal["Online", "In-person", "Phone"]] = None
    meeting_details: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[Literal["Scheduled", "Completed"]] = None

    model_config = ConfigDict(extra="forbid")


# -------------------------
# Datetime helpers
# -------------------------

def to_utc(value: datetime) -> datetime:
    """
    Convert a datetime to UTC before comparing it.

    SQLite may return a naive datetime after removing timezone
    information. This project stores interview wall times in IST,
    so a naive stored datetime is interpreted as IST.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=IST)

    return value.astimezone(timezone.utc)


def validate_future_datetime(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scheduled_at must include a timezone, such as +05:30.",
        )

    if to_utc(value) <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The interview date and time must be in the future.",
        )


def serialize_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=IST)

    return value.isoformat()


# -------------------------
# Database and permission helpers
# -------------------------

def get_application_or_404(db: Session, application_id: int):
    application = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    job = db.query(Job).filter(Job.id == application.job_id).first()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The job associated with this application was not found.",
        )

    return application, job


def ensure_recruiter_or_admin(current_user: User):
    if current_user.role not in ("recruiter", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters and admins can manage interviews.",
        )


def ensure_application_access(current_user: User, job: Job):
    ensure_recruiter_or_admin(current_user)

    if (
        current_user.role != "admin"
        and job.recruiter_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage interviews for your own job postings.",
        )


def get_interview_or_404(db: Session, interview_id: int):
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id)
        .first()
    )

    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found.",
        )

    application, job = get_application_or_404(
        db,
        interview.application_id,
    )

    return interview, application, job


# -------------------------
# Interview response helper
# -------------------------

def interview_response(db: Session, interview: Interview):
    application, job = get_application_or_404(
        db,
        interview.application_id,
    )

    candidate = (
        db.query(User)
        .filter(User.id == application.candidate_id)
        .first()
    )

    return {
        "id": interview.id,
        "application_id": application.id,
        "candidate_id": application.candidate_id,
        "candidate_name": (
            candidate.full_name if candidate else "Unknown candidate"
        ),
        "candidate_email": candidate.email if candidate else None,
        "job_id": job.id,
        "job_title": job.title,
        "recruiter_id": job.recruiter_id,
        "scheduled_at": serialize_datetime(interview.scheduled_at),
        "interview_type": interview.interview_type,
        "meeting_details": interview.meeting_details,
        "notes": interview.notes,
        "status": interview.status,
        "created_at": serialize_datetime(
            getattr(interview, "created_at", None)
        ),
    }


# -------------------------
# Schedule an interview
# -------------------------

@router.post(
    "/applications/{application_id}",
    status_code=status.HTTP_201_CREATED,
)
def schedule_interview(
    application_id: int,
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application, job = get_application_or_404(db, application_id)
    ensure_application_access(current_user, job)

    if application.status in ("Rejected", "Hired"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot schedule an interview for a rejected or hired application.",
        )

    validate_future_datetime(payload.scheduled_at)

    interview = Interview(
        application_id=application.id,
        candidate_id=application.candidate_id,
        job_id=job.id,
        recruiter_id=job.recruiter_id,
        scheduled_at=payload.scheduled_at,
        interview_type=payload.interview_type,
        meeting_details=payload.meeting_details,
        notes=payload.notes,
        status="Scheduled",
    )

    try:
        db.add(interview)
        db.commit()
        db.refresh(interview)
        return interview_response(db, interview)
    except Exception:
        db.rollback()
        raise


# -------------------------
# Candidate: view my interviews
# -------------------------

@router.get("/my")
def get_my_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for candidates.",
        )

    interviews = (
        db.query(Interview)
        .filter(Interview.candidate_id == current_user.id)
        .order_by(Interview.scheduled_at.asc())
        .all()
    )

    return [
        interview_response(db, interview)
        for interview in interviews
    ]


# -------------------------
# Recruiter/admin: view interviews for an application
# -------------------------

@router.get("/applications/{application_id}")
def get_application_interviews(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application, job = get_application_or_404(db, application_id)
    ensure_application_access(current_user, job)

    interviews = (
        db.query(Interview)
        .filter(Interview.application_id == application.id)
        .order_by(Interview.scheduled_at.asc())
        .all()
    )

    return [
        interview_response(db, interview)
        for interview in interviews
    ]


# -------------------------
# Update an interview
# -------------------------

@router.patch("/{interview_id}")
def update_interview(
    interview_id: int,
    payload: InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview, application, job = get_interview_or_404(
        db,
        interview_id,
    )
    ensure_application_access(current_user, job)

    if interview.status == "Cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A cancelled interview cannot be updated.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update.",
        )

    new_status = updates.get("status", interview.status)
    new_datetime = updates.get("scheduled_at", interview.scheduled_at)

    # A scheduled interview must have a future date and time.
    # Normalize both values before comparison to prevent the
    # offset-naive versus offset-aware TypeError.
    if new_status == "Scheduled":
        if "scheduled_at" in updates:
            validate_future_datetime(updates["scheduled_at"])
        elif to_utc(new_datetime) <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This interview is in the past. "
                    "Choose a future date and time before scheduling it."
                ),
            )

    for field, value in updates.items():
        setattr(interview, field, value)

    try:
        db.commit()
        db.refresh(interview)
        return interview_response(db, interview)
    except Exception:
        db.rollback()
        raise


# -------------------------
# Cancel an interview
# -------------------------

@router.post("/{interview_id}/cancel")
def cancel_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview, application, job = get_interview_or_404(
        db,
        interview_id,
    )
    ensure_application_access(current_user, job)

    if interview.status == "Cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This interview is already cancelled.",
        )

    if interview.status == "Completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A completed interview cannot be cancelled.",
        )

    try:
        interview.status = "Cancelled"
        db.commit()
        db.refresh(interview)
        return interview_response(db, interview)
    except Exception:
        db.rollback()
        raise
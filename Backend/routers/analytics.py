
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from models import Application, Job, User


router = APIRouter(prefix="/analytics", tags=["Recruitment Analytics"])


@router.get("/dashboard")
def get_recruitment_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_candidates = (
        db.query(func.count(User.id))
        .filter(User.role == "candidate")
        .scalar()
        or 0
    )
    total_recruiters = (
        db.query(func.count(User.id))
        .filter(User.role == "recruiter")
        .scalar()
        or 0
    )

    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    active_jobs = (
        db.query(func.count(Job.id))
        .filter(Job.is_active.is_(True))
        .scalar()
        or 0
    )
    closed_jobs = total_jobs - active_jobs

    total_applications = (
        db.query(func.count(Application.id)).scalar() or 0
    )

    hired_count = (
        db.query(func.count(Application.id))
        .filter(Application.status == "Hired")
        .scalar()
        or 0
    )

    status_rows = (
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )

    status_counts = {
        "Applied": 0,
        "Shortlisted": 0,
        "Interview": 0,
        "Hired": 0,
        "Rejected": 0,
    }

    for application_status, count in status_rows:
        status_counts[application_status] = count

    # Applications created during the last 12 calendar months,
    # including the current month.
    now = datetime.now(timezone.utc)
    first_month = (now.year * 12 + now.month - 1) - 11
    first_year = first_month // 12
    first_month_number = first_month % 12 + 1
    start_date = datetime(
        first_year,
        first_month_number,
        1,
        tzinfo=timezone.utc,
    )

    monthly_rows = (
        db.query(
            func.strftime("%Y-%m", Application.applied_at).label("month"),
            func.count(Application.id).label("total"),
        )
        .filter(Application.applied_at >= start_date)
        .group_by(func.strftime("%Y-%m", Application.applied_at))
        .order_by(func.strftime("%Y-%m", Application.applied_at))
        .all()
    )

    monthly_lookup = {
        month: count
        for month, count in monthly_rows
        if month is not None
    }

    monthly_applications = []
    for offset in range(12):
        month_index = first_month + offset
        year = month_index // 12
        month_number = month_index % 12 + 1
        month_label = f"{year:04d}-{month_number:02d}"

        monthly_applications.append(
            {
                "month": month_label,
                "applications": monthly_lookup.get(month_label, 0),
            }
        )

    top_job_rows = (
        db.query(
            Job.id,
            Job.title,
            Job.location,
            func.count(Application.id).label("applicant_count"),
        )
        .outerjoin(Application, Application.job_id == Job.id)
        .group_by(Job.id, Job.title, Job.location)
        .order_by(func.count(Application.id).desc(), Job.id.desc())
        .limit(10)
        .all()
    )

    top_jobs = [
        {
            "job_id": job_id,
            "title": title,
            "location": location,
            "applicants": applicant_count,
        }
        for job_id, title, location, applicant_count in top_job_rows
    ]

    return {
        "generated_at": now.isoformat(),
        "overview": {
            "total_users": total_users,
            "total_candidates": total_candidates,
            "total_recruiters": total_recruiters,
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "closed_jobs": closed_jobs,
            "total_applications": total_applications,
            "hired_count": hired_count,
            "hiring_rate_percent": (
                round(hired_count / total_applications * 100, 2)
                if total_applications
                else 0
            ),
        },
        "application_statuses": [
            {"status": name, "count": count}
            for name, count in status_counts.items()
        ],
        "monthly_applications": monthly_applications,
        "top_jobs": top_jobs,
    }
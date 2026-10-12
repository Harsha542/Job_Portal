

from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def current_time():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    full_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), default="candidate", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_time,
        nullable=False,
    )

    jobs: Mapped[list["Job"]] = relationship(
        back_populates="recruiter"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="candidate",
        foreign_keys="Application.candidate_id",
    )
    scheduled_interviews: Mapped[list["Interview"]] = relationship(
        back_populates="recruiter",
        foreign_keys="Interview.recruiter_id",
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    title: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    location: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    required_skills: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    salary_min: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    salary_max: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    recruiter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_time,
        nullable=False,
    )

    recruiter: Mapped["User"] = relationship(
        back_populates="jobs"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="job"
    )


class Application(Base):
    __tablename__ = "applications"

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_candidate_job_application",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), nullable=False
    )
    resume_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="Applied", nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_time,
        nullable=False,
    )

    candidate: Mapped["User"] = relationship(
        back_populates="applications",
        foreign_keys=[candidate_id],
    )
    job: Mapped["Job"] = relationship(
        back_populates="applications"
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"), nullable=False, index=True
    )
    recruiter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    interview_type: Mapped[str] = mapped_column(
        String(30), default="Online", nullable=False
    )
    meeting_details: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="Scheduled", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=current_time,
        nullable=False,
    )

    application: Mapped["Application"] = relationship(
        back_populates="interviews"
    )
    recruiter: Mapped["User"] = relationship(
        back_populates="scheduled_interviews",
        foreign_keys=[recruiter_id],
    )
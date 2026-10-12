
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


# -------------------------
# Authentication schemas
# -------------------------

class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["candidate", "recruiter"] = "candidate"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -------------------------
# Job schemas
# -------------------------

class JobCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=20)
    location: str = Field(min_length=2, max_length=150)
    required_skills: str = Field(min_length=2)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_salary_range(self):
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError(
                "Maximum salary must be greater than or equal to minimum salary"
            )
        return self


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, min_length=20)
    location: str | None = Field(default=None, min_length=2, max_length=150)
    required_skills: str | None = Field(default=None, min_length=2)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_update(self):
        required_fields = (
            "title",
            "description",
            "location",
            "required_skills",
        )

        for field_name in required_fields:
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} cannot be null")

        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError(
                "Maximum salary must be greater than or equal to minimum salary"
            )

        return self


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    location: str
    required_skills: str
    salary_min: float | None
    salary_max: float | None
    recruiter_id: int
    is_active: bool
    created_at: datetime


# -------------------------
# Application schemas
# -------------------------

ApplicationStatus = Literal[
    "Applied",
    "Shortlisted",
    "Interview",
    "Rejected",
    "Hired",
]


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationResponse(BaseModel):
    id: int
    candidate_id: int
    job_id: int
    job_title: str
    job_location: str
    status: ApplicationStatus
    applied_at: datetime
    resume_available: bool


class ApplicantResponse(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str
    candidate_email: EmailStr
    job_id: int
    job_title: str
    status: ApplicationStatus
    applied_at: datetime
    resume_available: bool

from fastapi import Depends, FastAPI
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
import models

from routers.auth import router as auth_router
from routers.jobs import router as jobs_router
from routers.applications import router as applications_router
from routers.analytics import router as analytics_router
from routers.interviews import router as interviews_router


# Create missing tables in the configured database.
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Job Portal & Recruitment Management System",
    description=(
        "A recruitment platform for candidates, recruiters, "
        "and administrators."
    ),
    version="1.0.0",
)


app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(analytics_router)
app.include_router(interviews_router)


@app.get("/", tags=["General"])
def home():
    return {
        "message": "Job Portal API is running",
        "status": "success",
        "version": "1.0.0",
    }


@app.get("/health", tags=["General"])
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "database": "connected",
    }


@app.get("/database/tables", tags=["Database"])
def list_tables():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    return {"tables": sorted(tables)}
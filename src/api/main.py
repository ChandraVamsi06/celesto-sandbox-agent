import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.api.database import db

SANDBOX_NAME_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")
VALID_STATES = {"created", "ready", "running", "succeeded", "failed", "deleted"}
REQUIRED_EXECUTION_TARGET = "celesto_sandbox"


class RunCreateRequest(BaseModel):
    run_id: str = Field(..., description="Unique run identifier")
    sandbox_name: str = Field(..., description="Sandbox name matching sbx- followed by 8+ lowercase alphanumeric chars")
    problem_id: str = Field(..., description="Problem identifier")
    state: str = Field(..., description="Run state: created, ready, running, succeeded, failed, or deleted")
    execution_target: str = Field(..., description="Execution target, must strictly be celesto_sandbox")


class RunResponse(BaseModel):
    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seeds on startup
    db.init_db()
    yield


app = FastAPI(
    title="Celesto Sandbox Run Ledger API",
    description="Trusted control plane API managing agent run ledger and isolation verification",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve report files and execution command logs
reports_dir = Path("reports")
if reports_dir.exists():
    app.mount("/reports", StaticFiles(directory=str(reports_dir)), name="reports")

logs_dir = Path("logs")
if logs_dir.exists():
    app.mount("/logs", StaticFiles(directory=str(logs_dir)), name="logs")



@app.get("/health")
def health_check():
    """Health check endpoint for Docker Compose and uptime probes."""
    return {"status": "ok"}


@app.get("/api/runs", response_model=List[RunResponse])
def get_runs():
    """List all recorded sandbox runs."""
    return db.list_runs()


@app.post("/api/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def record_run(payload: RunCreateRequest):
    """
    Record an agent sandbox run.
    Rejects any run targeting the host or with invalid sandbox nomenclature or state.
    """
    if payload.execution_target != REQUIRED_EXECUTION_TARGET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid execution_target '{payload.execution_target}'. Only '{REQUIRED_EXECUTION_TARGET}' is allowed.",
        )

    if payload.state not in VALID_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state '{payload.state}'. Allowed states are: {sorted(list(VALID_STATES))}",
        )

    if not SANDBOX_NAME_REGEX.match(payload.sandbox_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sandbox_name '{payload.sandbox_name}'. Must start with 'sbx-' followed by 8 or more lowercase letters/digits.",
        )

    created = db.create_run(
        run_id=payload.run_id,
        sandbox_name=payload.sandbox_name,
        problem_id=payload.problem_id,
        state=payload.state,
        execution_target=payload.execution_target,
    )
    return created

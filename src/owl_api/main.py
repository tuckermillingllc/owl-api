"""FastAPI app for owl-api."""

from __future__ import annotations

import asyncio

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .jobs import store
from .models import JobStatus, OptimizeResult, OwlCase
from .solver import solve_case
from .state_tax import SUPPORTED_STATES


app = FastAPI(
    title="owl-api",
    version=__version__,
    description=(
        "FastAPI wrapper around mdlacasse/Owl with state-tax post-processing. "
        "Backs the Retirement tab in FinanceKeeper."
    ),
)

# CORS — only used when running the dev server alongside a Vite/Streamlit UI.
# iOS / Swift clients don't care about CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/states")
async def states() -> list[dict[str, str]]:
    return SUPPORTED_STATES


@app.post("/optimize", response_model=JobStatus)
async def optimize(case: OwlCase, background: BackgroundTasks) -> JobStatus:
    job_id = await store.create()

    async def runner() -> OptimizeResult:
        # Run the synchronous owlplanner solve in a worker thread so the event
        # loop stays responsive.
        return await asyncio.to_thread(solve_case, case)

    background.add_task(store.run, job_id, runner)
    job = await store.get(job_id)
    assert job is not None
    return job


@app.post("/optimize/sync", response_model=OptimizeResult)
async def optimize_sync(case: OwlCase) -> OptimizeResult:
    """Run synchronously — convenient for quick curl tests / CI."""
    return await asyncio.to_thread(solve_case, case)


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def job_status(job_id: str) -> JobStatus:
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(404, f"unknown job {job_id}")
    return job

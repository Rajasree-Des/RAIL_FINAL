"""Standalone FastAPI application for Playwright automation."""

import asyncio
import logging

from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import settings
from app.core.job_manager import job_manager
from app.core.logging import setup_logging
from app.scrapers.railmadad.runner import RailMadadRunner

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Rail Automation Engine",
    description="Standalone Playwright service for RailMadad downloads",
    version="1.0.0",
)


async def verify_token(authorization: str | None = Header(None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if authorization[7:] != settings.service_token:
        raise HTTPException(status_code=403, detail="Invalid token")


async def _run_job(config: dict) -> None:
    run_id = config["run_id"]
    try:
        runner = RailMadadRunner(config)
        await runner.execute()
    except asyncio.CancelledError:
        job_manager.update_status(run_id, "stopped")
        logger.info("Job %s cancelled", run_id)
    except Exception:
        logger.exception("Job %s failed", run_id)
        job_manager.update_status(run_id, "failed")
    finally:
        job_manager.cleanup(run_id)


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "automation-engine"}


@app.post("/internal/run", dependencies=[Depends(verify_token)])
async def start_run(config: dict) -> dict:
    run_id = config.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id required")

    if job_manager.get(run_id):
        raise HTTPException(status_code=409, detail="Job already exists")

    state = job_manager.register(run_id, config)
    task = asyncio.create_task(_run_job(config))
    job_manager.set_task(run_id, task)

    return {"success": True, "run_id": run_id, "status": state.status}


@app.post("/internal/stop/{run_id}", dependencies=[Depends(verify_token)])
async def stop_run(run_id: str) -> dict:
    ok = job_manager.stop(run_id)
    return {"success": ok, "run_id": run_id, "status": "stopped"}


@app.post("/internal/pause/{run_id}", dependencies=[Depends(verify_token)])
async def pause_run(run_id: str) -> dict:
    ok = job_manager.pause(run_id)
    return {"success": ok, "run_id": run_id, "status": "paused"}


@app.post("/internal/resume/{run_id}", dependencies=[Depends(verify_token)])
async def resume_run(run_id: str) -> dict:
    ok = job_manager.resume(run_id)
    return {"success": ok, "run_id": run_id, "status": "running"}


@app.get("/internal/status/{run_id}", dependencies=[Depends(verify_token)])
async def get_status(run_id: str) -> dict:
    state = job_manager.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"run_id": run_id, "status": state.status}

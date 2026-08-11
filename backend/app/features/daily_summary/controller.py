"""API controller for Daily Summary."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.domain.entities.user import User
from app.features.activity.emit import emit_activity
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.features.daily_summary.dependencies import get_daily_summary_service
from app.features.daily_summary.schemas import DailySummaryListResponse, DailySummaryResponse
from app.features.daily_summary.service import DailySummaryService

router = APIRouter(tags=["daily-summary"])

_DEBUG_LOG = Path(__file__).resolve().parents[4] / "debug-6b4059.log"


def _agent_log(*, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "6b4059",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _DEBUG_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    except Exception:
        pass
    # #endregion


@router.get(
    "/automation/runs/{run_id}/summary",
    response_model=DailySummaryResponse,
    dependencies=[Depends(require_officer_or_admin)],
)
async def get_run_summary(
    run_id: str,
    service: Annotated[DailySummaryService, Depends(get_daily_summary_service)],
    user: Annotated[User, Depends(require_officer_or_admin)],
) -> DailySummaryResponse:
    _agent_log(
        hypothesis_id="H1-H4",
        location="daily_summary/controller.py:get_run_summary",
        message="GET summary request",
        data={"run_id": run_id, "user_id": user.id, "run_id_len": len(run_id)},
    )
    try:
        result = await service.get_for_run(run_id, user.id)
        _agent_log(
            hypothesis_id="H4",
            location="daily_summary/controller.py:get_run_summary",
            message="GET summary success",
            data={"run_id": run_id, "summary_id": result.summary_id, "status": result.status},
        )
        return result
    except Exception as exc:
        _agent_log(
            hypothesis_id="H1-H4",
            location="daily_summary/controller.py:get_run_summary",
            message="GET summary error",
            data={"run_id": run_id, "exc_type": type(exc).__name__, "exc_msg": str(exc)[:200]},
        )
        raise


@router.post(
    "/automation/runs/{run_id}/summary/regenerate",
    response_model=DailySummaryResponse,
    dependencies=[Depends(require_officer_or_admin), Depends(validate_csrf_token)],
)
async def regenerate_run_summary(
    run_id: str,
    service: Annotated[DailySummaryService, Depends(get_daily_summary_service)],
    user: Annotated[User, Depends(require_officer_or_admin)],
) -> DailySummaryResponse:
    _agent_log(
        hypothesis_id="H1-H3",
        location="daily_summary/controller.py:regenerate_run_summary",
        message="POST regenerate request",
        data={"run_id": run_id, "user_id": user.id, "run_id_len": len(run_id)},
    )
    try:
        result = await service.generate(run_id, user.id, regenerated=True)
        _agent_log(
            hypothesis_id="H3",
            location="daily_summary/controller.py:regenerate_run_summary",
            message="POST regenerate success",
            data={"run_id": run_id, "summary_id": result.summary_id, "status": result.status},
        )
        return result
    except Exception as exc:
        _agent_log(
            hypothesis_id="H1-H3",
            location="daily_summary/controller.py:regenerate_run_summary",
            message="POST regenerate error",
            data={"run_id": run_id, "exc_type": type(exc).__name__, "exc_msg": str(exc)[:200]},
        )
        raise


@router.post(
    "/automation/runs/{run_id}/summary/copied",
    status_code=204,
    dependencies=[Depends(require_officer_or_admin), Depends(validate_csrf_token)],
)
async def mark_summary_copied(
    run_id: str,
    user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[DailySummaryService, Depends(get_daily_summary_service)],
) -> None:
    summary = await service.get_for_run(run_id, user.id)
    await emit_activity(
        user_id=user.id,
        action="SUMMARY_COPIED",
        message=f"Daily summary copied for {summary.report_date}",
        status="info",
        run_id=run_id,
        metadata={
            "summary_id": summary.summary_id,
            "report_date": summary.report_date,
        },
        dedupe_key=None,
    )


@router.get(
    "/summaries",
    response_model=DailySummaryListResponse,
    dependencies=[Depends(require_officer_or_admin)],
)
async def list_daily_summaries(
    service: Annotated[DailySummaryService, Depends(get_daily_summary_service)],
    user: Annotated[User, Depends(require_officer_or_admin)],
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DailySummaryListResponse:
    return await service.list_summaries(user.id, limit=limit, offset=offset)


@router.get(
    "/summaries/{summary_id}/download",
    dependencies=[Depends(require_officer_or_admin)],
)
async def download_daily_summary(
    summary_id: str,
    service: Annotated[DailySummaryService, Depends(get_daily_summary_service)],
    user: Annotated[User, Depends(require_officer_or_admin)],
) -> PlainTextResponse:
    summary = await service.get_by_id(summary_id, user.id)
    report_date = (summary.report_date or "unknown").replace(".", "-")
    filename = f"Rail_Madad_Daily_Summary_{report_date}.txt"
    # Prefer DD.MM.YYYY in filename as brief asks Rail_Madad_Daily_Summary_<REPORT_DATE>.txt
    if summary.report_date:
        filename = f"Rail_Madad_Daily_Summary_{summary.report_date}.txt"
    await emit_activity(
        user_id=user.id,
        action="SUMMARY_DOWNLOADED",
        message=f"Daily summary downloaded for {summary.report_date}",
        status="info",
        run_id=summary.run_id,
        metadata={
            "summary_id": summary.summary_id,
            "report_date": summary.report_date,
        },
    )
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}",
    }
    return PlainTextResponse(
        content=summary.text or "",
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )

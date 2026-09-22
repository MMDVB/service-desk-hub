"""Report history: SDCM, AICC, and SLA each get their own table (same shape),
so this one router handles all three via a small lookup instead of copy-pasting
three near-identical route sets."""
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..db.models import SdcmReport, AiccReport, SlaReport
from ..auth import require_auth, require_role, CurrentUser

router = APIRouter(prefix="/api/reports", tags=["reports"])
can_save = require_role("admin", "team_leader", "supervisor")

REPORT_MODELS = {
    "sdcm": SdcmReport,
    "aicc": AiccReport,
    "sla": SlaReport,
}


def get_model(report_type: str):
    model = REPORT_MODELS.get(report_type)
    if not model:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown report type '{report_type}' (use sdcm, aicc, or sla)")
    return model


class ReportSnapshotIn(BaseModel):
    date: date
    summary: dict[str, Any]


@router.post("/{report_type}", status_code=status.HTTP_201_CREATED)
def save_snapshot(
    report_type: str,
    body: ReportSnapshotIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(can_save),
):
    """Upserts one day's summary — re-uploading the same date's report
    just replaces that day's snapshot instead of creating a duplicate."""
    model = get_model(report_type)
    existing = db.query(model).filter(model.report_date == body.date).first()
    if existing:
        existing.summary = body.summary
        existing.uploaded_by = user.id
    else:
        db.add(model(report_date=body.date, summary=body.summary, uploaded_by=user.id))
    db.commit()
    return {"date": body.date, "reportType": report_type, "saved": True}


@router.get("/{report_type}")
def list_snapshots(
    report_type: str,
    from_: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    model = get_model(report_type)
    q = db.query(model)
    if from_:
        q = q.filter(model.report_date >= from_)
    if to:
        q = q.filter(model.report_date <= to)
    rows = q.order_by(model.report_date).all()
    return [{"date": r.report_date.isoformat(), "summary": r.summary} for r in rows]


@router.get("/{report_type}/{report_date}")
def get_snapshot(
    report_type: str,
    report_date: date,
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    model = get_model(report_type)
    row = db.query(model).filter(model.report_date == report_date).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report saved for that date")
    return {"date": row.report_date.isoformat(), "summary": row.summary}

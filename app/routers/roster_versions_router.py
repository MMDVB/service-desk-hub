from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import CurrentUser, require_auth
from ..db.models import RosterVersion
from ..db.session import get_db
from ..permissions import require_permission

router = APIRouter(prefix="/api/roster-versions", tags=["roster-versions"])


def _user_summary(user) -> dict[str, Any] | None:
    if not user:
        return None

    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
        "role": user.role,
    }


def _version_dict(row: RosterVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "versionNumber": row.version_number,
        "status": row.status,
        "snapshot": row.snapshot,
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "createdByUser": _user_summary(row.creator),
        "publishedBy": row.published_by,
        "publishedAt": row.published_at,
        "publishedByUser": _user_summary(row.publisher),
        "updatedBy": row.updated_by,
        "updatedAt": row.updated_at,
        "updatedByUser": _user_summary(row.updater),
    }


class DraftSnapshotIn(BaseModel):
    snapshot: dict[str, Any]


@router.get("/published")
def get_published(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("roster.view")),
):
    row = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "published")
        .order_by(RosterVersion.version_number.desc())
        .first()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No published roster version")
    return _version_dict(row)


@router.get("/draft")
def get_draft(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("roster.draft.view")),
):
    row = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "draft")
        .first()
    )

    published = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "published")
        .order_by(RosterVersion.version_number.desc())
        .first()
    )

    if not row:
        return {
            "exists": False,
            "draft": None,
            "published": _version_dict(published) if published else None,
        }

    return {
        "exists": True,
        "draft": _version_dict(row),
        "published": _version_dict(published) if published else None,
    }

@router.post("/draft", status_code=status.HTTP_201_CREATED)
def create_draft(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("roster.draft.edit")),
):
    existing = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "draft")
        .first()
    )

    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A roster draft already exists",
        )

    latest_published = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "published")
        .order_by(RosterVersion.version_number.desc())
        .first()
    )

    if not latest_published:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No published roster version exists",
        )

    next_number = latest_published.version_number + 1

    row = RosterVersion(
        version_number=next_number,
        status="draft",
        snapshot=latest_published.snapshot,
        created_by=user.id,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return _version_dict(row)
    existing = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "draft")
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A roster draft already exists")

    latest = (
        db.query(RosterVersion)
        .order_by(RosterVersion.version_number.desc())
        .first()
    )
    next_number = (latest.version_number if latest else 0) + 1

    row = RosterVersion(
        version_number=next_number,
        status="draft",
        snapshot=body.snapshot,
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _version_dict(row)


@router.put("/draft")
def update_draft(
    body: DraftSnapshotIn,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("roster.draft.edit")),
):
    row = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "draft")
        .first()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No roster draft exists")

    row.snapshot = body.snapshot
    row.updated_by = user.id
    row.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(row)
    return _version_dict(row)


@router.post("/publish")
def publish_draft(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("roster.publish")),
):
    draft = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "draft")
        .first()
    )

    if not draft:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No roster draft exists",
        )

    published = (
        db.query(RosterVersion)
        .filter(RosterVersion.status == "published")
        .first()
    )

    if published:
        published.status = "archived"

    # Publish the current draft
    draft.status = "published"
    draft.published_by = user.id
    draft.published_at = datetime.now(timezone.utc)

    # Immediately create the next draft from the newly published snapshot
    now = datetime.now(timezone.utc)

    next_draft = RosterVersion(
        version_number=draft.version_number + 1,
        status="draft",
        snapshot=draft.snapshot,
        created_by=user.id,
        updated_by=user.id,
        updated_at=now,
    )

    db.add(next_draft)

    db.commit()
    db.refresh(draft)
    db.refresh(next_draft)

    return {
        "published": _version_dict(draft),
        "draft": _version_dict(next_draft),
    }


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("roster.history.view")),
):
    rows = (
        db.query(RosterVersion)
        .filter(RosterVersion.status.in_(["published", "archived"]))
        .order_by(RosterVersion.version_number.desc())
        .all()
    )
    return [_version_dict(row) for row in rows]

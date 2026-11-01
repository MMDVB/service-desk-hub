"""Persistence and version management for On-Call imports."""

from collections import Counter
from typing import Any

from sqlalchemy import exists, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.db.models import OnCallEntry, OnCallUpload


def recompute_superseded(db: Session) -> None:
    """Mark entries superseded when a newer current upload covers the same duty."""
    newer_upload = aliased(OnCallUpload)
    newer_entry = aliased(OnCallEntry)

    old_uploaded_at = (
        select(OnCallUpload.uploaded_at)
        .where(OnCallUpload.id == OnCallEntry.upload_id)
        .scalar_subquery()
    )

    newer_exists = exists().where(
        newer_entry.upload_id == newer_upload.id,
        newer_upload.is_current.is_(True),
        newer_upload.id != OnCallEntry.upload_id,
        newer_upload.source_group == OnCallEntry.source_group,
        newer_entry.team == OnCallEntry.team,
        newer_entry.duty_date == OnCallEntry.duty_date,
        or_(
            newer_upload.uploaded_at > old_uploaded_at,
            (newer_upload.uploaded_at == old_uploaded_at)
            & (newer_upload.id > OnCallEntry.upload_id),
        ),
    )

    db.execute(
        update(OnCallEntry)
        .values(is_superseded=newer_exists)
        .execution_options(synchronize_session=False)
    )


def save_import(
    db: Session,
    parsed: dict[str, Any],
    *,
    original_name: str,
    source_type: str,
    user_id: int | None,
    stored_name: str = "",
    file_sha256: str = "",
    group_override: str | None = None,
    file_key: str | None = None,
) -> OnCallUpload:
    """Save an import and replace the previous current version of its file key."""
    if source_type not in {"xlsx", "msg", "paste"}:
        raise ValueError("Unsupported On-Call source type.")

    entries = parsed.get("entries") or []
    if not entries:
        raise ValueError("The import contains no On-Call records.")

    source_group = (group_override or parsed.get("source_group") or "Other").strip()
    key = (file_key or original_name).strip().casefold()

    if not source_group or not key:
        raise ValueError("Import group and file key cannot be empty.")

    teams = Counter(
        str(item.get("team") or "Unknown")
        for item in entries
    )

    report = {
        "teams": dict(sorted(teams.items(), key=lambda item: item[0].casefold())),
        "warnings": list(parsed.get("warnings") or []),
    }
    for field in ("sheets", "subject"):
        if parsed.get(field) is not None:
            report[field] = parsed[field]

    upload = OnCallUpload(
        file_key=key,
        original_name=original_name[:255],
        stored_name=stored_name[:150],
        source_type=source_type,
        source_group=source_group[:100],
        period_start=parsed.get("period_start"),
        period_end=parsed.get("period_end"),
        rows_count=len(entries),
        file_sha256=file_sha256,
        report=report,
        is_current=True,
        uploaded_by=user_id,
    )

    try:
        db.query(OnCallUpload).filter(
            OnCallUpload.file_key == key,
            OnCallUpload.is_current.is_(True),
        ).update(
            {OnCallUpload.is_current: False},
            synchronize_session=False,
        )

        db.add(upload)
        db.flush()

        db.add_all([
            OnCallEntry(
                upload_id=upload.id,
                source_group=source_group[:100],
                team=str(item.get("team") or "Unknown")[:150],
                duty_date=item.get("duty_date"),
                shift_start=item.get("shift_start"),
                shift_end=item.get("shift_end"),
                person_name=str(item.get("person_name") or "")[:150],
                role=str(item.get("role") or "")[:50],
                phone=str(item.get("phone") or "")[:30],
                email=str(item.get("email") or "")[:150],
                note=str(item.get("note") or "")[:255],
            )
            for item in entries
        ])

        db.flush()
        recompute_superseded(db)
        db.commit()
        db.refresh(upload)
        return upload

    except Exception:
        db.rollback()
        raise


def activate_upload(db: Session, upload_id: int) -> OnCallUpload:
    """Activate an older version and recalculate superseded entries."""
    upload = (
        db.query(OnCallUpload)
        .filter(OnCallUpload.id == upload_id)
        .with_for_update()
        .one_or_none()
    )

    if upload is None:
        raise ValueError("On-Call upload was not found.")

    try:
        db.query(OnCallUpload).filter(
            OnCallUpload.file_key == upload.file_key,
            OnCallUpload.id != upload.id,
            OnCallUpload.is_current.is_(True),
        ).update(
            {OnCallUpload.is_current: False},
            synchronize_session=False,
        )

        upload.is_current = True
        db.flush()
        recompute_superseded(db)
        db.commit()
        db.refresh(upload)
        return upload

    except Exception:
        db.rollback()
        raise


def delete_upload(db: Session, upload_id: int) -> str:
    """Delete an upload and return its stored filename for filesystem cleanup."""
    upload = (
        db.query(OnCallUpload)
        .filter(OnCallUpload.id == upload_id)
        .with_for_update()
        .one_or_none()
    )

    if upload is None:
        raise ValueError("On-Call upload was not found.")

    stored_name = upload.stored_name or ""

    try:
        db.delete(upload)
        db.flush()
        recompute_superseded(db)
        db.commit()
        return stored_name

    except Exception:
        db.rollback()
        raise

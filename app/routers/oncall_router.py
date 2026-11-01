from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from ..auth import CurrentUser, require_auth
from ..permissions import require_permission, has_permission
from ..db.models import OnCallUpload, OnCallEntry, OnCallSetting
from ..db.session import get_db
from ..services.oncall_import import (
    save_import,
    activate_upload,
    delete_upload,
)
from ..services.oncall_parser import parse_excel, parse_msg, parse_pasted_text


router = APIRouter(prefix="/api/oncall", tags=["On-Call"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "storage" / "oncall" / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILES = 20


@router.get("/access")
def get_oncall_access(
    current: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    keys = (
        "oncall.import",
        "oncall.manual_import",
        "oncall.edit",
        "oncall.delete",
        "oncall.history.view",
        "oncall.manage",
    )
    return {key: has_permission(current, key, db) for key in keys}

XLSX_SIGNATURE = b"PK\x03\x04"
MSG_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


def serialize_entry(entry: OnCallEntry) -> dict:
    return {
        "id": entry.id,
        "upload_id": entry.upload_id,
        "source_group": entry.source_group,
        "team": entry.team,
        "date": entry.duty_date.isoformat(),
        "shift_start": entry.shift_start.strftime("%H:%M") if entry.shift_start else None,
        "shift_end": entry.shift_end.strftime("%H:%M") if entry.shift_end else None,
        "name": entry.person_name,
        "role": entry.role,
        "phone": entry.phone,
        "email": entry.email,
        "note": entry.note,
        "is_superseded": entry.is_superseded,
    }


def serialize_upload(upload: OnCallUpload) -> dict:
    return {
        "id": upload.id,
        "file_key": upload.file_key,
        "original_name": upload.original_name,
        "source_type": upload.source_type,
        "source_group": upload.source_group,
        "period_start": upload.period_start.isoformat() if upload.period_start else None,
        "period_end": upload.period_end.isoformat() if upload.period_end else None,
        "rows_count": upload.rows_count,
        "file_sha256": upload.file_sha256,
        "report": upload.report or {},
        "is_current": upload.is_current,
        "uploaded_by": upload.uploaded_by,
        "uploaded_at": upload.uploaded_at.isoformat() if upload.uploaded_at else None,
    }


async def read_upload(upload: UploadFile) -> tuple[bytes, str]:
    filename = Path(upload.filename or "").name
    suffix = Path(filename).suffix.lower()

    if suffix not in {".xlsx", ".xlsm", ".msg"}:
        raise ValueError("Only .xlsx, .xlsm and .msg files are supported.")

    content = await upload.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("Each file must be 10 MB or smaller.")

    if suffix in {".xlsx", ".xlsm"} and not content.startswith(XLSX_SIGNATURE):
        raise ValueError(f"{filename}: Invalid Excel file.")
    if suffix == ".msg" and not content.startswith(MSG_SIGNATURE):
        raise ValueError(f"{filename}: Invalid Outlook MSG file.")

    return content, suffix


@router.get("/entries")
def list_entries(
    mode: str = "now",
    selected_date: date | None = None,
    group: str | None = None,
    team: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_auth),
):
    if mode not in {"now", "date", "all"}:
        raise HTTPException(400, "Invalid date mode.")

    query = (
        db.query(OnCallEntry)
        .join(OnCallUpload, OnCallEntry.upload_id == OnCallUpload.id)
        .filter(
            OnCallUpload.is_current.is_(True),
            OnCallEntry.is_superseded.is_(False),
        )
    )

    today = date.today()
    now_time = datetime.now().time().replace(tzinfo=None)

    if mode == "date":
        if not selected_date:
            raise HTTPException(400, "A date is required for date mode.")
        query = query.filter(OnCallEntry.duty_date == selected_date)
    elif mode == "now":
        previous_date = today - timedelta(days=1)
        query = query.filter(
            OnCallEntry.duty_date.in_([today, previous_date])
        )

    if group:
        query = query.filter(OnCallEntry.source_group == group)
    if team:
        query = query.filter(OnCallEntry.team == team)

    if q and q.strip():
        term = f"%{q.strip()}%"
        conditions = [
            OnCallEntry.person_name.ilike(term),
            OnCallEntry.team.ilike(term),
            OnCallEntry.email.ilike(term),
            OnCallEntry.role.ilike(term),
            OnCallEntry.source_group.ilike(term),
        ]

        digits = "".join(ch for ch in q if ch.isdigit())
        if len(digits) >= 4:
            normalized = digits.lstrip("0")
            if normalized:
                conditions.append(
                    func.regexp_replace(
                        func.coalesce(OnCallEntry.phone, ""),
                        "[^0-9]", "", "g"
                    ).ilike(f"%{normalized}%")
                )

        query = query.filter(or_(*conditions))

    rows = query.all()

    if mode == "now":
        previous_date = today - timedelta(days=1)
        rows = [
            row for row in rows
            if row.duty_date == today
            or (
                row.duty_date == previous_date
                and row.shift_start is not None
                and row.shift_end is not None
                and row.shift_start >= row.shift_end
                and now_time < row.shift_end
            )
        ]

    def role_order(role):
        value = (role or "").strip().casefold()
        if "main" in value or "primary" in value:
            return 0
        if "backup" in value or "secondary" in value:
            return 2
        return 1

    rows.sort(
        key=lambda row: (
            -row.duty_date.toordinal() if mode == "all"
            else row.duty_date.toordinal(),
            (row.source_group or "").casefold(),
            (row.team or "").casefold(),
            row.shift_start or time.min,
            role_order(row.role),
            (row.person_name or "").casefold(),
            row.id,
        )
    )

    groups = [
        item[0] for item in
        db.query(OnCallEntry.source_group)
        .join(OnCallUpload)
        .filter(OnCallUpload.is_current.is_(True))
        .distinct()
        .order_by(OnCallEntry.source_group)
        .all()
    ]
    teams = [
        item[0] for item in
        db.query(OnCallEntry.team)
        .join(OnCallUpload)
        .filter(OnCallUpload.is_current.is_(True))
        .distinct()
        .order_by(OnCallEntry.team)
        .all()
    ]

    return {
        "entries": [serialize_entry(row) for row in rows],
        "groups": groups,
        "teams": teams,
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_files(
    files: list[UploadFile] = File(...),
    group: str | None = Form(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("oncall.import")),
):
    if not files or len(files) > MAX_FILES:
        raise HTTPException(400, f"Upload between 1 and {MAX_FILES} files.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for upload in files:
        stored_name = f"{uuid.uuid4().hex}{Path(upload.filename or '').suffix.lower()}"
        destination = UPLOAD_DIR / stored_name

        try:
            content, suffix = await read_upload(upload)
            destination.write_bytes(content)

            if suffix == ".msg":
                parsed = parse_msg(destination)
                source_type = "msg"
            else:
                parsed = parse_excel(destination, upload.filename)
                source_type = "xlsx"

            if not parsed.get("entries"):
                raise ValueError("No On-Call records found in this file.")

            saved = save_import(
                db,
                parsed,
                original_name=Path(upload.filename or "upload").name,
                stored_name=stored_name,
                source_type=source_type,
                user_id=user.id,
                file_sha256=hashlib.sha256(content).hexdigest(),
                group_override=group,
            )
            results.append({
                "success": True,
                "upload": serialize_upload(saved),
            })

        except Exception as exc:
            destination.unlink(missing_ok=True)
            results.append({
                "success": False,
                "filename": upload.filename,
                "error": str(exc),
            })
        finally:
            await upload.close()

    return {"results": results}


class ManualImport(BaseModel):
    text: str
    group: str = "SAEI VAS"
    from_date: date | None = None
    to_date: date | None = None
    shift_start: str = "08:00"
    shift_end: str = "08:00"


@router.post("/manual-import", status_code=status.HTTP_201_CREATED)
def manual_import(
    body: ManualImport,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("oncall.manual_import")),
):
    try:
        parsed = parse_pasted_text(
            body.text,
            group=body.group,
            from_date=body.from_date,
            to_date=body.to_date,
            shift_start=body.shift_start,
            shift_end=body.shift_end,
        )

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}.txt"
        (UPLOAD_DIR / stored_name).write_text(body.text, encoding="utf-8")

        key = (
            f"paste:{body.group}:{parsed['period_start']}:"
            f"{parsed['period_end']}"
        ).casefold()

        try:
            saved = save_import(
                db,
                parsed,
                original_name=f"Paste - {body.group}",
                stored_name=stored_name,
                source_type="paste",
                user_id=user.id,
                file_sha256=hashlib.sha256(body.text.encode("utf-8")).hexdigest(),
                group_override=body.group,
                file_key=key,
            )
        except Exception:
            (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
            raise

        return {"upload": serialize_upload(saved)}

    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/history")
def list_history(
    limit: int = 500,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("oncall.history.view")),
):
    limit = max(1, min(limit, 500))
    uploads = (
        db.query(OnCallUpload)
        .options(joinedload(OnCallUpload.uploader))
        .order_by(OnCallUpload.uploaded_at.desc(), OnCallUpload.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            **serialize_upload(upload),
            "uploaded_by_name": (
                upload.uploader.username if upload.uploader else None
            ),
        }
        for upload in uploads
    ]


@router.get("/history/{upload_id}")
def upload_detail(
    upload_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("oncall.history.view")),
):
    upload = (
        db.query(OnCallUpload)
        .options(joinedload(OnCallUpload.entries), joinedload(OnCallUpload.uploader))
        .filter(OnCallUpload.id == upload_id)
        .first()
    )
    if not upload:
        raise HTTPException(404, "Upload not found.")

    return {
        "upload": serialize_upload(upload),
        "uploaded_by_name": upload.uploader.username if upload.uploader else None,
        "entries": [serialize_entry(row) for row in upload.entries],
    }


@router.get("/history/{upload_id}/download")
def download_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("oncall.history.view")),
):
    upload = db.query(OnCallUpload).filter(OnCallUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found.")

    path = UPLOAD_DIR / upload.stored_name
    if not upload.stored_name or not path.is_file():
        raise HTTPException(404, "Original upload file is unavailable.")

    return FileResponse(path, filename=upload.original_name)


@router.post("/history/{upload_id}/activate")
def activate_history_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("oncall.edit")),
):
    try:
        upload = activate_upload(db, upload_id)
        return {"upload": serialize_upload(upload)}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/history/{upload_id}")
def remove_history_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("oncall.delete")),
):
    try:
        stored_name = delete_upload(db, upload_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    if stored_name:
        (UPLOAD_DIR / stored_name).unlink(missing_ok=True)

    return {"success": True}



class OnCallSettingsPayload(BaseModel):
    show_copy: bool = True
    show_call: bool = False


@router.get("/settings")
def get_oncall_settings(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_auth),
):
    settings = {
        row.setting_key: row.setting_value
        for row in db.query(OnCallSetting).all()
    }
    return {
        "show_copy": settings.get("show_copy", True),
        "show_call": settings.get("show_call", False),
    }


@router.put("/settings")
def update_oncall_settings(
    payload: OnCallSettingsPayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission("oncall.manage")),
):
    values = {
        "show_copy": payload.show_copy,
        "show_call": payload.show_call,
    }

    try:
        for key, value in values.items():
            setting = db.get(OnCallSetting, key)
            if setting is None:
                setting = OnCallSetting(
                    setting_key=key,
                    setting_value=value,
                    updated_by=user.id,
                )
                db.add(setting)
            else:
                setting.setting_value = value
                setting.updated_by = user.id

        db.commit()
        return values
    except Exception:
        db.rollback()
        raise

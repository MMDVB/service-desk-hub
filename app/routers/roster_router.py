from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..db.session import get_db
from ..db.models import RosterColumn, TeamMember, RosterEntry, RosterEntryMember, Holiday, AuditLog
from ..auth import require_auth, require_role, CurrentUser

router = APIRouter(prefix="/api/roster", tags=["roster"])
can_edit = require_role("admin", "leadership")


def log_action(db: Session, user_id: int, action: str, detail: dict):
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))


# ---------- Columns ----------
class ColumnIn(BaseModel):
    key: str
    labelEn: str
    labelFa: Optional[str] = None
    color: Optional[str] = "#E2E8F0"
    textColor: Optional[str] = "#334155"
    isMulti: Optional[bool] = True


class ColumnPatch(BaseModel):
    labelEn: Optional[str] = None
    labelFa: Optional[str] = None
    color: Optional[str] = None
    textColor: Optional[str] = None


@router.get("/columns")
def list_columns(db: Session = Depends(get_db), _=Depends(require_auth)):
    cols = db.query(RosterColumn).order_by(RosterColumn.sort_order).all()
    return [
        {
            "id": c.id, "key": c.key, "label_en": c.label_en, "label_fa": c.label_fa,
            "color": c.color, "text_color": c.text_color, "is_multi": c.is_multi,
            "is_builtin": c.is_builtin, "sort_order": c.sort_order,
        }
        for c in cols
    ]


@router.post("/columns", status_code=status.HTTP_201_CREATED)
def add_column(body: ColumnIn, db: Session = Depends(get_db), user: CurrentUser = Depends(can_edit)):
    max_order = db.query(RosterColumn).count()
    col = RosterColumn(
        key=body.key, label_en=body.labelEn, label_fa=body.labelFa or body.labelEn,
        color=body.color, text_color=body.textColor, is_multi=body.isMulti,
        is_builtin=False, sort_order=max_order + 1,
    )
    db.add(col)
    log_action(db, user.id, "roster_column_add", {"key": body.key})
    db.commit()
    db.refresh(col)
    return col


@router.patch("/columns/{column_id}")
def update_column(column_id: int, body: ColumnPatch, db: Session = Depends(get_db), user: CurrentUser = Depends(can_edit)):
    col = db.query(RosterColumn).filter(RosterColumn.id == column_id).first()
    if not col:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Column not found")
    if body.labelEn is not None:
        col.label_en = body.labelEn
    if body.labelFa is not None:
        col.label_fa = body.labelFa
    if body.color is not None:
        col.color = body.color
    if body.textColor is not None:
        col.text_color = body.textColor
    log_action(db, user.id, "roster_column_update", {"id": column_id})
    db.commit()
    db.refresh(col)
    return col


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(column_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(can_edit)):
    col = db.query(RosterColumn).filter(RosterColumn.id == column_id).first()
    if not col:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Column not found")
    if col.is_builtin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Built-in columns cannot be deleted")
    db.delete(col)
    log_action(db, user.id, "roster_column_delete", {"id": column_id})
    db.commit()


# ---------- Team members ----------
class MemberIn(BaseModel):
    fullName: str
    username: Optional[str] = None


@router.get("/team")
def list_team(db: Session = Depends(get_db), _=Depends(require_auth)):
    members = db.query(TeamMember).filter(TeamMember.is_active.is_(True)).order_by(TeamMember.full_name).all()
    return [{"id": m.id, "full_name": m.full_name, "username": m.username} for m in members]


@router.post("/team", status_code=status.HTTP_201_CREATED)
def add_member(body: MemberIn, db: Session = Depends(get_db), _=Depends(can_edit)):
    member = TeamMember(full_name=body.fullName, username=body.username)
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id, "full_name": member.full_name, "username": member.username}


@router.delete("/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: int, db: Session = Depends(get_db), _=Depends(can_edit)):
    # Soft delete — keeps historical roster entries intact.
    member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
    if member:
        member.is_active = False
        db.commit()


# ---------- Entries ----------
@router.get("/entries")
def get_entries(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_auth),
):
    rows = (
        db.query(RosterEntry)
        .options(joinedload(RosterEntry.members).joinedload(RosterEntryMember.team_member))
        .join(RosterColumn, RosterEntry.column_id == RosterColumn.id)
        .filter(RosterEntry.entry_date.between(from_, to))
        .order_by(RosterEntry.id)
        .all()
    )
    col_by_id = {c.id: c for c in db.query(RosterColumn).all()}

    days: dict[str, dict] = defaultdict(dict)
    for entry in rows:
        col = col_by_id[entry.column_id]
        date_key = entry.entry_date.isoformat()
        names = [m.team_member.full_name for m in entry.members if m.team_member] or (
            [entry.free_text] if entry.free_text else []
        )
        if not names:
            continue
        if col.is_multi:
            days[date_key].setdefault(col.key, []).extend(names)
        else:
            days[date_key][col.key] = names[0]
    return days


class EntryPut(BaseModel):
    date: date
    columnKey: str
    names: list[str]


@router.put("/entries")
def put_entry(body: EntryPut, db: Session = Depends(get_db), user: CurrentUser = Depends(can_edit)):
    column = db.query(RosterColumn).filter(RosterColumn.key == body.columnKey).first()
    if not column:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown column")

    # Replace whatever was assigned before for this date+column — simplest, safest way to
    # sync from the frontend's cell editor, which already tracks the whole list client-side.
    existing = db.query(RosterEntry).filter(
        RosterEntry.entry_date == body.date, RosterEntry.column_id == column.id
    ).all()
    for e in existing:
        db.delete(e)
    db.flush()

    final_names = body.names if column.is_multi else body.names[:1]
    for name in final_names:
        member = db.query(TeamMember).filter(
            TeamMember.full_name == name, TeamMember.is_active.is_(True)
        ).first()
        entry = RosterEntry(entry_date=body.date, column_id=column.id, free_text=None if member else name)
        db.add(entry)
        db.flush()
        if member:
            db.add(RosterEntryMember(entry_id=entry.id, team_member_id=member.id))

    log_action(db, user.id, "roster_entry_update", {"date": body.date.isoformat(), "columnKey": body.columnKey, "names": body.names})
    db.commit()
    return {"date": body.date, "columnKey": body.columnKey, "names": final_names}


# ---------- Holidays ----------
class HolidayIn(BaseModel):
    date: date
    label: Optional[str] = "Official holiday"


@router.get("/holidays")
def list_holidays(db: Session = Depends(get_db), _=Depends(require_auth)):
    rows = db.query(Holiday).order_by(Holiday.holiday_date).all()
    return [{"date": h.holiday_date.isoformat(), "label": h.label} for h in rows]


@router.post("/holidays", status_code=status.HTTP_201_CREATED)
def add_holiday(body: HolidayIn, db: Session = Depends(get_db), _=Depends(can_edit)):
    existing = db.query(Holiday).filter(Holiday.holiday_date == body.date).first()
    if existing:
        existing.label = body.label
    else:
        db.add(Holiday(holiday_date=body.date, label=body.label))
    db.commit()
    return {"date": body.date, "label": body.label}


@router.delete("/holidays/{holiday_date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(holiday_date: date, db: Session = Depends(get_db), _=Depends(can_edit)):
    db.query(Holiday).filter(Holiday.holiday_date == holiday_date).delete()
    db.commit()

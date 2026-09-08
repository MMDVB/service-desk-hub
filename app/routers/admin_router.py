"""Admin management overview. Read-only operational metrics for admins."""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..db.models import User, TeamMember, RosterEntry, Holiday, AuditLog
from ..auth import require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/overview")
def overview(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    users = db.query(User).all()
    by_role = {"admin": 0, "leadership": 0, "agent": 0}
    for u in users:
        role = "leadership" if u.role == "supervisor" else u.role
        by_role[role] = by_role.get(role, 0) + 1
    active_users = sum(1 for u in users if u.is_active)
    active_members = db.query(func.count(TeamMember.id)).filter(TeamMember.is_active.is_(True)).scalar() or 0
    today_entries = db.query(func.count(RosterEntry.id)).filter(RosterEntry.entry_date == date.today()).scalar() or 0
    holidays = db.query(func.count(Holiday.id)).filter(Holiday.holiday_date >= date.today()).scalar() or 0
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(8).all()
    user_names = {u.id: u.display_name for u in users}
    activity = [{
        "id": x.id, "action": x.action, "detail": x.detail or {},
        "user": user_names.get(x.user_id, "System"), "createdAt": x.created_at.isoformat() if x.created_at else None
    } for x in logs]
    return {
        "users": {"total": len(users), "active": active_users, "inactive": len(users)-active_users},
        "roles": by_role,
        "team": {"activeMembers": active_members},
        "roster": {"todayEntries": today_entries},
        "upcomingHolidays": holidays,
        "recentActivity": activity
    }

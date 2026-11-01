"""Administration overview and audit log endpoints."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..db.models import AuditLog, Holiday, RosterEntry, TeamMember, User
from ..db.session import get_db
from ..permissions import has_permission, require_permission


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("dashboard.view")),
):
    users = []

    # User statistics are only exposed to admins.
    if current.role == "admin":
        users = db.query(User).all()

    by_role = {
        "admin": 0,
        "team_leader": 0,
        "supervisor": 0,
        "engineer": 0,
    }

    if current.role == "admin":
        for user in users:
            by_role[user.role] = by_role.get(user.role, 0) + 1

    active_members_query = db.query(TeamMember).filter(
        TeamMember.is_active.is_(True)
    )

    active_members = active_members_query.count()

    today_entries = (
        db.query(func.count(RosterEntry.id))
        .filter(RosterEntry.entry_date == date.today())
        .scalar()
        or 0
    )

    upcoming_holidays = (
        db.query(func.count(Holiday.id))
        .filter(Holiday.holiday_date >= date.today())
        .scalar()
        or 0
    )

    activity = []

    if has_permission(current, "audit.view", db):
        logs = (
            db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(8)
            .all()
        )

        user_names = {
            user.id: user.display_name
            for user in db.query(User).all()
        }

        activity = [
            {
                "id": log.id,
                "action": log.action,
                "detail": log.detail or {},
                "user": user_names.get(log.user_id, "System"),
                "createdAt": (
                    log.created_at.isoformat()
                    if log.created_at
                    else None
                ),
            }
            for log in logs
        ]

    result = {
        "roles": by_role,
        "team": {
            "activeMembers": active_members,
        },
        "roster": {
            "todayEntries": today_entries,
        },
        "upcomingHolidays": upcoming_holidays,
        "recentActivity": activity,
    }

    if current.role == "admin":
        active_users = sum(
            1 for user in users if user.is_active
        )

        result["users"] = {
            "total": len(users),
            "active": active_users,
            "inactive": len(users) - active_users,
        }

    return result


@router.get("/audit")
def list_audit_logs(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(
        require_permission("audit.view")
    ),
):
    logs = (
        db.query(AuditLog, User)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )

    return [
        {
            "id": log.id,
            "user": (
                {
                    "id": user.id,
                    "username": user.username,
                    "displayName": user.display_name,
                    "role": user.role,
                }
                if user
                else None
            ),
            "action": log.action,
            "detail": log.detail,
            "createdAt": (
                log.created_at.isoformat()
                if log.created_at
                else None
            ),
        }
        for log, user in logs
    ]

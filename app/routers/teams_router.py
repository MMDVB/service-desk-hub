"""Team management API."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..db.models import Team, TeamAssignment, TeamMember, User
from ..db.session import get_db
from ..permissions import require_permission
from ..audit import write_audit


router = APIRouter(prefix="/api/teams", tags=["teams"])


class TeamCreate(BaseModel):
    name: str
    supervisorId: int | None = None
    description: str | None = None
    isActive: bool = True


class TeamUpdate(BaseModel):
    name: str | None = None
    supervisorId: int | None = None
    description: str | None = None
    isActive: bool | None = None


def is_manager(user: CurrentUser) -> bool:
    return user.role in ("admin", "team_leader")


def can_access_team(current: CurrentUser, team: Team) -> bool:
    if is_manager(current):
        return True
    return (
        current.role == "supervisor"
        and team.supervisor_id == current.id
    )


def serialize_team(team: Team):
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "isActive": team.is_active,
        "supervisor": (
            {
                "id": team.supervisor.id,
                "username": team.supervisor.username,
                "displayName": team.supervisor.display_name,
                "role": team.supervisor.role,
            }
            if team.supervisor
            else None
        ),
        "memberCount": len(team_assignments(team)),
    }


def team_assignments(team: Team):
    # SQLAlchemy relationship is intentionally queried through the DB
    # in endpoints; this helper exists only for serialization compatibility.
    return []


def load_team(db: Session, team_id: int) -> Team:
    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    return team


def validate_supervisor(db: Session, supervisor_id: int | None):
    if supervisor_id is None:
        return None

    supervisor = (
        db.query(User)
        .filter(
            User.id == supervisor_id,
            User.is_active.is_(True),
        )
        .first()
    )

    if not supervisor or supervisor.role != "supervisor":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supervisor must be an active supervisor user",
        )

    return supervisor


@router.get("")
def list_teams(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.view")),
):
    query = db.query(Team).order_by(Team.name)

    if current.role == "supervisor":
        query = query.filter(Team.supervisor_id == current.id)

    teams = query.all()

    result = []

    for team in teams:
        count = (
            db.query(TeamAssignment)
            .filter(TeamAssignment.team_id == team.id)
            .count()
        )

        result.append({
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "isActive": team.is_active,
            "supervisor": (
                {
                    "id": team.supervisor.id,
                    "username": team.supervisor.username,
                    "displayName": team.supervisor.display_name,
                    "role": team.supervisor.role,
                }
                if team.supervisor
                else None
            ),
            "memberCount": count,
        })

    return result


@router.get("/members")
def list_team_members(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.view")),
):
    members = (
        db.query(TeamMember)
        .filter(TeamMember.is_active.is_(True))
        .order_by(TeamMember.full_name)
        .all()
    )

    return [
        {
            "id": m.id,
            "fullName": m.full_name,
            "username": m.username,
            "userId": m.user_id,
            "isActive": m.is_active,
        }
        for m in members
    ]


@router.get("/supervisors")
def list_supervisors(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.view")),
):
    users = (
        db.query(User)
        .filter(
            User.role == "supervisor",
            User.is_active.is_(True),
        )
        .order_by(User.display_name)
        .all()
    )

    return [
        {
            "id": u.id,
            "username": u.username,
            "displayName": u.display_name,
            "role": u.role,
        }
        for u in users
    ]


@router.get("/{team_id}")
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.view")),
):
    team = load_team(db, team_id)

    if not can_access_team(current, team):
        raise HTTPException(status_code=403, detail="Access denied")

    assignments = (
        db.query(TeamAssignment, TeamMember)
        .join(
            TeamMember,
            TeamMember.id == TeamAssignment.team_member_id,
        )
        .filter(TeamAssignment.team_id == team.id)
        .order_by(TeamMember.full_name)
        .all()
    )

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "isActive": team.is_active,
        "supervisor": (
            {
                "id": team.supervisor.id,
                "username": team.supervisor.username,
                "displayName": team.supervisor.display_name,
                "role": team.supervisor.role,
            }
            if team.supervisor
            else None
        ),
        "members": [
            {
                "id": member.id,
                "fullName": member.full_name,
                "username": member.username,
                "userId": member.user_id,
                "isActive": member.is_active,
            }
            for _, member in assignments
        ],
    }


@router.post("")
def create_team(
    body: TeamCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.create")),
):
    if current.role not in ("admin", "team_leader"):
        raise HTTPException(status_code=403, detail="Access denied")

    name = body.name.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Team name is required")

    if db.query(Team).filter(Team.name == name).first():
        raise HTTPException(status_code=409, detail="Team already exists")

    validate_supervisor(db, body.supervisorId)

    team = Team(
        name=name,
        supervisor_id=body.supervisorId,
        description=body.description,
        is_active=body.isActive,
    )

    db.add(team)
    db.flush()

    write_audit(
        db,
        current.id,
        "TEAM_CREATED",
        {
            "teamId": team.id,
            "name": team.name,
            "supervisorId": team.supervisor_id,
        },
    )

    db.commit()
    db.refresh(team)

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "isActive": team.is_active,
        "supervisorId": team.supervisor_id,
    }


@router.patch("/{team_id}")
def update_team(
    team_id: int,
    body: TeamUpdate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.edit")),
):
    team = load_team(db, team_id)

    if not can_access_team(current, team):
        raise HTTPException(status_code=403, detail="Access denied")

    old_values = {
        "name": team.name,
        "supervisorId": team.supervisor_id,
        "description": team.description,
        "isActive": team.is_active,
    }

    if body.name is not None:
        name = body.name.strip()

        if not name:
            raise HTTPException(status_code=400, detail="Team name is required")

        duplicate = (
            db.query(Team)
            .filter(Team.name == name, Team.id != team.id)
            .first()
        )

        if duplicate:
            raise HTTPException(status_code=409, detail="Team already exists")

        team.name = name

    if body.supervisorId is not None:
        validate_supervisor(db, body.supervisorId)
        team.supervisor_id = body.supervisorId

    if body.description is not None:
        team.description = body.description

    if body.isActive is not None:
        team.is_active = body.isActive

    new_values = {
        "name": team.name,
        "supervisorId": team.supervisor_id,
        "description": team.description,
        "isActive": team.is_active,
    }

    write_audit(
        db,
        current.id,
        "TEAM_UPDATED",
        {
            "teamId": team.id,
            "old": old_values,
            "new": new_values,
        },
    )

    db.commit()
    db.refresh(team)

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "isActive": team.is_active,
        "supervisorId": team.supervisor_id,
    }


@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.delete")),
):
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    team = load_team(db, team_id)

    write_audit(
        db,
        current.id,
        "TEAM_DELETED",
        {
            "teamId": team.id,
            "name": team.name,
            "supervisorId": team.supervisor_id,
        },
    )

    db.delete(team)
    db.commit()

    return {"ok": True}


@router.post("/{team_id}/members/{member_id}")
def add_member(
    team_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.members.manage")),
):
    team = load_team(db, team_id)

    if not can_access_team(current, team):
        raise HTTPException(status_code=403, detail="Access denied")

    member = (
        db.query(TeamMember)
        .filter(
            TeamMember.id == member_id,
            TeamMember.is_active.is_(True),
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=404,
            detail="Team member not found",
        )

    existing = (
        db.query(TeamAssignment)
        .filter(
            TeamAssignment.team_id == team.id,
            TeamAssignment.team_member_id == member.id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Member already assigned to this team",
        )

    db.add(
        TeamAssignment(
            team_id=team.id,
            team_member_id=member.id,
        )
    )

    write_audit(
        db,
        current.id,
        "TEAM_MEMBER_ADDED",
        {
            "teamId": team.id,
            "memberId": member.id,
            "memberName": member.full_name,
        },
    )

    db.commit()

    return {
        "ok": True,
        "teamId": team.id,
        "memberId": member.id,
    }


@router.delete("/{team_id}/members/{member_id}")
def remove_member(
    team_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("teams.members.manage")),
):
    team = load_team(db, team_id)

    if not can_access_team(current, team):
        raise HTTPException(status_code=403, detail="Access denied")

    assignment = (
        db.query(TeamAssignment)
        .filter(
            TeamAssignment.team_id == team.id,
            TeamAssignment.team_member_id == member_id,
        )
        .first()
    )

    if assignment:
        member = (
            db.query(TeamMember)
            .filter(TeamMember.id == member_id)
            .first()
        )

        write_audit(
            db,
            current.id,
            "TEAM_MEMBER_REMOVED",
            {
                "teamId": team.id,
                "memberId": member_id,
                "memberName": member.full_name if member else None,
            },
        )

        db.delete(assignment)
        db.commit()

    return {"ok": True}

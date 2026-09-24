from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from ..db.session import get_db
from ..db.models import TeamMember, User, TeamAssignment, Team
from ..auth import require_role, CurrentUser
from ..audit import write_audit


router = APIRouter(prefix="/api/members", tags=["members"])

admin_only = require_role("admin")


def serialize_member(member: TeamMember) -> dict:
    return {
        "id": member.id,
        "fullName": member.full_name,
        "username": member.username,
        "isActive": member.is_active,
        "userId": member.user_id,
        "linkedUser": (
            {
                "id": member.user.id,
                "username": member.user.username,
                "displayName": member.user.display_name,
                "role": member.user.role,
                "isActive": member.user.is_active,
            }
            if member.user
            else None
        ),
    }


@router.get("")
def list_members(
    active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(admin_only),
):
    query = (
        db.query(TeamMember)
        .options(joinedload(TeamMember.user))
        .order_by(TeamMember.full_name)
    )

    if active is not None:
        query = query.filter(TeamMember.is_active.is_(active))

    members = query.all()

    result = []

    for member in members:
        teams = (
            db.query(Team)
            .join(
                TeamAssignment,
                TeamAssignment.team_id == Team.id,
            )
            .filter(
                TeamAssignment.team_member_id == member.id,
                Team.is_active.is_(True),
            )
            .order_by(Team.name)
            .all()
        )

        item = serialize_member(member)
        item["teams"] = [
            {
                "id": team.id,
                "name": team.name,
            }
            for team in teams
        ]

        result.append(item)

    return result


@router.get("/{member_id}")
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(admin_only),
):
    member = (
        db.query(TeamMember)
        .options(joinedload(TeamMember.user))
        .filter(TeamMember.id == member_id)
        .first()
    )

    if not member:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Member not found",
        )

    teams = (
        db.query(Team)
        .join(
            TeamAssignment,
            TeamAssignment.team_id == Team.id,
        )
        .filter(TeamAssignment.team_member_id == member.id)
        .order_by(Team.name)
        .all()
    )

    result = serialize_member(member)
    result["teams"] = [
        {
            "id": team.id,
            "name": team.name,
            "isActive": team.is_active,
        }
        for team in teams
    ]

    return result


class MemberCreate(BaseModel):
    fullName: str = Field(min_length=1, max_length=120)
    username: Optional[str] = Field(default=None, max_length=80)
    userId: Optional[int] = None
    isActive: bool = True


@router.post("", status_code=status.HTTP_201_CREATED)
def create_member(
    body: MemberCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(admin_only),
):
    if body.userId is not None:
        user = db.query(User).filter(User.id == body.userId).first()

        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "User not found",
            )

        existing = (
            db.query(TeamMember)
            .filter(TeamMember.user_id == body.userId)
            .first()
        )

        if existing:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This user is already linked to a Member",
            )

    member = TeamMember(
        full_name=body.fullName,
        username=body.username,
        is_active=body.isActive,
        user_id=body.userId,
    )

    db.add(member)
    db.flush()

    write_audit(
        db,
        current.id,
        "MEMBER_CREATED",
        {
            "memberId": member.id,
            "fullName": member.full_name,
            "userId": member.user_id,
        },
    )

    db.commit()
    db.refresh(member)

    return serialize_member(member)


class MemberPatch(BaseModel):
    fullName: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=120,
    )
    username: Optional[str] = Field(
        default=None,
        max_length=80,
    )
    userId: Optional[int] = None
    isActive: Optional[bool] = None


@router.patch("/{member_id}")
def update_member(
    member_id: int,
    body: MemberPatch,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(admin_only),
):
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id
    ).first()

    if not member:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Member not found",
        )

    if body.userId is not None and body.userId != member.user_id:
        user = db.query(User).filter(User.id == body.userId).first()

        if not user:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "User not found",
            )

        existing = (
            db.query(TeamMember)
            .filter(
                TeamMember.user_id == body.userId,
                TeamMember.id != member.id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This user is already linked to another Member",
            )

        member.user_id = body.userId

    if body.fullName is not None:
        member.full_name = body.fullName

    if body.username is not None:
        member.username = body.username

    if body.isActive is not None:
        member.is_active = body.isActive

    write_audit(
        db,
        current.id,
        "MEMBER_UPDATED",
        {
            "memberId": member.id,
            "userId": member.user_id,
        },
    )

    db.commit()
    db.refresh(member)

    return serialize_member(member)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_member(
    member_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(admin_only),
):
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id
    ).first()

    if not member:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Member not found",
        )

    member.is_active = False

    write_audit(
        db,
        current.id,
        "MEMBER_DEACTIVATED",
        {
            "memberId": member.id,
            "userId": member.user_id,
        },
    )

    db.commit()

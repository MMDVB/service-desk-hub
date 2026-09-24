"""User management: list/create/update/deactivate accounts. Every route here
is admin-only — this is the panel that decides who else can log in at all."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..db.models import User, TeamMember, TeamAssignment
from ..auth import require_auth, require_role, hash_password, CurrentUser
from ..audit import write_audit

router = APIRouter(prefix="/api/users", tags=["users"])
admin_only = require_role("admin")


def serialize(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "displayName": u.display_name,
        "role": u.role, "isActive": u.is_active,
    }


@router.get("")
def list_users(db: Session = Depends(get_db), _=Depends(admin_only)):
    users = db.query(User).order_by(User.username).all()
    return [serialize(u) for u in users]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    displayName: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    role: str = Field(pattern="^(admin|team_leader|supervisor|agent)$")
    addToMembers: bool = False


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db), current: CurrentUser = Depends(admin_only)):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken")
    user = User(
        username=body.username, display_name=body.displayName,
        password_hash=hash_password(body.password), role=body.role, is_active=True,
    )
    db.add(user)
    db.flush()

    member = None
    if body.addToMembers:
        member = TeamMember(
            full_name=user.display_name,
            username=user.username,
            is_active=user.is_active,
            user_id=user.id,
        )
        db.add(member)
        db.flush()

        write_audit(
            db,
            current.id,
            "MEMBER_CREATED",
            {
                "memberId": member.id,
                "userId": user.id,
                "fullName": member.full_name,
                "username": member.username,
            },
        )

    write_audit(
        db,
        current.id,
        "USER_CREATED",
        {
            "userId": user.id,
            "username": user.username,
            "role": user.role,
            "addToMembers": body.addToMembers,
            "memberId": member.id if member else None,
        },
    )

    db.commit()
    db.refresh(user)
    return serialize(user)


class UserPatch(BaseModel):
    displayName: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(admin|team_leader|supervisor|agent)$")
    isActive: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)
    addToMembers: Optional[bool] = None


@router.patch("/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), current: CurrentUser = Depends(admin_only)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == current.id and body.isActive is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't deactivate your own account")
    if user.id == current.id and body.role and body.role != "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't remove your own admin role")

    old_values = {
        "displayName": user.display_name,
        "role": user.role,
        "isActive": user.is_active,
    }

    if body.displayName is not None:
        user.display_name = body.displayName
    if body.role is not None:
        user.role = body.role
    if body.isActive is not None:
        user.is_active = body.isActive
    if body.password:
        user.password_hash = hash_password(body.password)

    member = db.query(TeamMember).filter(TeamMember.user_id == user.id).first()

    if body.addToMembers is True:
        if member:
            member.is_active = True
            member.full_name = user.display_name
            member.username = user.username
        else:
            member = TeamMember(
                full_name=user.display_name,
                username=user.username,
                is_active=True,
                user_id=user.id,
            )
            db.add(member)
            db.flush()

    elif body.addToMembers is False and member:
        assignment = (
            db.query(TeamAssignment)
            .filter(TeamAssignment.team_member_id == member.id)
            .first()
        )

        if assignment:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Remove this member from the team before disabling the Member status",
            )

        member.is_active = False

    if member:
        if body.displayName is not None:
            member.full_name = user.display_name
        if body.isActive is not None:
            member.is_active = user.is_active
        member.username = user.username

    new_values = {
        "displayName": user.display_name,
        "role": user.role,
        "isActive": user.is_active,
    }

    write_audit(
        db,
        current.id,
        "USER_UPDATED",
        {
            "userId": user.id,
            "username": user.username,
            "old": old_values,
            "new": new_values,
            "passwordChanged": bool(body.password),
            "memberLinked": bool(member),
            "memberActive": member.is_active if member else None,
        },
    )

    db.commit()
    db.refresh(user)
    return serialize(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(user_id: int, db: Session = Depends(get_db), current: CurrentUser = Depends(admin_only)):
    if user_id == current.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't deactivate your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_active = False

        member = db.query(TeamMember).filter(TeamMember.user_id == user.id).first()
        if member:
            member.is_active = False

        write_audit(
            db,
            current.id,
            "USER_DEACTIVATED",
            {
                "userId": user.id,
                "username": user.username,
                "memberId": member.id if member else None,
            },
        )

        db.commit()

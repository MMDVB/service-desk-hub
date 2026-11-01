"""Permission management API."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..db.models import (
    Permission,
    RolePermission,
    User,
    UserPermissionOverride,
)
from ..db.session import get_db
from ..permissions import has_permission, require_permission
from ..audit import write_audit


router = APIRouter(prefix="/api/permissions", tags=["permissions"])

ROLES = ("admin", "team_leader", "supervisor", "engineer")


@router.get("")
def list_permissions(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("roles.view")),
):
    permissions = (
        db.query(Permission)
        .filter(Permission.is_active.is_(True))
        .order_by(Permission.category, Permission.permission_key)
        .all()
    )

    return [
        {
            "id": p.id,
            "key": p.permission_key,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "isActive": p.is_active,
        }
        for p in permissions
    ]


@router.get("/roles")
def list_role_permissions(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("roles.view")),
):
    permissions = (
        db.query(Permission)
        .filter(Permission.is_active.is_(True))
        .order_by(Permission.category, Permission.permission_key)
        .all()
    )

    result = {}

    for role in ROLES:
        rows = (
            db.query(RolePermission)
            .filter(RolePermission.role == role)
            .all()
        )

        allowed_map = {row.permission_id: row.allowed for row in rows}

        result[role] = [
            {
                "permissionId": permission.id,
                "key": permission.permission_key,
                "allowed": (
                    True
                    if role == "admin"
                    else bool(allowed_map.get(permission.id, False))
                ),
            }
            for permission in permissions
        ]

    return result


class RolePermissionUpdate(BaseModel):
    permissionId: int
    allowed: bool


@router.put("/roles/{role}")
def update_role_permission(
    role: str,
    body: RolePermissionUpdate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("roles.manage")),
):
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    # Admin always has full access and cannot be reduced.
    if role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin permissions cannot be changed",
        )

    permission = (
        db.query(Permission)
        .filter(
            Permission.id == body.permissionId,
            Permission.is_active.is_(True),
        )
        .first()
    )

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )

    row = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    old_value = row.allowed if row else False

    if row:
        row.allowed = body.allowed
    else:
        row = RolePermission(
            role=role,
            permission_id=permission.id,
            allowed=body.allowed,
        )
        db.add(row)

    write_audit(
        db,
        current.id,
        "ROLE_PERMISSION_CHANGED",
        {
            "role": role,
            "permissionId": permission.id,
            "key": permission.permission_key,
            "oldAllowed": old_value,
            "allowed": body.allowed,
        },
    )

    db.commit()

    return {
        "role": role,
        "permissionId": permission.id,
        "key": permission.permission_key,
        "oldAllowed": old_value,
        "allowed": body.allowed,
    }


@router.get("/users/{user_id}")
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("roles.view")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    permissions = (
        db.query(Permission)
        .filter(Permission.is_active.is_(True))
        .order_by(Permission.category, Permission.permission_key)
        .all()
    )

    overrides = (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.user_id == user_id)
        .all()
    )

    override_map = {
        row.permission_id: row.allowed
        for row in overrides
    }

    role_rows = (
        db.query(RolePermission)
        .filter(RolePermission.role == user.role)
        .all()
    )

    role_map = {
        row.permission_id: row.allowed
        for row in role_rows
    }

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "displayName": user.display_name,
            "role": user.role,
            "isActive": user.is_active,
        },
        "permissions": [
            {
                "permissionId": permission.id,
                "key": permission.permission_key,
                "roleAllowed": (
                    True
                    if user.role == "admin"
                    else bool(role_map.get(permission.id, False))
                ),
                "override": override_map.get(permission.id),
                "effective": (
                    True
                    if user.role == "admin"
                    else (
                        override_map[permission.id]
                        if permission.id in override_map
                        else bool(role_map.get(permission.id, False))
                    )
                ),
            }
            for permission in permissions
        ],
    }


class PermissionOverride(BaseModel):
    permissionId: int
    allowed: bool


@router.put("/users/{user_id}")
def set_user_permission(
    user_id: int,
    body: PermissionOverride,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("roles.manage")),
):
    if current.role == "admin" and user_id == current.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin permissions cannot be overridden",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    permission = (
        db.query(Permission)
        .filter(
            Permission.id == body.permissionId,
            Permission.is_active.is_(True),
        )
        .first()
    )

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )

    override = (
        db.query(UserPermissionOverride)
        .filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_id == permission.id,
        )
        .first()
    )

    old_value = override.allowed if override else None

    if override:
        override.allowed = body.allowed
    else:
        db.add(
            UserPermissionOverride(
                user_id=user_id,
                permission_id=permission.id,
                allowed=body.allowed,
            )
        )

    write_audit(
        db,
        current.id,
        "USER_PERMISSION_OVERRIDE_CHANGED",
        {
            "targetUserId": user_id,
            "permissionId": permission.id,
            "key": permission.permission_key,
            "oldAllowed": old_value,
            "allowed": body.allowed,
        },
    )

    db.commit()

    return {
        "userId": user_id,
        "permissionId": permission.id,
        "key": permission.permission_key,
        "oldAllowed": old_value,
        "allowed": body.allowed,
    }


@router.delete("/users/{user_id}/{permission_id}")
def remove_user_permission_override(
    user_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_permission("roles.manage")),
):
    if current.role == "admin" and user_id == current.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin permissions cannot be overridden",
        )

    override = (
        db.query(UserPermissionOverride)
        .filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_id == permission_id,
        )
        .first()
    )

    if override:
        write_audit(
            db,
            current.id,
            "USER_PERMISSION_OVERRIDE_REMOVED",
            {
                "targetUserId": user_id,
                "permissionId": permission_id,
            },
        )

        db.delete(override)
        db.commit()

    return {"ok": True}

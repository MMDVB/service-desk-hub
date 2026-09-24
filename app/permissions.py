"""Central permission engine for Service Desk Hub."""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .auth import CurrentUser, require_auth
from .db.models import Permission, RolePermission, UserPermissionOverride
from .db.session import get_db


def has_permission(
    user: CurrentUser,
    permission_key: str,
    db: Session,
) -> bool:
    """
    Resolve a user's effective permission.

    Priority:
    1. Admin always has full access.
    2. Explicit user override wins.
    3. Otherwise use the user's role permission.
    """

    if user.role == "admin":
        return True

    permission = (
        db.query(Permission)
        .filter(
            Permission.permission_key == permission_key,
            Permission.is_active.is_(True),
        )
        .first()
    )

    if not permission:
        return False

    override = (
        db.query(UserPermissionOverride)
        .filter(
            UserPermissionOverride.user_id == user.id,
            UserPermissionOverride.permission_id == permission.id,
        )
        .first()
    )

    if override is not None:
        return override.allowed

    role_permission = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == user.role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    return bool(role_permission and role_permission.allowed)


def require_permission(permission_key: str):
    """
    FastAPI dependency factory for permission-protected endpoints.
    """

    def dependency(
        current: CurrentUser = Depends(require_auth),
        db: Session = Depends(get_db),
    ) -> CurrentUser:

        if not has_permission(current, permission_key, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_key}",
            )

        return current

    return dependency

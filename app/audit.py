from sqlalchemy.orm import Session

from .db.models import AuditLog


def write_audit(
    db: Session,
    user_id: int,
    action: str,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            detail=detail or {},
        )
    )

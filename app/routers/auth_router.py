from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..db.models import User
from ..auth import verify_password, create_access_token, require_auth, CurrentUser

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/15minutes")  # slow down brute-force guessing
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()

    # Same error for "no such user" and "wrong password" — don't reveal which one it was.
    if not user or not user.is_active or not user.password_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    token = create_access_token(user.id, user.username, user.role)
    return LoginResponse(
        token=token,
        user={"id": user.id, "username": user.username, "displayName": user.display_name, "role": user.role},
    )


@router.get("/me")
def me(current: CurrentUser = Depends(require_auth), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current.id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return {"id": user.id, "username": user.username, "displayName": user.display_name, "role": user.role}

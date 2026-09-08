import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # must run before any module reads os.environ (db session, auth)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.routers.auth_router import router as auth_router, limiter
from app.routers.roster_router import router as roster_router
from app.routers.reports_router import router as reports_router
from app.routers.users_router import router as users_router
from app.routers.admin_router import router as admin_router

app = FastAPI(title="Service Desk Hub API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# FastAPI's default error body is {"detail": "..."}, but every page in this project
# (login forms, save-to-history widgets, the admin panel) reads `data.error`. Without
# this, every failed request silently showed "undefined" instead of the real message.
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else None
    message = f"{'.'.join(str(p) for p in first['loc'])}: {first['msg']}" if first else "Invalid request"
    return JSONResponse(status_code=422, content={"error": message})

allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(roster_router)
app.include_router(reports_router)
app.include_router(users_router)
app.include_router(admin_router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return RedirectResponse(url="/dashboard/")


# Serves public/admin/index.html at http://localhost:4000/admin — a quick way to
# confirm the whole stack (DB + API + auth) works before wiring up the real dashboard.
public_dir = Path(__file__).parent / "public"
app.mount("/admin", StaticFiles(directory=public_dir / "admin", html=True), name="admin")

# Serves the full dashboard suite (hub shell + SDCM/AICC/SLA reports + Shift Roster)
# at http://localhost:4000/dashboard/ — this is the actual product, unchanged from
# the standalone version, just hosted by this same server for convenience.
app.mount("/dashboard", StaticFiles(directory=public_dir / "dashboard", html=True), name="dashboard")

"""FastAPI application — hiring triage system server."""
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from resumetool.config import settings
from resumetool.database.models import Base
from resumetool.database.session import engine
from resumetool.server.routes import candidates, dashboard, feedback, jobs, screening


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="ResumeTool Hiring Triage", lifespan=lifespan)

_security = HTTPBasic()


def _parse_auth_users() -> dict[str, str]:
    """Parse 'user:pass,user2:pass2' config into a dict."""
    users = {}
    for pair in settings.hr_auth_users.split(","):
        pair = pair.strip()
        if ":" in pair:
            u, p = pair.split(":", 1)
            users[u.strip()] = p.strip()
    return users


def require_hr_auth(credentials: HTTPBasicCredentials = Depends(_security)):
    users = _parse_auth_users()
    expected_password = users.get(credentials.username)
    if not expected_password or not secrets.compare_digest(
        credentials.password.encode(), expected_password.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# Public endpoints (no auth): screening form
app.include_router(screening.router)

# Authenticated: API + dashboard
app.include_router(jobs.router, dependencies=[Depends(require_hr_auth)])
app.include_router(candidates.router, dependencies=[Depends(require_hr_auth)])
app.include_router(feedback.router, dependencies=[Depends(require_hr_auth)])
app.include_router(dashboard.router, dependencies=[Depends(require_hr_auth)])

try:
    app.mount("/static", StaticFiles(directory="src/resumetool/server/static"), name="static")
except Exception:
    pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

from fastapi import APIRouter

from app.db import check_database_ready


router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readiness() -> dict[str, str]:
    check_database_ready()
    return {"status": "ready"}

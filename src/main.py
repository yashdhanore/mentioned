from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.database import check_api_database_role, create_db_and_tables
from src.jobs.exceptions import JobError
from src.mentions.exceptions import MentionError


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_api_database_role()
    create_db_and_tables()
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: object, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error_code": "validation_error", "message": "The request is not valid."},
    )


@app.exception_handler(JobError)
async def job_error_handler(_: object, exc: JobError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )


@app.exception_handler(MentionError)
async def mention_error_handler(_: object, exc: MentionError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )


if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))


# Import and include routers
from src.jobs.router import router as jobs_router
from src.mentions.router import router as mentions_router
from src.push.router import router as push_router

app.include_router(jobs_router)
app.include_router(mentions_router)
app.include_router(push_router)


@app.get("/health")
async def health():
    return {"status": "ok"}

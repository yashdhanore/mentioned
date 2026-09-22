from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from src.account.router import router as account_router
from src.config import get_settings
from src.database import check_api_database_role, create_db_and_tables
from src.errors import AppError
from src.push.router import router as push_router
from src.sources.router import router as sources_router
from src.waitlist.router import router as waitlist_router

settings = get_settings()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_PRIVACY_HTML = (_TEMPLATES_DIR / "privacy.html").read_text()
_SUPPORT_HTML = (_TEMPLATES_DIR / "support.html").read_text()


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


@app.exception_handler(AppError)
async def app_error_handler(_: object, exc: AppError) -> JSONResponse:
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


app.include_router(account_router)
app.include_router(push_router)
app.include_router(sources_router)
app.include_router(waitlist_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/privacy", include_in_schema=False)
async def privacy_policy() -> Response:
    if settings.web_base_url:
        return RedirectResponse(f"{settings.web_base_url}/privacy", status_code=301)
    return HTMLResponse(_PRIVACY_HTML)


@app.get("/support", include_in_schema=False)
async def support_page() -> Response:
    if settings.web_base_url:
        return RedirectResponse(f"{settings.web_base_url}/support", status_code=301)
    return HTMLResponse(_SUPPORT_HTML)

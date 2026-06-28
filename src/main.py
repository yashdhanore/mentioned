from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from src.config import get_settings
from src.database import check_api_database_role, create_db_and_tables
from src.jobs.exceptions import JobError
from src.mentions.exceptions import MentionError
from src.sources.exceptions import SourceError


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


@app.exception_handler(SourceError)
async def source_error_handler(_: object, exc: SourceError) -> JSONResponse:
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
from src.account.router import router as account_router
from src.push.router import router as push_router
from src.sources.router import router as sources_router
from src.waitlist.router import router as waitlist_router

app.include_router(account_router)
app.include_router(push_router)
app.include_router(sources_router)
app.include_router(waitlist_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy() -> str:
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Mentioned Privacy Policy</title>
    <style>
      body { color: #1c2520; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.6; margin: 0; }
      main { margin: 0 auto; max-width: 760px; padding: 40px 20px; }
      h1, h2 { line-height: 1.2; }
      h1 { font-size: 2rem; }
      h2 { font-size: 1.2rem; margin-top: 2rem; }
      a { color: #345d8c; }
    </style>
  </head>
  <body>
    <main>
      <h1>Mentioned Privacy Policy</h1>
      <p>Effective date: May 14, 2026</p>

      <p>
        Mentioned helps you save public Instagram Reel and post links and identify books mentioned
        in that content. This policy explains what information the app processes and why.
      </p>

      <h2>Information We Collect</h2>
      <p>
        We collect account information provided through Supabase authentication, such as your email
        address and user identifier. We also store the Instagram URLs you submit, saved-source
        extraction status, extracted item results, related book metadata, and optional Expo push
        notification tokens if you allow notifications.
      </p>

      <h2>How We Use Information</h2>
      <p>
        We use this information to authenticate your account, process submitted links, save your
        results, show your saved Reels and books, send saved-source notifications, prevent abuse, and
        diagnose service issues.
      </p>

      <h2>Service Providers</h2>
      <p>
        Mentioned uses Supabase for authentication and database hosting, Render for backend hosting,
        Google Gemini for extraction, Google Books for book metadata, Expo for push notification
        delivery, and Instagram content access through public URLs you provide. These providers
        process information only as needed to operate the app.
      </p>

      <h2>Data Sharing</h2>
      <p>
        We do not sell your personal information. We do not share your saved content with other
        users. Information is shared with service providers only to provide the app's functionality,
        comply with legal obligations, or protect the service from abuse.
      </p>

      <h2>Data Retention and Deletion</h2>
      <p>
        We keep account data, submitted URLs, saved sources, extracted items, and push tokens while
        your account is active or as needed to operate and protect the service. You can delete saved
        sources in the app. To request account or data deletion, contact support.
      </p>

      <h2>Security</h2>
      <p>
        We use authenticated API access, row-level database access controls, and separate internal
        worker credentials to protect user data. No internet service can guarantee absolute security.
      </p>

      <h2>Children</h2>
      <p>
        Mentioned is not intended for children under 13.
      </p>

      <h2>Contact</h2>
      <p>
        For privacy questions or deletion requests, contact
        <a href="mailto:yashdhanore@gmail.com">yashdhanore@gmail.com</a>.
      </p>
    </main>
  </body>
</html>
"""


@app.get("/support", response_class=HTMLResponse, include_in_schema=False)
async def support_page() -> str:
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Mentioned Support</title>
    <style>
      body { color: #1c2520; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.6; margin: 0; }
      main { margin: 0 auto; max-width: 680px; padding: 40px 20px; }
      a { color: #345d8c; }
    </style>
  </head>
  <body>
    <main>
      <h1>Mentioned Support</h1>
      <p>
        Need help with Mentioned, account access, extraction results, or data deletion?
        Email <a href="mailto:yashdhanore@gmail.com">yashdhanore@gmail.com</a>.
      </p>
      <p><a href="/privacy">Privacy Policy</a></p>
    </main>
  </body>
</html>
"""

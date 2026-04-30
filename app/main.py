from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import create_db_and_tables
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.results import router as results_router


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(results_router)


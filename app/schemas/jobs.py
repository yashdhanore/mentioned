from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel


class CreateJobRequest(BaseModel):
    url: AnyHttpUrl


class JobResponse(BaseModel):
    job_id: str
    source_url: str
    source_kind: str
    status: str
    current_stage: str | None
    progress: float
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


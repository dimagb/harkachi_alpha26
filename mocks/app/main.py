from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="External mocks", docs_url=None, redoc_url=None, openapi_url=None)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"] = "ok"


@app.get("/mock/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

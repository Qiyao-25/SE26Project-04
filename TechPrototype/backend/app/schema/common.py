from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = ""
    data: T
    request_id: str = Field(min_length=1)


class HealthData(BaseModel):
    status: str
    database: str
    environment: str
    version: str
    component_versions: dict[str, str]


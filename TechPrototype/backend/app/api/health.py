from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.schema.common import ApiResponse, HealthData
from app.service.health import get_health

router = APIRouter(tags=["system"])


@router.get("/health", response_model=ApiResponse[HealthData], summary="检查 API 和数据库健康状态", operation_id="health_check", responses={503: {"description": "数据库不可用"}})
def health(request: Request) -> JSONResponse | ApiResponse[HealthData]:
    data = get_health(request.app.state.engine, request.app.state.settings)
    payload = ApiResponse[HealthData](data=data, request_id=request.state.request_id)
    if data.status != "ok":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload.model_dump(), headers={"X-Request-ID": request.state.request_id})
    return payload


@router.get("/api/health", response_model=ApiResponse[HealthData], include_in_schema=False)
def api_health(request: Request) -> JSONResponse | ApiResponse[HealthData]:
    return health(request)

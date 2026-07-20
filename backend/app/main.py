import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.learning import router as learning_router
from app.api.admin import router as admin_router
from app.api.papers import router as papers_router
from app.api.profile import router as profile_router
from app.api.recommendations import router as recommendations_router
from app.api.search import router as search_router
from app.api.subscriptions import router as subscriptions_router
from app.api.tasks import router as tasks_router
from app.core.config import Settings, get_settings
from app.core.database import create_engine_for
from app.schema.common import ApiResponse
from app.service.crawl_scheduler import run_crawl_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_crawl_scheduler(app, stop_event))
    app.state.crawl_stop_event = stop_event
    app.state.crawl_task = task
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="PaperMate Backend API",
        description="PaperMate 技术原型迭代二后端 API",
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = create_engine_for(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        payload = ApiResponse[dict](code="VALIDATION_ERROR", message="请求参数校验失败", data={"errors": exc.errors()}, request_id=request.state.request_id)
        return JSONResponse(status_code=400, content=payload.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        payload = ApiResponse[dict](code="HTTP_ERROR", message=str(exc.detail), data={}, request_id=request.state.request_id)
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(learning_router)
    app.include_router(papers_router)
    app.include_router(profile_router)
    app.include_router(recommendations_router)
    app.include_router(subscriptions_router)
    app.include_router(search_router)
    app.include_router(tasks_router)
    return app


app = create_app()

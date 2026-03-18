import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.assignments import router as assignments_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.departments import router as departments_router
from app.api.notifications import router as notifications_router
from app.api.rotations import router as rotations_router
from app.api.submissions import router as submissions_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.database import engine
from app.core.rate_limit import limiter
from app.middleware import LimitRequestSizeMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown.

    Startup:
    - Validate database connectivity
    - Log application initialization

    Shutdown:
    - Dispose database connections gracefully
    """
    # Startup
    logger.info("Starting %s...", settings.APP_NAME)

    # Validate database connectivity
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connectivity validated")
    except Exception as e:
        logger.error("Database connection failed during startup: %s", e)
        raise

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)

    # Dispose database connections
    await engine.dispose()
    logger.info("Database connections disposed")


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

MAX_REQUEST_SIZE = 1_048_576  # 1 MB

# Add pure ASGI middleware (more efficient than BaseHTTPMiddleware)
app.add_middleware(LimitRequestSizeMiddleware, max_size=MAX_REQUEST_SIZE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions. Log the trace, return generic 500."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
        },
    )


# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(departments_router)
app.include_router(rotations_router)
app.include_router(submissions_router)
app.include_router(assignments_router)
app.include_router(dashboard_router)
app.include_router(notifications_router)
app.include_router(audit_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

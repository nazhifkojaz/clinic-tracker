from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assignments import router as assignments_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.departments import router as departments_router
from app.api.rotations import router as rotations_router
from app.api.submissions import router as submissions_router
from app.api.users import router as users_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(departments_router)
app.include_router(rotations_router)
app.include_router(submissions_router)
app.include_router(assignments_router)
app.include_router(dashboard_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import FRONTEND_URL
from app.database import engine, Base
from app.models.user import User  # noqa: F401 - needed so create_all sees the model
from app.models.profile import JobSeekerProfile  # noqa: F401
from app.models.cv import CV  # noqa: F401
from app.models.job import Job  # noqa: F401 - needed so create_all sees the model
from app.models.application import Application, ApplicationStatusHistory  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.admin import SystemSetting, AdminAuditLog  # noqa: F401
from app.routes.auth import router as auth_router
from app.routes.profile import router as profile_router
from app.routes.admin import router as admin_router
from app.routes.cv import router as cv_router
from app.routes.jobs import router as jobs_router
from app.routes.applications import router as applications_router
from app.routes.notifications import router as notifications_router

app = FastAPI(title="AutoApply API", version="1.0.0")

# CORS - allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables on startup
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(admin_router)
app.include_router(cv_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(notifications_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/system/shutdown")
def shutdown_system():
    """Allows local desktop container (Electron) to trigger graceful server shutdown."""
    import os, signal, threading
    def _kill():
        import time
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=_kill, daemon=True).start()
    return {"message": "Shutting down"}


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import init_db, AsyncSessionLocal
from backend.app.seeds.seed_data import seed_database

# Routers
from backend.app.api.hospitals import router as hospitals_router
from backend.app.api.campaigns import router as campaigns_router
from backend.app.api.queue import router as queue_router
from backend.app.api.calls import router as calls_router
from backend.app.api.escalations import router as escalations_router
from backend.app.api.protocols import router as protocols_router
from backend.app.api.simulation import router as simulation_router
from backend.app.api.safety import router as safety_router
from backend.app.api.patients import router as patients_router
from backend.app.api.ehr import router as ehr_router
from backend.app.api.audit import router as audit_router
from backend.app.api.health import router as health_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.chat import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    await init_db()
    # Seed multi-tenant data if empty
    async with AsyncSessionLocal() as session:
        await seed_database(session)
    yield

app = FastAPI(
    title="Multi-Hospital Post-Discharge Outreach Platform",
    description="Autonomous AI-Powered Patient Follow-Up, Clinical Triage & Hospital Outreach Operations Platform",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(hospitals_router, prefix="/api")
app.include_router(campaigns_router, prefix="/api")
app.include_router(queue_router, prefix="/api")
app.include_router(calls_router, prefix="/api")
app.include_router(escalations_router, prefix="/api")
app.include_router(protocols_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")
app.include_router(safety_router, prefix="/api")
app.include_router(patients_router, prefix="/api")
app.include_router(ehr_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(chat_router)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "platform": settings.APP_NAME,
        "version": "2.0.0",
        "status": "OPERATIONAL",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)

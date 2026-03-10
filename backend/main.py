from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
from database import init_db
from routers import wells, aquifers, alerts, forecasting, dashboard, auth, regulatory, sync, recommendations
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        from services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logging.warning(f"Scheduler could not start: {e}")
    yield
    try:
        from services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

app = FastAPI(
    title="Aquifer Intelligence Platform API",
    description="Real-time groundwater monitoring and forecasting system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow all origins (development mode)
# allow_credentials must be False when allow_origins=["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["Authentication"])
app.include_router(wells.router,       prefix="/api/wells",       tags=["Wells"])
app.include_router(aquifers.router,    prefix="/api/aquifers",    tags=["Aquifers"])
app.include_router(alerts.router,      prefix="/api/alerts",      tags=["Alerts"])
app.include_router(forecasting.router, prefix="/api/forecasting", tags=["Forecasting"])
app.include_router(dashboard.router,   prefix="/api/dashboard",   tags=["Dashboard"])
app.include_router(regulatory.router,  prefix="/api/regulatory",  tags=["Regulatory"])
app.include_router(sync.router,        prefix="/api/sync",        tags=["Data Sync"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])

@app.get("/health")
def health():
    return {"status": "healthy"}

# Serve Frontend
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # If it's an API route, let it fall through to the routers
        if full_path.startswith("api/"):
            return None # Should be handled by routers
        
        # Check if the requested file exists in frontend
        file_path = os.path.join(frontend_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Otherwise serve index.html (for SPA routing)
        return FileResponse(os.path.join(frontend_path, "index.html"))
else:
    @app.get("/")
    def root():
        return {"message": "Aquifer Intelligence Platform API (Frontend not found)", "version": "1.0.0"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
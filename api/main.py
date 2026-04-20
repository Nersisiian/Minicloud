from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from api.routes import auth, vms, tasks
from observability.logging_config import setup_logging
from observability.metrics import setup_metrics
from db.base import engine

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Metrics endpoint will be handled by prometheus_client
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="MiniCloud IaaS API",
    description="KVM Orchestrator Control Plane",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup metrics
setup_metrics(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(vms.router)
app.include_router(tasks.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
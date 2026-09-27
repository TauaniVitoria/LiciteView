import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    oauth2_schema,
    hash_password,
    verify_password
)

limiter = Limiter(key_func=get_remote_address)

_celery_worker: subprocess.Popen | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _celery_worker
    # Em produção (Docker), START_CELERY_WORKER=false — worker roda em container separado.
    # Em desenvolvimento local, START_CELERY_WORKER=true (padrão) sobe o worker junto.
    if os.getenv("START_CELERY_WORKER", "true").lower() == "true":
        _celery_worker = subprocess.Popen(
            [sys.executable, "-m", "celery", "-A", "worker.celery_app",
             "worker", "--loglevel=info", "--pool=solo"],
        )
        print("✓ Celery worker iniciado (PID:", _celery_worker.pid, ")")
    yield
    if _celery_worker:
        _celery_worker.terminate()
        print("✓ Celery worker encerrado")


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:4200").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# As funções de autenticação e hash foram movidas para config.py

from routes.auth_routes import auth_router
from routes.admin_routes import admin_router
from routes.cliente_routes import cliente_router

app.include_router(admin_router)
app.include_router(cliente_router)
app.include_router(auth_router)


@app.get("/health", tags=["Infra"])
def health():
    return {"status": "ok"}

# StaticFiles removido em produção (frontend servido pelo Render)
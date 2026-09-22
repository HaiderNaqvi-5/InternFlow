import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    attendance,
    audit,
    auth,
    batches,
    certificates,
    company,
    discussions,
    notifications,
    reports,
    search,
    submissions,
    tasks,
    users,
)
from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import User
from app.websocket.manager import manager

settings = get_settings()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("internflow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.APP_ENV)
    yield
    logger.info("Shutdown complete")


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0",
    description="FastAPI REST API for InternFlow internship operations platform.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# A strict origin list is required in production (no wildcard).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = settings.API_PREFIX

for module in (
    auth,
    users,
    company,
    batches,
    tasks,
    submissions,
    attendance,
    discussions,
    notifications,
    search,
    analytics,
    reports,
    certificates,
    audit,
):
    app.include_router(module.router, prefix=api_prefix)

app.include_router(attendance.LEAVE_ROUTER, prefix=api_prefix)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    user = None
    if token:
        payload = decode_token(token, expected_type="access")
        if payload:
            db = SessionLocal()
            user = db.get(User, int(payload["sub"]))
            db.close()
    if user is None or not user.is_active:
        await websocket.close(code=4401)
        return

    await manager.connect(websocket, user.id)
    await websocket.send_json({"type": "connected", "user_id": user.id})
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, user.id)


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "message": "InternFlow API. See /docs for OpenAPI."}

"""
Production AI Agent — Main FastAPI Application
Matches all requirements for 12-factor cloud-native AI agents.
"""
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import os
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn


from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Structured JSON Logging
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.getLevelName(settings.log_level),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# Global metrics and status flags
START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Application Lifespan Lifecycle
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    # Simulate database / connection pools startup delay
    time.sleep(0.1)
    _is_ready = True
    logger.info(json.dumps({"event": "ready", "status": "all systems operational"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown", "status": "cleaning up resources"}))

# ─────────────────────────────────────────────────────────
# FastAPI App Initialization
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# CORS Middleware configurations
origins = settings.allowed_origins.split(",") if hasattr(settings, "allowed_origins") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Custom HTTP Middleware for security headers & latency structured logging
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Apply security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        logger.error(json.dumps({
            "event": "request_error",
            "method": request.method,
            "path": request.url.path,
            "error": str(e),
        }))
        raise

# ─────────────────────────────────────────────────────────
# Request & Response Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Question for the AI agent")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────
@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "ui": "GET /ui (Web Control Console)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }

@app.get("/ui", response_class=HTMLResponse, tags=["UI"])
def get_ui():
    """Expose a beautiful web interface to test the agent APIs."""
    static_file_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.exists(static_file_path):
        raise HTTPException(status_code=404, detail="UI index.html not found")
    with open(static_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    user_id: str = Depends(verify_api_key),
):
    """
    Submit a query to the AI Agent.
    Requires header: X-API-Key: <your-key>
    """
    # Rate Limiting check
    check_rate_limit(user_id)

    # Cost / Budget check
    check_budget(user_id)

    # Calculate token cost (Input tokens estimation: ~2 per word)
    input_tokens = len(body.question.split()) * 2
    input_cost = (input_tokens / 1000) * 0.00015
    record_cost(user_id, input_cost)

    logger.info(json.dumps({
        "event": "agent_call",
        "client": str(request.client.host) if request.client else "unknown",
        "user_id": user_id,
        "q_len": len(body.question),
    }))

    # Invoke Mock LLM
    answer = llm_ask(body.question)

    # Record output token costs (Output tokens estimation: ~2 per word)
    output_tokens = len(answer.split()) * 2
    output_cost = (output_tokens / 1000) * 0.0006
    record_cost(user_id, output_cost)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Used by platform orchestrator to check if container is alive."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Used by load-balancer to check if instance is ready to receive traffic."""
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Agent is starting or unhealthy")
    return {"ready": True}

@app.get("/metrics", tags=["Operations"])
def metrics(user_id: str = Depends(verify_api_key)):
    """Expose application metrics (restricted)."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def handle_sigterm(signum, frame):
    global _is_ready
    logger.info(json.dumps({
        "event": "signal",
        "msg": "Received SIGTERM signal. Initiating graceful shutdown sequence.",
        "signum": signum
    }))
    _is_ready = False  # Tells load balancers we're no longer accepting traffic

# Register SIGTERM listener
signal.signal(signal.SIGTERM, handle_sigterm)

if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API key auth enabled. Expected prefix: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )

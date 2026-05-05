"""NFC AI — FastAPI entry point (Sprint 1: agent wired)"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from ..schemas.decision import ERPEvent, DecisionOutput
from ..agents.engine import DecisionAgent
from ..logger.decision_logger import get_logger, UserActionInput


class Settings(BaseSettings):
    api_secret_key: str = "dev-secret"
    allowed_origins: str = "http://localhost:8070"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
agent: DecisionAgent | None = None

INSIGHT_HTTP_TIMEOUT_SEC = float(os.getenv("INSIGHT_HTTP_TIMEOUT_SEC", "90"))
INSIGHT_MAX_CONCURRENT = max(1, int(os.getenv("INSIGHT_MAX_CONCURRENT", "2")))
_insight_sem = asyncio.Semaphore(INSIGHT_MAX_CONCURRENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = DecisionAgent()
    yield
    agent = None


app = FastAPI(
    title="NFC AI Decision Platform",
    description="AI Decision Layer for Odoo 18 ERP — NFC",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "sprint": "S1",
        "agent": "ready" if agent else "not_initialized",
    }


class InsightResponse(BaseModel):
    decision: DecisionOutput
    log_id: int | None = None


@app.post("/api/insight", response_model=InsightResponse)
async def get_insight(event: ERPEvent) -> InsightResponse:
    """
    Nhận ERPEvent từ OWL widget.
    Trả về DecisionOutput + log_id (để OWL widget gửi user_action sau).

    Event flow:
      ERPEvent → EventAggregator → DomainRouter → LangGraph Agent → DecisionOutput → DecisionLog
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    async with _insight_sem:
        try:
            decision, log_id = await asyncio.wait_for(
                asyncio.to_thread(agent.run, event),
                timeout=INSIGHT_HTTP_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            decision = DecisionOutput(
                level="no_data",
                message="Hết thời gian chờ phân tích AI. Giảm số dòng cùng lúc hoặc thử lại.",
                confidence="low",
                data_points=0,
            )
            log_id = None
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return InsightResponse(decision=decision, log_id=log_id)


@app.post("/api/feedback")
async def log_user_action(data: UserActionInput):
    """
    OWL widget gọi endpoint này khi user quyết định (accept / ignore / override).
    Dữ liệu này nuôi Feedback Loop để AI tự cải thiện theo thời gian.
    """
    logger = get_logger()
    ok = logger.log_user_action(data)
    return {"success": ok}


@app.get("/api/tools")
async def list_tools():
    """Debug endpoint: liệt kê các tools đã được đăng ký."""
    from ..tools.registry import list_tools
    return {"tools": list_tools()}


@app.get("/api/routes")
async def list_routes():
    """Debug endpoint: liệt kê domain routing table."""
    from ..events.router import DOMAIN_ROUTES
    return {
        "routes": [
            {
                "model": r.model,
                "event_type": r.event_type,
                "tools": r.tools,
            }
            for r in DOMAIN_ROUTES
        ]
    }

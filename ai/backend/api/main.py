"""NFC AI — FastAPI entry point"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from ..schemas.decision import ERPEvent, DecisionOutput
from ..analytics.price_analyzer import PriceAnalyzer
from ..logger.decision_logger import get_logger, UserActionInput


class Settings(BaseSettings):
    api_secret_key: str = "dev-secret"
    allowed_origins: str = "http://localhost:8070"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
_analyzer = PriceAnalyzer()

INSIGHT_HTTP_TIMEOUT_SEC = float(os.getenv("INSIGHT_HTTP_TIMEOUT_SEC", "15"))
INSIGHT_MAX_CONCURRENT = max(1, int(os.getenv("INSIGHT_MAX_CONCURRENT", "10")))
_insight_sem = asyncio.Semaphore(INSIGHT_MAX_CONCURRENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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
        "agent": "pure_sql_analyzer",
    }


class InsightResponse(BaseModel):
    decision: DecisionOutput
    log_id: int | None = None


@app.post("/api/insight", response_model=InsightResponse)
async def get_insight(event: ERPEvent) -> InsightResponse:
    """
    Nhận ERPEvent từ OWL widget.
    Trả về DecisionOutput + log_id.

    Flow: ERPEvent → PriceAnalyzer (SQL thuần) → DecisionOutput → DecisionLog
    Không gọi LLM — latency < 200ms, 0 token cost.
    """
    async with _insight_sem:
        try:
            decision = await asyncio.wait_for(
                asyncio.to_thread(_analyzer.analyze, event),
                timeout=INSIGHT_HTTP_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            decision = DecisionOutput(
                level="no_data",
                message="Hết thời gian chờ. Thử lại sau.",
                confidence="low",
                data_points=0,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Ghi log để dùng cho feedback loop sau này
    log_id: int | None = None
    try:
        from ..logger.decision_logger import DecisionLogInput
        logger = get_logger()
        log_input = DecisionLogInput(
            odoo_model=event.model,
            record_id=event.record_id or 0,
            field_name=event.field,
            field_value=str(event.value or ""),
            event_type=event.event_type or "price_check",
            company_id=int(event.context.get("company_id") or 1),
            user_id=int(event.context.get("user_id") or 0),
            ai_level=decision.level,
            ai_deviation=decision.deviation_pct,
            ai_message=decision.message,
            ai_suggestion=decision.suggestion,
            ai_confidence=decision.confidence,
            ai_data_points=decision.data_points,
            ai_tools_used=decision.tools_used,
            ai_cached=decision.cached,
        )
        log_id = logger.log(log_input)
    except Exception:
        pass

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
    """Debug: analyzer mode (no LLM)."""
    return {"mode": "pure_sql_analyzer", "tools": ["price_history_sql", "supplier_comparison_sql"]}

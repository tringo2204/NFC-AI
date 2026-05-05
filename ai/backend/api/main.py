"""NFC AI — FastAPI entry point (Sprint 1: agent wired)"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings

from ..schemas.decision import ERPEvent, DecisionOutput
from ..agents.engine import DecisionAgent


class Settings(BaseSettings):
    api_secret_key: str = "dev-secret"
    allowed_origins: str = "http://localhost:8070"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
agent: DecisionAgent | None = None


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


@app.post("/api/insight", response_model=DecisionOutput)
async def get_insight(event: ERPEvent) -> DecisionOutput:
    """
    Nhận ERPEvent từ OWL widget.
    Trả về DecisionOutput (JSON schema cố định).

    Event flow:
      ERPEvent → EventAggregator → DomainRouter → LangGraph Agent → DecisionOutput
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    try:
        return agent.run(event)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

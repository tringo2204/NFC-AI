"""NFC AI — FastAPI entry point (Sprint 0 skeleton)"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_secret_key: str = "dev-secret"
    allowed_origins: str = "http://localhost:8070"
    redis_url: str = "redis://localhost:6379/1"
    odoo_db_host: str = "localhost"
    odoo_db_port: int = 5432
    odoo_db_name: str = "nfc_erp"
    odoo_db_user: str = "odoo18"
    odoo_db_password: str = "odoo18"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"

    class Config:
        env_file = ".env"


settings = Settings()

app = FastAPI(
    title="NFC AI Decision Platform",
    description="AI Decision Layer for Odoo 18 ERP — NFC",
    version="0.1.0",
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
    return {"status": "ok", "version": "0.1.0", "sprint": "S0"}


@app.post("/api/insight")
async def get_insight(event: dict):
    """
    Nhận ERPEvent từ OWL widget, trả về Decision JSON.
    Sprint 0: stub — agent sẽ được kết nối ở Sprint 1.
    """
    return {
        "level": "no_data",
        "deviation_pct": None,
        "message": "AI engine chưa được kích hoạt (Sprint 0).",
        "suggestion": None,
        "actions": [],
        "confidence": "low",
        "data_points": 0,
        "tools_used": [],
        "cached": False,
    }

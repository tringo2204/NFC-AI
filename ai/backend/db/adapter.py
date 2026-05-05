"""
Odoo DB Adapter — read-only SQLAlchemy connection.
AI chỉ đọc data, không bao giờ write vào Odoo DB.
"""
from functools import lru_cache
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic_settings import BaseSettings


class DBSettings(BaseSettings):
    odoo_db_host: str = "localhost"
    odoo_db_port: int = 5432
    odoo_db_name: str = "nfc_erp"
    odoo_db_user: str = "odoo18"
    odoo_db_password: str = "odoo18"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> DBSettings:
    return DBSettings()


@lru_cache
def get_engine():
    s = get_settings()
    url = (
        f"postgresql+psycopg2://{s.odoo_db_user}:{s.odoo_db_password}"
        f"@{s.odoo_db_host}:{s.odoo_db_port}/{s.odoo_db_name}"
    )
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class OdooQuery:
    """Helper cho các query thường dùng, trả về list[dict]."""

    def __init__(self, session: Session):
        self.db = session

    def fetch(self, sql: str, **params) -> list[dict]:
        result = self.db.execute(text(sql), params)
        cols = result.keys()
        return [dict(zip(cols, row)) for row in result.fetchall()]

    def fetch_one(self, sql: str, **params) -> dict | None:
        rows = self.fetch(sql, **params)
        return rows[0] if rows else None

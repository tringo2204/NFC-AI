"""
Decision Logger — ghi log mọi AI insight và user action.
Đây là nền tảng của Feedback Loop và competitive moat dài hạn.

Schema: ai_decision_log (PostgreSQL — DB riêng, không phải Odoo DB)
"""
import json
import os
from datetime import datetime, timezone
from typing import Literal

import structlog
from pydantic import BaseModel
from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text, Boolean,
    create_engine, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

log = structlog.get_logger()
Base = declarative_base()


class DecisionLog(Base):
    __tablename__ = "ai_decision_log"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    timestamp       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Event context
    odoo_model      = Column(String(100), nullable=False, index=True)
    record_id       = Column(Integer, nullable=False)
    field_name      = Column(String(100))
    field_value     = Column(Text)
    event_type      = Column(String(100), index=True)
    company_id      = Column(Integer)
    user_id         = Column(Integer, index=True)

    # AI output
    ai_level        = Column(String(20))    # good|normal|high|critical|no_data
    ai_deviation    = Column(Float)
    ai_message      = Column(String(200))
    ai_suggestion   = Column(Text)
    ai_confidence   = Column(String(20))
    ai_data_points  = Column(Integer)
    ai_tools_used   = Column(Text)          # JSON array
    ai_cached       = Column(Boolean, default=False)
    ai_latency_ms   = Column(Integer)       # thời gian phản hồi

    # User action (cập nhật sau khi user làm gì)
    user_action     = Column(String(50))    # accepted|ignored|overridden|negotiated
    user_action_at  = Column(DateTime(timezone=True))
    outcome         = Column(String(100))   # po_confirmed|po_cancelled|renegotiated


class DecisionLogInput(BaseModel):
    odoo_model:     str
    record_id:      int
    field_name:     str = ""
    field_value:    str = ""
    event_type:     str = ""
    company_id:     int = 1
    user_id:        int = 0
    ai_level:       str
    ai_deviation:   float | None = None
    ai_message:     str
    ai_suggestion:  str | None = None
    ai_confidence:  str
    ai_data_points: int
    ai_tools_used:  list[str] = []
    ai_cached:      bool = False
    ai_latency_ms:  int = 0


class UserActionInput(BaseModel):
    log_id:         int
    user_action:    Literal["accepted", "ignored", "overridden", "negotiated"]
    outcome:        str = ""


class DecisionLogger:
    def __init__(self, db_url: str | None = None):
        url = db_url or os.getenv(
            "LOGGER_DB_URL",
            os.getenv("ODOO_DB_URL", "postgresql+psycopg2://odoo18:odoo18@localhost:5432/nfc_erp")
        )
        try:
            self._engine = create_engine(url, pool_pre_ping=True)
            self._session_factory = sessionmaker(bind=self._engine)
            self._ensure_table()
            self._enabled = True
            log.info("decision_logger_ready")
        except Exception as e:
            log.warning("decision_logger_disabled", reason=str(e))
            self._enabled = False

    def _ensure_table(self):
        Base.metadata.create_all(self._engine)

    def log_insight(self, data: DecisionLogInput) -> int | None:
        """Ghi AI insight vào log. Trả về log_id để cập nhật user_action sau."""
        if not self._enabled:
            return None
        session = self._session_factory()
        try:
            record = DecisionLog(
                odoo_model=data.odoo_model,
                record_id=data.record_id,
                field_name=data.field_name,
                field_value=str(data.field_value)[:500],
                event_type=data.event_type,
                company_id=data.company_id,
                user_id=data.user_id,
                ai_level=data.ai_level,
                ai_deviation=data.ai_deviation,
                ai_message=data.ai_message,
                ai_suggestion=data.ai_suggestion,
                ai_confidence=data.ai_confidence,
                ai_data_points=data.ai_data_points,
                ai_tools_used=json.dumps(data.ai_tools_used),
                ai_cached=data.ai_cached,
                ai_latency_ms=data.ai_latency_ms,
            )
            session.add(record)
            session.commit()
            log.info("decision_logged", log_id=record.id, level=data.ai_level)
            return record.id
        except Exception as e:
            session.rollback()
            log.error("decision_log_error", error=str(e))
            return None
        finally:
            session.close()

    def log_user_action(self, data: UserActionInput) -> bool:
        """Cập nhật user_action sau khi user quyết định."""
        if not self._enabled:
            return False
        session = self._session_factory()
        try:
            record = session.get(DecisionLog, data.log_id)
            if record:
                record.user_action = data.user_action
                record.user_action_at = datetime.now(timezone.utc)
                record.outcome = data.outcome
                session.commit()
                log.info("user_action_logged", log_id=data.log_id, action=data.user_action)
                return True
        except Exception as e:
            session.rollback()
            log.error("user_action_log_error", error=str(e))
        finally:
            session.close()
        return False

    def get_feedback_stats(self, model: str, field: str, days: int = 30) -> dict:
        """
        Thống kê Feedback Loop: AI đúng bao nhiêu %?
        Dùng để tự điều chỉnh threshold theo thời gian.
        """
        if not self._enabled:
            return {}
        session = self._session_factory()
        try:
            result = session.execute(text("""
                SELECT
                    ai_level,
                    user_action,
                    COUNT(*) AS count,
                    AVG(ai_deviation) AS avg_deviation
                FROM ai_decision_log
                WHERE odoo_model = :model
                  AND field_name = :field
                  AND timestamp >= NOW() - INTERVAL ':days days'
                  AND user_action IS NOT NULL
                GROUP BY ai_level, user_action
                ORDER BY ai_level, user_action
            """), {"model": model, "field": field, "days": days})
            rows = [dict(zip(result.keys(), r)) for r in result.fetchall()]
            return {"stats": rows, "model": model, "field": field, "days": days}
        finally:
            session.close()


# Singleton
_logger_instance: DecisionLogger | None = None


def get_logger() -> DecisionLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = DecisionLogger()
    return _logger_instance

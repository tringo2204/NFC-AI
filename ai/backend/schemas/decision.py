"""Decision JSON Schema — unified cho mọi tool và module."""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Action(BaseModel):
    label: str
    type: Literal["link", "button", "copy"] = "button"
    value: str = ""


class DecisionOutput(BaseModel):
    level: Literal["good", "normal", "high", "critical", "no_data"]
    deviation_pct: Optional[float] = None
    message: str = Field(..., max_length=200)
    suggestion: Optional[str] = None
    # LLM có thể trả actions là list[dict] hoặc list[str] — normalize về list[Action]
    actions: list[Action] = []
    confidence: Literal["high", "medium", "low"]
    data_points: int
    tools_used: list[str] = []
    cached: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_actions(cls, data: Any) -> Any:
        """LLM đôi khi trả actions là list[str] — normalize về list[dict]."""
        if isinstance(data, dict) and "actions" in data:
            normalized = []
            for a in (data["actions"] or []):
                if isinstance(a, str):
                    normalized.append({"label": a, "type": "button", "value": ""})
                elif isinstance(a, dict):
                    a.setdefault("type", "button")
                    a.setdefault("value", "")
                    normalized.append(a)
            data["actions"] = normalized
        return data


class ERPEvent(BaseModel):
    model: str              # vd: purchase.order.line
    record_id: int
    field: str              # vd: price_unit
    value: float | str | int | None
    context: dict = {}      # company_id, user_id, currency_id...
    event_type: str = ""    # semantic (set by Event Aggregator)

"""Decision JSON Schema — unified cho mọi tool và module."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Action(BaseModel):
    label: str
    type: Literal["link", "button", "copy"]
    value: str


class DecisionOutput(BaseModel):
    level: Literal["good", "normal", "high", "critical", "no_data"]
    deviation_pct: Optional[float] = None
    message: str = Field(..., max_length=120)
    suggestion: Optional[str] = None
    actions: list[Action] = []
    confidence: Literal["high", "medium", "low"]
    data_points: int
    tools_used: list[str] = []
    cached: bool = False


class ERPEvent(BaseModel):
    model: str              # vd: purchase.order.line
    record_id: int
    field: str              # vd: price_unit
    value: float | str | int | None
    context: dict = {}      # company_id, user_id, currency_id...
    event_type: str = ""    # semantic (set by Event Aggregator)

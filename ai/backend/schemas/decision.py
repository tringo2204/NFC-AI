"""Decision JSON Schema — unified cho mọi tool và module."""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Action(BaseModel):
    label: str
    type: Literal["link", "button", "copy"] = "button"
    value: str = ""


class PriceRecord(BaseModel):
    """1 dòng lịch sử giá — hiện trong bảng mini panel."""
    date:     str
    price:    float
    supplier: str
    qty:      float = 0


class PriceContext(BaseModel):
    """Dữ liệu giá structured — panel render trực tiếp, không parse text."""
    avg_price:        Optional[float] = None   # TB 6 tháng
    min_price:        Optional[float] = None   # Thấp nhất
    max_price:        Optional[float] = None   # Cao nhất
    suggested_price:  Optional[float] = None   # Giá đề xuất thương lượng
    best_supplier:    Optional[str]   = None   # NCC giá tốt nhất
    best_supplier_price: Optional[float] = None
    recent_history:   list[PriceRecord] = []   # 3 giao dịch gần nhất


class DecisionOutput(BaseModel):
    level: Literal["good", "normal", "high", "critical", "no_data"]
    deviation_pct: Optional[float] = None
    message: str = Field(..., max_length=200)
    suggestion: Optional[str] = None
    price_context: Optional[PriceContext] = None   # ← dữ liệu structured mới
    actions: list[Action] = []
    confidence: Literal["high", "medium", "low"]
    data_points: int
    tools_used: list[str] = []
    cached: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # Normalize actions list[str] → list[dict]
        normalized = []
        for a in (data.get("actions") or []):
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

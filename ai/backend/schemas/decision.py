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


class SupplierStat(BaseModel):
    """Thống kê giá theo từng NCC — dùng cho SupplierCompareCard."""
    supplier:  str
    avg_price: float
    min_price: float
    max_price: float
    count:     int
    last_date: str = ""


class PriceContext(BaseModel):
    """Dữ liệu giá structured — panel render trực tiếp, không parse text."""
    avg_price:        Optional[float] = None
    min_price:        Optional[float] = None
    max_price:        Optional[float] = None
    suggested_price:  Optional[float] = None
    best_supplier:    Optional[str]   = None
    best_supplier_price: Optional[float] = None
    recent_history:   list[PriceRecord] = []    # 3 dòng gần nhất (table)
    chart_data:       list[PriceRecord] = []    # 12 tháng (sparkline)
    supplier_compare: list[SupplierStat] = []   # so sánh NCC


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

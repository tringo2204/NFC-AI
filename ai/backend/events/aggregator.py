"""
Event Aggregator — chuyển raw Odoo field_change thành semantic business event.

Tại sao cần:
  User gõ "150" → "1500" → "15000" → "150000" = 4 raw events.
  Chỉ gọi LLM 1 lần khi user dừng nhập (debounce ở OWL widget).
  Aggregator nhận event đã debounced và gán semantic event_type.
"""
from dataclasses import dataclass

from ..schemas.decision import ERPEvent


@dataclass
class AggregationRule:
    model: str
    field: str | None          # None = match mọi field
    condition: str             # "any" | "value_changed" | "state_transition"
    from_state: str | None     # chỉ dùng khi condition = state_transition
    to_state: str | None
    event_type: str            # semantic name


# ── Routing table: raw event → semantic event_type ────────────────────────────
AGGREGATION_RULES: list[AggregationRule] = [
    # Purchase
    AggregationRule("purchase.order.line", "price_unit",       "any",              None,       None,        "price_input_completed"),
    AggregationRule("purchase.order.line", "product_id",       "any",              None,       None,        "product_selected"),
    AggregationRule("purchase.order",      "state",            "state_transition",  "draft",   "purchase",  "rfq_confirmed"),
    AggregationRule("purchase.order",      "state",            "state_transition",  "draft",   "sent",      "rfq_sent"),
    AggregationRule("purchase.order",      "amount_total",     "any",              None,       None,        "po_amount_changed"),

    # HR
    AggregationRule("hr.contract",         "wage",             "any",              None,       None,        "salary_input_completed"),
    AggregationRule("hr.contract",         "state",            "state_transition",  "draft",   "open",      "contract_activated"),

    # Stock
    AggregationRule("stock.quant",         "quantity",         "any",              None,       None,        "stock_quantity_changed"),

    # Sale
    AggregationRule("sale.order.line",     "price_unit",       "any",              None,       None,        "price_input_completed"),

    # Account
    AggregationRule("account.move",        "invoice_date_due", "any",              None,       None,        "payment_due_approaching"),
]


class EventAggregator:
    """
    Nhận ERPEvent thô, trả về cùng event với event_type đã được resolve.
    Nếu không match rule nào → event_type = "unknown", agent sẽ bỏ qua.
    """

    def __init__(self, rules: list[AggregationRule] = AGGREGATION_RULES):
        self.rules = rules

    def resolve(self, event: ERPEvent) -> ERPEvent:
        for rule in self.rules:
            if rule.model != event.model:
                continue
            if rule.field and rule.field != event.field:
                continue
            if rule.condition == "state_transition":
                old = event.context.get("old_value")
                new = event.value
                if rule.from_state and old != rule.from_state:
                    continue
                if rule.to_state and new != rule.to_state:
                    continue
            # Match!
            event.event_type = rule.event_type
            return event

        event.event_type = "unknown"
        return event

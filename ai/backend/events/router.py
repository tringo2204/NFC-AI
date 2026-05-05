"""
Domain Router — config-driven routing (model, event_type) → scoped tool list.

LLM chỉ thấy tools trong scope của nó.
  - Giảm token (3 tool descriptions thay vì 17+)
  - Tăng determinism: purchase agent không thể gọi get_salary_benchmark()
  - Dễ debug: biết chính xác tool nào có thể được gọi
"""
from dataclasses import dataclass, field


@dataclass
class DomainRoute:
    model: str
    event_type: str
    tools: list[str]                  # tên tools trong Tool Registry
    system_prompt_hint: str = ""      # gợi ý thêm cho LLM về context


DOMAIN_ROUTES: list[DomainRoute] = [
    # ── Purchase ──────────────────────────────────────────────────────────────
    DomainRoute(
        model="purchase.order.line",
        event_type="price_input_completed",
        tools=["get_price_history", "get_supplier_comparison", "get_price_volatility"],
        system_prompt_hint="Phân tích giá nhập từ góc độ mua hàng: so sánh với lịch sử, benchmark thị trường.",
    ),
    DomainRoute(
        model="purchase.order.line",
        event_type="product_selected",
        tools=["get_price_history", "get_supplier_comparison"],
        system_prompt_hint="Sản phẩm vừa được chọn. Cung cấp thông tin nền về giá và supplier.",
    ),
    DomainRoute(
        model="purchase.order",
        event_type="rfq_confirmed",
        tools=["get_supplier_score", "get_budget_compliance", "get_market_benchmark"],
        system_prompt_hint="RFQ vừa được xác nhận thành PO. Đánh giá toàn diện: supplier, budget, benchmark.",
    ),
    DomainRoute(
        model="purchase.order",
        event_type="po_amount_changed",
        tools=["get_budget_compliance", "get_market_benchmark"],
        system_prompt_hint="Tổng giá trị PO thay đổi. Kiểm tra ngưỡng duyệt BGĐ và budget compliance.",
    ),
    DomainRoute(
        model="purchase.request.line",
        event_type="price_input_completed",
        tools=["get_price_history", "get_supplier_comparison", "get_price_volatility"],
        system_prompt_hint="Đây là Đơn giá ước tính trên Yêu cầu mua (PR), chưa phải PO. So sánh với lịch sử mua thực để điền mức giá hợp lý trước khi duyệt.",
    ),
    DomainRoute(
        model="purchase.request.line",
        event_type="product_selected",
        tools=["get_price_history", "get_supplier_comparison"],
        system_prompt_hint="Sản phẩm vừa chọn trên dòng PR. Gợi ý mức giá ước tính dựa trên lịch sử mua.",
    ),

    # ── HR ────────────────────────────────────────────────────────────────────
    DomainRoute(
        model="hr.contract",
        event_type="salary_input_completed",
        tools=["get_salary_benchmark", "get_headcount_trend"],
        system_prompt_hint="Mức lương vừa được nhập. So sánh với benchmark thị trường và nội bộ.",
    ),
    DomainRoute(
        model="hr.contract",
        event_type="contract_activated",
        tools=["get_retention_risk", "get_performance_context"],
        system_prompt_hint="Hợp đồng vừa kích hoạt. Đánh giá rủi ro giữ chân nhân viên.",
    ),

    # ── Stock ─────────────────────────────────────────────────────────────────
    DomainRoute(
        model="stock.quant",
        event_type="stock_quantity_changed",
        tools=["get_reorder_suggestion", "get_demand_forecast", "get_lead_time_risk"],
        system_prompt_hint="Tồn kho thay đổi. Đánh giá nguy cơ thiếu hàng và đề xuất đặt hàng.",
    ),

    # ── Sale ──────────────────────────────────────────────────────────────────
    DomainRoute(
        model="sale.order.line",
        event_type="price_input_completed",
        tools=["get_margin_analysis", "get_discount_benchmark"],
        system_prompt_hint="Giá bán vừa nhập. Phân tích margin và so với mức chiết khấu điển hình.",
    ),
]

# Index để lookup nhanh
_ROUTE_INDEX: dict[tuple[str, str], DomainRoute] = {
    (r.model, r.event_type): r for r in DOMAIN_ROUTES
}


class DomainRouter:
    def route(self, model: str, event_type: str) -> DomainRoute | None:
        """Trả về DomainRoute nếu có, None nếu không match."""
        return _ROUTE_INDEX.get((model, event_type))

    def get_tools(self, model: str, event_type: str) -> list[str]:
        route = self.route(model, event_type)
        return route.tools if route else []

    def get_system_hint(self, model: str, event_type: str) -> str:
        route = self.route(model, event_type)
        return route.system_prompt_hint if route else ""

"""
PriceAnalyzer — tính DecisionOutput từ SQL thuần, không gọi LLM.

Flow:
  ERPEvent (product_id / record_id + price_unit)
    → query get_price_history   (6 tháng, mọi NCC)
    → query get_supplier_comparison (12 tháng)
    → tính avg / deviation / level
    → build DecisionOutput với price_context đầy đủ
    → trả về ngay (< 200ms, 0 token)
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

from ..db.adapter import OdooQuery, SessionLocal
from ..schemas.decision import (
    DecisionOutput,
    ERPEvent,
    PriceContext,
    PriceRecord,
    SupplierStat,
)

# ── Hằng số ──────────────────────────────────────────────────────────────────

_LEVEL_THRESHOLDS = [
    (5,  "good"),
    (15, "normal"),
    (30, "high"),
]
# > 30% → critical


def _classify(deviation_pct: float) -> str:
    abs_dev = abs(deviation_pct)
    for threshold, level in _LEVEL_THRESHOLDS:
        if abs_dev <= threshold:
            return level
    return "critical"


def _fmt_vnd(amount: float) -> str:
    """Định dạng số tiền VND gọn: 1.250.000 → '1.25M' hoặc '125k'."""
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}M"
    if amount >= 1_000:
        return f"{amount / 1_000:.0f}k"
    return str(int(amount))


def _build_message(
    current_price: float,
    avg_price: float,
    deviation_pct: float,
    best_supplier: str | None,
    months: int,
) -> str:
    """Sinh câu nhận xét ngắn (≤ 150 ký tự) bằng template Python."""
    direction = "cao hơn" if deviation_pct > 0 else "thấp hơn"
    abs_dev = abs(round(deviation_pct, 1))
    avg_str = _fmt_vnd(avg_price)
    cur_str = _fmt_vnd(current_price)
    msg = f"Giá {cur_str} {direction} {abs_dev}% so với TB {months}T ({avg_str})"
    if best_supplier and deviation_pct > 5:
        msg += f". NCC tốt nhất: {best_supplier}"
    return msg[:150]


def _build_suggestion(deviation_pct: float, suggested_price: float | None) -> str | None:
    if deviation_pct <= 5:
        return None
    if suggested_price:
        return f"Thương lượng về mức {_fmt_vnd(suggested_price)}đ (−5% so với TB)"
    if deviation_pct > 15:
        return "Cân nhắc lấy thêm báo giá từ NCC khác"
    return None


# ── SQL helpers ───────────────────────────────────────────────────────────────

_SQL_HISTORY = """
    SELECT
        po.date_order::date          AS date,
        pol.price_unit               AS price,
        rp.name                      AS supplier,
        pol.product_qty              AS qty,
        po.name                      AS po_ref
    FROM purchase_order_line pol
    JOIN purchase_order po ON po.id  = pol.order_id
    JOIN res_partner   rp ON rp.id  = po.partner_id
    WHERE pol.product_id = :product_id
      AND po.state IN ('purchase', 'done')
      AND po.date_order >= NOW() - make_interval(months => :months)
    ORDER BY po.date_order DESC
    LIMIT 50
"""

_SQL_COMPARE = """
    SELECT
        rp.name                          AS supplier,
        MIN(pol.price_unit)              AS min_price,
        MAX(pol.price_unit)              AS max_price,
        ROUND(AVG(pol.price_unit), 0)    AS avg_price,
        COUNT(*)                         AS count,
        MAX(po.date_order)::date         AS last_date
    FROM purchase_order_line pol
    JOIN purchase_order po ON po.id  = pol.order_id
    JOIN res_partner   rp ON rp.id  = po.partner_id
    WHERE pol.product_id = :product_id
      AND po.state IN ('purchase', 'done')
      AND po.date_order >= NOW() - INTERVAL '12 months'
    GROUP BY rp.id, rp.name
    ORDER BY avg_price ASC
"""

_SQL_PRODUCT_FROM_LINE = """
    SELECT product_id FROM purchase_order_line WHERE id = :line_id
"""

_SQL_PRODUCT_FROM_PR_LINE = """
    SELECT product_id FROM purchase_request_line WHERE id = :line_id
"""


# ── Main analyzer ─────────────────────────────────────────────────────────────

class PriceAnalyzer:
    """Thay thế LangGraph agent cho endpoint /api/insight."""

    HISTORY_MONTHS = 6
    COMPARE_MONTHS = 12

    def analyze(self, event: ERPEvent) -> DecisionOutput:
        current_price = float(event.value or 0)
        if current_price <= 0:
            return DecisionOutput(
                level="no_data",
                message="Chưa có giá để phân tích.",
                confidence="low",
                data_points=0,
            )

        db = SessionLocal()
        try:
            q = OdooQuery(db)
            product_id = self._resolve_product_id(q, event)

            if not product_id:
                return DecisionOutput(
                    level="no_data",
                    message="Không xác định được sản phẩm.",
                    confidence="low",
                    data_points=0,
                )

            # ── Query history + compare ───────────────────────────────────
            history_rows = q.fetch(_SQL_HISTORY, product_id=product_id, months=self.HISTORY_MONTHS)
            compare_rows = q.fetch(_SQL_COMPARE, product_id=product_id)

            if not history_rows:
                return DecisionOutput(
                    level="no_data",
                    message="Chưa có lịch sử mua hàng để so sánh.",
                    confidence="low",
                    data_points=0,
                )

            # ── Tính toán ─────────────────────────────────────────────────
            prices = [float(r["price"]) for r in history_rows if r["price"]]
            avg_price = statistics.mean(prices)
            min_price = min(prices)
            max_price = max(prices)
            deviation_pct = ((current_price - avg_price) / avg_price) * 100 if avg_price else 0
            suggested_price = round(avg_price * 0.95, 0) if deviation_pct > 5 else None

            level = _classify(deviation_pct)

            # ── Best supplier (lowest avg) ────────────────────────────────
            best_supplier = compare_rows[0]["supplier"] if compare_rows else None
            best_supplier_price = float(compare_rows[0]["avg_price"]) if compare_rows else None

            # ── Build price_context ───────────────────────────────────────
            recent_3 = history_rows[:3]
            chart_data_sorted = sorted(history_rows, key=lambda r: str(r["date"]))

            price_context = PriceContext(
                avg_price=round(avg_price, 0),
                min_price=round(min_price, 0),
                max_price=round(max_price, 0),
                suggested_price=suggested_price,
                best_supplier=best_supplier,
                best_supplier_price=best_supplier_price,
                recent_history=[
                    PriceRecord(
                        date=str(r["date"]),
                        price=float(r["price"]),
                        supplier=str(r["supplier"]),
                        qty=float(r.get("qty") or 0),
                    )
                    for r in recent_3
                ],
                chart_data=[
                    PriceRecord(
                        date=str(r["date"]),
                        price=float(r["price"]),
                        supplier=str(r["supplier"]),
                        qty=float(r.get("qty") or 0),
                    )
                    for r in chart_data_sorted
                ],
                supplier_compare=[
                    SupplierStat(
                        supplier=str(r["supplier"]),
                        avg_price=float(r["avg_price"]),
                        min_price=float(r["min_price"]),
                        max_price=float(r["max_price"]),
                        count=int(r["count"]),
                        last_date=str(r["last_date"]) if r["last_date"] else "",
                    )
                    for r in compare_rows
                ],
            )

            message = _build_message(
                current_price, avg_price, deviation_pct,
                best_supplier, self.HISTORY_MONTHS,
            )
            suggestion = _build_suggestion(deviation_pct, suggested_price)

            return DecisionOutput(
                level=level,
                deviation_pct=round(deviation_pct, 1),
                message=message,
                suggestion=suggestion,
                price_context=price_context,
                actions=[],
                confidence="high" if len(prices) >= 5 else "medium" if len(prices) >= 2 else "low",
                data_points=len(prices),
                tools_used=["price_history_sql", "supplier_comparison_sql"],
                cached=False,
            )

        finally:
            db.close()

    def _resolve_product_id(self, q: OdooQuery, event: ERPEvent) -> int | None:
        """Tìm product_id từ context hoặc record_id."""
        # Ưu tiên từ context nếu frontend đã gửi
        if event.context.get("product_id"):
            return int(event.context["product_id"])

        if not event.record_id:
            return None

        if event.model == "purchase.order.line":
            row = q.fetch_one(_SQL_PRODUCT_FROM_LINE, line_id=event.record_id)
        elif event.model == "purchase.request.line":
            row = q.fetch_one(_SQL_PRODUCT_FROM_PR_LINE, line_id=event.record_id)
        else:
            return None

        return int(row["product_id"]) if row and row.get("product_id") else None

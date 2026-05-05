"""get_supplier_score — điểm tổng hợp supplier: on-time, quality, price."""
from ..registry import tool
from ...db.adapter import OdooQuery


@tool
def get_supplier_score(q: OdooQuery, partner_id: int) -> dict | None:
    """
    Tính điểm tổng hợp của supplier dựa trên lịch sử giao hàng thực tế.
    Dùng khi cần đánh giá uy tín supplier hoặc so sánh để chọn nhà cung cấp.
    Trả về: score (0–100), on_time_rate (%), avg_delay_days, total_orders, qa_fail_count.
    Score = 60% on-time + 40% (1 - qa_fail_rate).
    """
    return q.fetch_one(
        """
        WITH delivery_stats AS (
            SELECT
                COUNT(sp.id)                                                 AS total_pickings,
                COUNT(sp.id) FILTER (
                    WHERE sp.date_done <= sp.scheduled_date
                       OR sp.scheduled_date IS NULL
                )                                                            AS on_time_count,
                ROUND(AVG(
                    EXTRACT(EPOCH FROM (sp.date_done - sp.scheduled_date)) / 86400
                ) FILTER (WHERE sp.date_done > sp.scheduled_date), 1)       AS avg_delay_days,
                COUNT(sp.id) FILTER (
                    WHERE sp.nfc_qa_passed = FALSE AND sp.nfc_qa_required = TRUE
                )                                                            AS qa_fail_count
            FROM stock_picking sp
            JOIN purchase_order po ON po.id = sp.purchase_id
            WHERE po.partner_id = :partner_id
              AND sp.state = 'done'
              AND sp.date_done >= NOW() - INTERVAL '12 months'
        ),
        order_stats AS (
            SELECT COUNT(*) AS total_orders
            FROM purchase_order
            WHERE partner_id = :partner_id
              AND state IN ('purchase', 'done')
              AND date_order >= NOW() - INTERVAL '12 months'
        )
        SELECT
            ds.total_pickings,
            os.total_orders,
            COALESCE(ds.on_time_count, 0)                                   AS on_time_count,
            CASE WHEN ds.total_pickings > 0
                THEN ROUND(ds.on_time_count * 100.0 / ds.total_pickings, 1)
                ELSE NULL END                                               AS on_time_rate,
            COALESCE(ds.avg_delay_days, 0)                                  AS avg_delay_days,
            COALESCE(ds.qa_fail_count, 0)                                   AS qa_fail_count,
            CASE WHEN ds.total_pickings > 0 THEN
                ROUND(
                    (ds.on_time_count * 100.0 / ds.total_pickings) * 0.6
                    + (1 - ds.qa_fail_count::float / NULLIF(ds.total_pickings, 0)) * 100 * 0.4
                , 1)
                ELSE NULL END                                               AS score
        FROM delivery_stats ds, order_stats os
        """,
        partner_id=partner_id,
    )

"""get_price_volatility — độ biến động giá và xu hướng."""
from ..registry import tool
from ...db.adapter import OdooQuery


@tool
def get_price_volatility(q: OdooQuery, product_id: int) -> dict | None:
    """
    Phân tích độ biến động giá mua trong 30 và 90 ngày gần nhất.
    Dùng khi đánh giá rủi ro giá: giá có ổn định không, xu hướng tăng hay giảm?
    Trả về: std_dev (độ lệch chuẩn), trend (tăng/giảm/ổn định), avg_30d, avg_90d, price_count.
    """
    return q.fetch_one(
        """
        SELECT
            ROUND(STDDEV(pol.price_unit)::numeric, 0)                        AS std_dev,
            ROUND(AVG(pol.price_unit) FILTER (
                WHERE po.date_order >= NOW() - INTERVAL '30 days')::numeric, 0) AS avg_30d,
            ROUND(AVG(pol.price_unit) FILTER (
                WHERE po.date_order >= NOW() - INTERVAL '90 days')::numeric, 0) AS avg_90d,
            COUNT(*) FILTER (
                WHERE po.date_order >= NOW() - INTERVAL '90 days')           AS price_count,
            CASE
                WHEN AVG(pol.price_unit) FILTER (WHERE po.date_order >= NOW() - INTERVAL '30 days')
                   > AVG(pol.price_unit) FILTER (WHERE po.date_order BETWEEN NOW() - INTERVAL '90 days'
                                                                          AND NOW() - INTERVAL '30 days')
                     * 1.05 THEN 'increasing'
                WHEN AVG(pol.price_unit) FILTER (WHERE po.date_order >= NOW() - INTERVAL '30 days')
                   < AVG(pol.price_unit) FILTER (WHERE po.date_order BETWEEN NOW() - INTERVAL '90 days'
                                                                          AND NOW() - INTERVAL '30 days')
                     * 0.95 THEN 'decreasing'
                ELSE 'stable'
            END AS trend
        FROM purchase_order_line pol
        JOIN purchase_order po ON po.id = pol.order_id
        WHERE pol.product_id = :product_id
          AND po.state IN ('purchase', 'done')
          AND po.date_order >= NOW() - INTERVAL '90 days'
        """,
        product_id=product_id,
    )

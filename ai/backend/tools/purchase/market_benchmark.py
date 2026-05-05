"""get_market_benchmark — benchmark giá nội bộ (min/max/avg/percentiles)."""
from ..registry import tool
from ...db.adapter import OdooQuery


@tool
def get_market_benchmark(q: OdooQuery, product_id: int) -> dict | None:
    """
    Tính benchmark giá mua nội bộ của sản phẩm từ toàn bộ lịch sử PO.
    Dùng khi cần biết "giá thị trường nội bộ" để đánh giá giá đang nhập có hợp lý không.
    Trả về: p25, p50 (median), p75, min, max, avg, best_supplier, sample_count.
    Lưu ý: benchmark này dựa trên data thực của doanh nghiệp — chính xác hơn giá thị trường ngoài.
    """
    return q.fetch_one(
        """
        WITH price_data AS (
            SELECT
                pol.price_unit,
                rp.name AS supplier
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            JOIN res_partner   rp ON rp.id = po.partner_id
            WHERE pol.product_id = :product_id
              AND po.state IN ('purchase', 'done')
        ),
        stats AS (
            SELECT
                ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price_unit)::numeric, 0) AS p25,
                ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY price_unit)::numeric, 0) AS p50,
                ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price_unit)::numeric, 0) AS p75,
                ROUND(MIN(price_unit)::numeric, 0)                                          AS min_price,
                ROUND(MAX(price_unit)::numeric, 0)                                          AS max_price,
                ROUND(AVG(price_unit)::numeric, 0)                                          AS avg_price,
                COUNT(*)                                                                     AS sample_count
            FROM price_data
        ),
        best AS (
            SELECT supplier
            FROM price_data
            ORDER BY price_unit ASC
            LIMIT 1
        )
        SELECT s.*, b.supplier AS best_supplier FROM stats s, best b
        """,
        product_id=product_id,
    )

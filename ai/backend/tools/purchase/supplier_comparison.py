"""get_supplier_comparison — so sánh giá giữa các supplier cho cùng sản phẩm."""
from ..registry import tool
from ...db.adapter import OdooQuery


@tool
def get_supplier_comparison(q: OdooQuery, product_id: int) -> list[dict]:
    """
    So sánh giá mua theo từng supplier trong 12 tháng gần nhất.
    Dùng khi cần chọn supplier tốt nhất hoặc đàm phán giá.
    Trả về: supplier, min_price, max_price, avg_price, count (số lần mua), last_date.
    """
    return q.fetch(
        """
        SELECT
            rp.name                          AS supplier,
            MIN(pol.price_unit)              AS min_price,
            MAX(pol.price_unit)              AS max_price,
            ROUND(AVG(pol.price_unit), 0)    AS avg_price,
            COUNT(*)                         AS order_count,
            MAX(po.date_order)::date         AS last_date,
            SUM(pol.product_qty)             AS total_qty
        FROM purchase_order_line pol
        JOIN purchase_order po ON po.id = pol.order_id
        JOIN res_partner   rp ON rp.id = po.partner_id
        WHERE pol.product_id = :product_id
          AND po.state IN ('purchase', 'done')
          AND po.date_order >= NOW() - INTERVAL '12 months'
        GROUP BY rp.id, rp.name
        ORDER BY avg_price ASC
        """,
        product_id=product_id,
    )

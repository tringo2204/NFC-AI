"""get_price_history — lịch sử giá mua theo product + supplier."""
from ..registry import tool
from ...db.adapter import OdooQuery


@tool
def get_price_history(q: OdooQuery, product_id: int, months: int = 6) -> list[dict]:
    """
    Lấy lịch sử giá mua của sản phẩm trong N tháng gần nhất.
    Dùng khi cần so sánh giá hiện tại với lịch sử giao dịch thực tế.
    Trả về các giao dịch PO đã xác nhận: date, price, supplier, qty, po_ref.
    Chỉ lấy PO ở trạng thái purchase hoặc done.
    """
    return q.fetch(
        """
        SELECT
            po.name                                  AS po_ref,
            po.date_order::date                      AS date,
            rp.name                                  AS supplier,
            pol.price_unit                           AS price,
            pol.product_qty                          AS qty,
            pol.product_qty * pol.price_unit         AS amount,
            uu.name                                  AS uom
        FROM purchase_order_line pol
        JOIN purchase_order po   ON po.id  = pol.order_id
        JOIN res_partner   rp   ON rp.id  = po.partner_id
        JOIN uom_uom       uu   ON uu.id  = pol.product_uom
        WHERE pol.product_id = :product_id
          AND po.state IN ('purchase', 'done')
          AND po.date_order >= NOW() - INTERVAL ':months months'
        ORDER BY po.date_order DESC
        LIMIT 30
        """,
        product_id=product_id,
        months=months,
    )

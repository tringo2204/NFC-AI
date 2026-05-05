"""get_price_history — lịch sử giá mua theo product, tùy chọn lọc theo NCC."""
from ..registry import tool
from ...db.adapter import OdooQuery


@tool
def get_price_history(
    q: OdooQuery,
    product_id: int,
    months: int = 6,
    partner_id: int | None = None,
) -> list[dict]:
    """
    Lấy lịch sử giá mua của sản phẩm trong N tháng gần nhất.
    Nếu truyền partner_id: chỉ các giao dịch với đúng nhà cung cấp đó (cùng NCC trên RFQ/PO).
    Nếu partner_id = None: mọi NCC nội bộ NFC.
    Trả về: date, price, supplier, qty, po_ref từ PO purchase/done.
    """
    sql = """
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
          AND po.date_order >= NOW() - make_interval(months => :months)
    """
    params: dict = {"product_id": product_id, "months": months}
    if partner_id is not None:
        sql += " AND po.partner_id = :partner_id"
        params["partner_id"] = partner_id
    sql += " ORDER BY po.date_order DESC LIMIT 30"
    return q.fetch(sql, **params)

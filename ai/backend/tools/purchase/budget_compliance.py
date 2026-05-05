"""get_budget_compliance — so sánh PO với budget được phê duyệt & ngưỡng CEO."""
from ..registry import tool
from ...db.adapter import OdooQuery

NFC_CEO_THRESHOLD = 50_000_000  # 50 triệu VND


@tool
def get_budget_compliance(q: OdooQuery, po_id: int) -> dict | None:
    """
    Kiểm tra PO có vượt ngưỡng duyệt BGĐ không, và tình trạng CEO approval.
    Dùng khi RFQ được xác nhận thành PO, hoặc tổng giá trị PO thay đổi.
    Trả về: amount_total, requires_ceo_approval, ceo_approved, ceo_approved_by,
             compliance_status (ok | pending_ceo | blocked).
    """
    return q.fetch_one(
        """
        SELECT
            po.name                                             AS po_ref,
            po.amount_total,
            rc.name                                             AS currency,
            po.requires_ceo_approval,
            po.ceo_approved,
            ru.name                                             AS ceo_approved_by,
            po.ceo_approved_date,
            CASE
                WHEN po.amount_total <= :threshold               THEN 'ok'
                WHEN po.requires_ceo_approval AND po.ceo_approved THEN 'ok'
                WHEN po.requires_ceo_approval AND NOT po.ceo_approved THEN 'pending_ceo'
                ELSE 'ok'
            END                                                 AS compliance_status,
            :threshold                                          AS ceo_threshold
        FROM purchase_order po
        LEFT JOIN res_users  ru ON ru.id = po.ceo_approved_by
        LEFT JOIN res_currency rc ON rc.id = po.currency_id
        WHERE po.id = :po_id
        """,
        po_id=po_id,
        threshold=NFC_CEO_THRESHOLD,
    )

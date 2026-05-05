from odoo import fields, models


class PurchaseOrderLine(models.Model):
    """Thêm field placeholder để OWL widget nfc_ai_insight có chỗ render."""
    _inherit = "purchase.order.line"

    nfc_ai_badge = fields.Char(
        string="AI Insight",
        compute="_compute_nfc_ai_badge",
        store=False,
    )

    def _compute_nfc_ai_badge(self):
        """Field luôn rỗng — OWL widget tự fetch data từ AI backend."""
        for rec in self:
            rec.nfc_ai_badge = ""

# -*- coding: utf-8 -*-
"""Cảnh báo chủ động: dòng PO có giá > 15% so với TB mua 6 tháng (≥3 giao dịch)."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    nfc_ai_price_risk = fields.Boolean(
        string="Có dòng giá vượt ngưỡng NFC",
        compute="_compute_nfc_ai_price_risk",
        help="Đơn giá cao hơn >15% so với trung bình mua 6 tháng (ít nhất 3 PO đã xác nhận).",
    )
    nfc_ai_price_risk_message = fields.Text(
        string="Chi tiết cảnh báo giá",
        compute="_compute_nfc_ai_price_risk",
    )

    def _nfc_avg_price_hist(self, product_id, exclude_order_id=None):
        self.env.cr.execute(
            """
            SELECT AVG(pol.price_unit), COUNT(*)
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE pol.product_id = %s
              AND po.state IN ('purchase', 'done')
              AND po.date_order >= (CURRENT_DATE - INTERVAL '6 months')
              AND (%s IS NULL OR pol.order_id != %s)
            """,
            (product_id, exclude_order_id, exclude_order_id),
        )
        row = self.env.cr.fetchone()
        if not row:
            return 0.0, 0
        avg, cnt = row[0], row[1]
        return (float(avg) if avg is not None else 0.0, int(cnt or 0))

    @api.depends("order_line", "order_line.product_id", "order_line.price_unit", "state")
    def _compute_nfc_ai_price_risk(self):
        threshold = 1.15
        min_hist = 3
        for order in self:
            order.nfc_ai_price_risk = False
            order.nfc_ai_price_risk_message = False
            if order.state not in ("draft", "sent"):
                continue
            lines = order.order_line.filtered(lambda l: l.product_id and l.price_unit)
            if not lines:
                continue
            exclude_oid = order.id if isinstance(order.id, int) else None
            parts = []
            for line in lines:
                avg, cnt = order._nfc_avg_price_hist(line.product_id.id, exclude_oid)
                if cnt < min_hist or avg <= 0:
                    continue
                if line.price_unit > avg * threshold:
                    pct = (line.price_unit - avg) / avg * 100.0
                    parts.append(
                        "%s: %s đ > TB %s đ (+%.0f%%)"
                        % (
                            line.product_id.display_name,
                            f"{line.price_unit:,.0f}".replace(",", "."),
                            f"{avg:,.0f}".replace(",", "."),
                            pct,
                        )
                    )
            if parts:
                order.nfc_ai_price_risk = True
                order.nfc_ai_price_risk_message = _(
                    "Một hoặc nhiều dòng có đơn giá cao hơn đáng kể so với lịch sử mua 6 tháng:\n\n%s\n\n"
                    "Vui lòng kiểm tra lại trước khi xác nhận đơn."
                ) % "\n".join(parts)

    def button_confirm(self):
        # Cùng thứ tự với nfc_purchase_request: gate báo giá trước, rồi cảnh báo giá AI.
        self._check_rfq_validation_gate()
        if not self.env.context.get("nfc_skip_price_risk"):
            self._compute_nfc_ai_price_risk()
            risky = self.filtered(lambda o: o.nfc_ai_price_risk)
            if risky:
                if len(self) > 1:
                    raise UserError(
                        _(
                            "Có đơn mua bị cảnh báo giá NFC AI. "
                            "Vui lòng xác nhận từng đơn một để xem chi tiết và quyết định."
                        )
                    )
                return {
                    "name": _("Cảnh báo giá — NFC AI"),
                    "type": "ir.actions.act_window",
                    "res_model": "nfc.ai.price.risk.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {
                        "default_purchase_order_id": risky[0].id,
                        "default_risk_message": risky[0].nfc_ai_price_risk_message or "",
                    },
                }
        return super().button_confirm()

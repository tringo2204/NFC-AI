# -*- coding: utf-8 -*-
from odoo import fields, models, _


class NfcAiPriceRiskWizard(models.TransientModel):
    _name = "nfc.ai.price.risk.wizard"
    _description = "Xác nhận PO khi NFC AI cảnh báo giá"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Đơn mua",
        required=True,
    )
    risk_message = fields.Text(string="Chi tiết", readonly=True)

    def action_confirm_anyway(self):
        self.ensure_one()
        if not self.purchase_order_id:
            return {"type": "ir.actions.act_window_close"}
        return self.purchase_order_id.with_context(nfc_skip_price_risk=True).button_confirm()

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}

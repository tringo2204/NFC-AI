# -*- coding: utf-8 -*-
"""Safety patch for purchase_requisition when order_id.currency_rate is 0 (missing rates)."""
from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Re-declare field để đảm bảo patch compute được Odoo ưu tiên hơn purchase_requisition
    price_total_cc = fields.Monetary(
        compute='_compute_price_total_cc',
        string="Company Subtotal",
        currency_field="company_currency_id",
        store=True,
    )

    @api.depends('price_subtotal', 'order_id.currency_rate')
    def _compute_price_total_cc(self):
        for line in self:
            rate = line.order_id.currency_rate
            if rate:
                line.price_total_cc = line.price_subtotal / rate
            else:
                # Avoid ZeroDivisionError — currency_rate = 0/NULL khi thiếu tỷ giá.
                # Đặt 1:1 tạm; user nên cấu hình tỷ giá trong Kế toán → Tiền tệ.
                line.price_total_cc = line.price_subtotal

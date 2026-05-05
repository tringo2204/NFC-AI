# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

NFC_PO_APPROVAL_LIMIT = 50_000_000  # 50 triệu VND


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_request_id = fields.Many2one(
        'purchase.request', string='Yêu Cầu Mua Hàng (PR)',
        index=True, ondelete='set null',
        copy=False,
    )
    pr_type = fields.Selection(
        related='purchase_request_id.pr_type',
        string='Loại PR', store=True,
    )

    # Validation gate: số lượng vendor báo giá & đính kèm bằng chứng
    vendor_quote_count = fields.Integer(
        string='Số vendor đã báo giá',
        default=0,
        help='Bắt buộc ≥ 3 vendor cho PR-SKU trước khi gửi duyệt (trừ trường hợp đặc biệt)',
    )
    has_quote_evidence = fields.Boolean(
        string='Đã đính kèm bằng chứng báo giá',
        help='Chụp màn hình email/Zalo, file PDF báo giá từ vendor',
    )
    bypass_quote_requirement = fields.Boolean(
        string='Bỏ qua yêu cầu ≥ 3 báo giá',
        help='Áp dụng khi đã có hợp đồng dài hạn hoặc vendor độc quyền',
    )
    bypass_reason = fields.Char(string='Lý do bỏ qua')

    # PO approval: requires CEO for high-value
    requires_ceo_approval = fields.Boolean(
        string='Cần BGĐ duyệt',
        compute='_compute_requires_ceo_approval', store=True,
    )
    ceo_approved = fields.Boolean(string='BGĐ đã duyệt', copy=False, tracking=True)
    ceo_approved_by = fields.Many2one('res.users', string='BGĐ duyệt bởi', copy=False)
    ceo_approved_date = fields.Datetime(string='Ngày BGĐ duyệt', copy=False)

    # ─────────────────────────────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('amount_total', 'currency_id')
    def _compute_requires_ceo_approval(self):
        for order in self:
            amount_vnd = order.amount_total
            if order.currency_id and order.currency_id.name != 'VND':
                try:
                    amount_vnd = order.currency_id._convert(
                        order.amount_total,
                        self.env.ref('base.VND', raise_if_not_found=False) or order.currency_id,
                        order.company_id,
                        fields.Date.today(),
                    )
                except Exception:
                    amount_vnd = order.amount_total
            order.requires_ceo_approval = amount_vnd >= NFC_PO_APPROVAL_LIMIT

    # ─────────────────────────────────────────────────────────────────────
    # Validation gate before confirm
    # ─────────────────────────────────────────────────────────────────────

    def _check_rfq_validation_gate(self):
        """Kiểm tra điều kiện trước khi xác nhận PO."""
        for order in self:
            pr_type = order.pr_type or (
                order.purchase_request_id.pr_type if order.purchase_request_id else 'operation'
            )
            if pr_type == 'sku' and not order.bypass_quote_requirement:
                if order.vendor_quote_count < 3:
                    raise UserError(_(
                        'PR-SKU yêu cầu ít nhất 3 báo giá từ vendor trước khi xác nhận.\n'
                        'Hiện tại: %d báo giá.\n'
                        'Nếu có lý do đặc biệt, hãy tích "Bỏ qua yêu cầu ≥ 3 báo giá" và ghi lý do.'
                    ) % order.vendor_quote_count)
                if not order.has_quote_evidence:
                    raise UserError(_(
                        'Vui lòng đính kèm bằng chứng báo giá (email, Zalo screenshot, PDF) '
                        'trước khi xác nhận PO.'
                    ))

    def button_confirm(self):
        self._check_rfq_validation_gate()
        return super().button_confirm()

    # ─────────────────────────────────────────────────────────────────────
    # CEO Approval
    # ─────────────────────────────────────────────────────────────────────

    def action_ceo_approve(self):
        for order in self:
            if not order.requires_ceo_approval:
                raise UserError(_('PO này không cần BGĐ duyệt (dưới hạn mức 50 triệu).'))
            order.ceo_approved = True
            order.ceo_approved_by = self.env.user
            order.ceo_approved_date = fields.Datetime.now()
            order.message_post(
                body=_('BGĐ đã phê duyệt PO (>50M) bởi %s') % self.env.user.name
            )

    def action_ceo_reject(self):
        for order in self:
            order.message_post(
                body=_('BGĐ từ chối phê duyệt PO bởi %s') % self.env.user.name
            )
            order.button_cancel()

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    purchase_request_id = fields.Many2one(
        'purchase.request',
        string='Yêu Cầu Mua Hàng (PR)',
        related='purchase_id.purchase_request_id',
        store=True,
    )
    nfc_pr_type = fields.Selection(
        related='purchase_request_id.pr_type',
        string='Loại PR',
        store=True,
    )
    # QA Gate fields
    nfc_qa_required = fields.Boolean(
        string='Cần QA',
        compute='_compute_nfc_qa_required',
        store=True,
        help='True khi PR-SKU. False khi PR-Operation / PR-Investment.',
    )
    nfc_qa_passed = fields.Boolean(
        string='QA Đã Pass',
        copy=False,
        tracking=True,
    )
    nfc_qa_note = fields.Text(string='Kết quả QA / Ghi chú kiểm định')
    nfc_qa_done_by = fields.Many2one('res.users', string='QA thực hiện bởi', copy=False)
    nfc_qa_date = fields.Datetime(string='Ngày QA', copy=False)

    @api.depends('nfc_pr_type')
    def _compute_nfc_qa_required(self):
        for picking in self:
            picking.nfc_qa_required = picking.nfc_pr_type == 'sku'

    # ─────────────────────────────────────────────────────────────────────
    # QA Actions
    # ─────────────────────────────────────────────────────────────────────

    def action_nfc_qa_pass(self):
        """QA xác nhận hàng đạt — cho phép chuyển vào kho chính."""
        for picking in self:
            if not picking.nfc_qa_required:
                raise UserError(_('Picking này không yêu cầu QA.'))
            picking.nfc_qa_passed = True
            picking.nfc_qa_done_by = self.env.user
            picking.nfc_qa_date = fields.Datetime.now()
            picking.message_post(
                body=_('QA PASS — Được phép nhập kho chính thức. Thực hiện bởi: %s') % self.env.user.name
            )

    def action_nfc_qa_fail(self):
        """QA xác nhận hàng không đạt — mở wizard để ghi chú và xử lý."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('QA Không Đạt — Ghi Nhận Lý Do'),
            'res_model': 'nfc.qa.fail.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_picking_id': self.id},
        }

    # ─────────────────────────────────────────────────────────────────────
    # Override validate — chặn nếu QA chưa pass (với SKU)
    # ─────────────────────────────────────────────────────────────────────

    def button_validate(self):
        for picking in self:
            if (
                picking.nfc_qa_required
                and not picking.nfc_qa_passed
                and picking.picking_type_code == 'incoming'
            ):
                raise UserError(_(
                    'Không thể xác nhận nhập kho khi QA chưa Pass!\n\n'
                    'Phiếu nhập: %s\n'
                    'Loại PR: SKU (Nguyên / Phụ liệu / Bao bì)\n\n'
                    'Vui lòng bấm "QA Pass" sau khi kiểm định xong.'
                ) % picking.name)
        return super().button_validate()

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class NfcQaFailWizard(models.TransientModel):
    _name = 'nfc.qa.fail.wizard'
    _description = 'Wizard QA Không Đạt'

    picking_id = fields.Many2one('stock.picking', string='Phiếu Nhận Hàng', required=True)
    fail_reason = fields.Text(string='Lý do không đạt', required=True)
    action = fields.Selection([
        ('return', 'Trả hàng lại NCC'),
        ('retest', 'Lấy mẫu lại / Kiểm định lại'),
        ('partial', 'Chấp nhận một phần (giảm cấp)'),
    ], string='Hành động xử lý', required=True, default='return')
    note = fields.Text(string='Ghi chú thêm')

    def action_confirm_fail(self):
        self.ensure_one()
        picking = self.picking_id
        picking.nfc_qa_passed = False
        picking.nfc_qa_note = f'FAIL — {self.fail_reason}\nXử lý: {dict(self._fields["action"].selection)[self.action]}\n{self.note or ""}'
        picking.nfc_qa_done_by = self.env.user
        picking.nfc_qa_date = fields.Datetime.now()
        picking.message_post(
            body=_(
                '<b>QA FAIL</b><br/>'
                'Lý do: %s<br/>'
                'Hành động: %s<br/>'
                'Thực hiện bởi: %s'
            ) % (
                self.fail_reason,
                dict(self._fields['action'].selection)[self.action],
                self.env.user.name,
            )
        )
        # Thông báo phòng Mua Hàng để xử lý PO
        if picking.purchase_id and picking.purchase_id.user_id:
            picking.purchase_id.message_post(
                body=_(
                    'Cảnh báo: QA Fail tại phiếu nhận hàng %s.<br/>'
                    'Lý do: %s — Cần liên hệ NCC xử lý.'
                ) % (picking.name, self.fail_reason),
                partner_ids=picking.purchase_id.user_id.partner_id.ids,
            )
        return {'type': 'ir.actions.act_window_close'}

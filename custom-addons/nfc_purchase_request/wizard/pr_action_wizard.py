# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PrActionWizard(models.TransientModel):
    _name = 'pr.action.wizard'
    _description = 'Wizard Duyệt / Từ Chối / Trả Về PR'

    request_id = fields.Many2one('purchase.request', string='PR', required=True)
    action = fields.Selection([
        ('approve', 'Duyệt'),
        ('reject', 'Từ Chối'),
        ('return', 'Trả Về Để Chỉnh Sửa'),
    ], string='Hành động', required=True)
    reason = fields.Text(string='Lý do / Ghi chú')

    @api.constrains('action', 'reason')
    def _check_reason_required(self):
        for wiz in self:
            if wiz.action in ('reject', 'return') and not wiz.reason:
                raise UserError(_('Vui lòng nhập lý do khi từ chối hoặc trả về PR.'))

    def action_confirm(self):
        self.ensure_one()
        pr = self.request_id
        if self.action == 'approve':
            if pr.pr_type == 'sku' and not pr.planning_confirmed:
                raise UserError(_(
                    'PR-SKU cần phòng Kế Hoạch xác nhận định mức (tích vào ô "Kế hoạch xác nhận") trước khi duyệt.'
                ))
            pr.state = 'approved'
            pr.message_post(body=_('Đã duyệt. %s') % (self.reason or ''))
            pr._send_notification('approved')

        elif self.action == 'reject':
            pr.reject_reason = self.reason
            pr.state = 'rejected'
            pr.message_post(body=_('Từ chối: %s') % self.reason)
            pr._send_notification('rejected')

        elif self.action == 'return':
            pr.reject_reason = self.reason
            pr.state = 'draft'
            pr.message_post(body=_('Trả về để chỉnh sửa: %s') % self.reason)

        return {'type': 'ir.actions.act_window_close'}

# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request (Yêu Cầu Mua Hàng)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ── Identity ─────────────────────────────────────────────────────────
    name = fields.Char(
        string='Số PR',
        readonly=True, copy=False, default='/',
        tracking=True,
    )
    pr_type = fields.Selection([
        ('sku', 'PR-SKU (Nguyên / Phụ liệu / Bao bì)'),
        ('investment', 'PR-Investment (Máy móc / Thiết bị)'),
        ('operation', 'PR-Operation (VPP / Dịch vụ / Khác)'),
    ], string='Loại PR', required=True, default='sku', tracking=True)

    # ── Source Reference ─────────────────────────────────────────────────
    source_type = fields.Selection([
        ('adhoc', 'Nhu cầu tức thời'),
        ('long_term_material', 'Hợp đồng NL dài hạn (≤12 tháng)'),
        ('long_term_service', 'Hợp đồng DV dài hạn'),
        ('production_plan', 'Từ kế hoạch sản xuất / MRP'),
    ], string='Nguồn phát sinh', required=True, default='adhoc', tracking=True)
    source_ref = fields.Char(string='Mã tham chiếu (HĐ / MO / Kế hoạch)')

    # ── Participants ──────────────────────────────────────────────────────
    requester_id = fields.Many2one(
        'res.users', string='Người yêu cầu',
        required=True, default=lambda self: self.env.user,
        tracking=True,
    )
    department_id = fields.Many2one(
        'hr.department', string='Phòng ban',
        compute='_compute_department', store=True,
    )
    approver_id = fields.Many2one(
        'res.users', string='Người duyệt (Manager)',
        compute='_compute_approver', store=True, readonly=False,
        tracking=True,
    )
    purchase_user_id = fields.Many2one(
        'res.users', string='Nhân viên MH phụ trách',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Công ty',
        required=True, default=lambda self: self.env.company,
    )

    # ── Dates ─────────────────────────────────────────────────────────────
    date_request = fields.Date(string='Ngày tạo PR', default=fields.Date.today, required=True)
    date_required = fields.Date(string='Ngày cần hàng', required=True, tracking=True)

    # ── State Machine ────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Bản Nháp'),
        ('submitted', 'Chờ Duyệt'),
        ('approved', 'Đã Duyệt'),
        ('accepted', 'MH Xác Nhận'),
        ('rejected', 'Bị Từ Chối'),
        ('cancelled', 'Đã Hủy'),
    ], string='Trạng Thái', default='draft', tracking=True, copy=False)

    reject_reason = fields.Text(string='Lý do từ chối / trả về', tracking=True)

    # ── Lines ─────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'purchase.request.line', 'request_id',
        string='Danh sách hàng hóa',
    )

    # ── Notes ────────────────────────────────────────────────────────────
    purpose = fields.Text(string='Mục đích sử dụng', required=True)
    note = fields.Html(string='Ghi chú thêm')

    # ── Linked documents ─────────────────────────────────────────────────
    rfq_ids = fields.One2many('purchase.order', 'purchase_request_id', string='RFQ / PO')
    rfq_count = fields.Integer(compute='_compute_rfq_count', string='Số RFQ/PO')

    # ── Investment-specific (chỉ hiện khi pr_type = investment) ──────────
    investment_amount = fields.Monetary(string='Ngân sách ước tính', currency_field='currency_id')
    investment_justification = fields.Text(string='Lý do đầu tư')
    asset_type = fields.Char(string='Loại tài sản / Thiết bị')

    currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ',
        default=lambda self: self.env.company.currency_id,
    )

    # ── SKU-specific ──────────────────────────────────────────────────────
    planning_confirmed = fields.Boolean(
        string='Kế hoạch xác nhận định mức',
        help='PR-SKU: Phòng Kế Hoạch đã đối soát định mức',
    )

    # ─────────────────────────────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('requester_id')
    def _compute_department(self):
        for rec in self:
            employee = self.env['hr.employee'].search(
                [('user_id', '=', rec.requester_id.id)], limit=1
            )
            rec.department_id = employee.department_id if employee else False

    @api.depends('requester_id')
    def _compute_approver(self):
        for rec in self:
            employee = self.env['hr.employee'].search(
                [('user_id', '=', rec.requester_id.id)], limit=1
            )
            if employee and employee.parent_id and employee.parent_id.user_id:
                rec.approver_id = employee.parent_id.user_id
            else:
                rec.approver_id = False

    def _compute_rfq_count(self):
        for rec in self:
            rec.rfq_count = len(rec.rfq_ids)

    # ─────────────────────────────────────────────────────────────────────
    # Sequence
    # ─────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.request') or '/'
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────
    # State transitions
    # ─────────────────────────────────────────────────────────────────────

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Vui lòng thêm ít nhất một mặt hàng trước khi gửi duyệt.'))
            if not rec.approver_id:
                raise UserError(_(
                    'Không tìm thấy người duyệt. '
                    'Vui lòng liên hệ HR để cập nhật thông tin quản lý trực tiếp.'
                ))
            rec.state = 'submitted'
            rec._send_notification('submitted')
        return True

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Chỉ có thể duyệt PR đang ở trạng thái Chờ Duyệt.'))
            if rec.pr_type == 'sku' and not rec.planning_confirmed:
                raise UserError(_(
                    'PR-SKU cần phòng Kế Hoạch xác nhận định mức trước khi duyệt.'
                ))
            rec.state = 'approved'
            rec._send_notification('approved')
        return True

    def action_return_to_draft(self):
        """Trả PR về Draft để chỉnh sửa (Manager hoặc Mua Hàng)."""
        for rec in self:
            if rec.state not in ('submitted', 'approved'):
                raise UserError(_('Chỉ có thể trả về PR đang ở trạng thái Chờ Duyệt hoặc Đã Duyệt.'))
            rec.state = 'draft'
            rec.reject_reason = False
        return True

    def action_accept(self):
        """Phòng Mua Hàng xác nhận."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Chỉ có thể xác nhận PR đã được Manager duyệt.'))
            rec.state = 'accepted'
            rec.purchase_user_id = self.env.user
            rec._send_notification('accepted')
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state in ('rejected', 'cancelled'):
                raise UserError(_('PR này đã được đóng.'))
            if rec.rfq_ids.filtered(lambda o: o.state not in ('cancel', 'draft')):
                raise UserError(_(
                    'Không thể hủy PR khi đã có RFQ/PO đang xử lý. '
                    'Vui lòng hủy các RFQ/PO trước.'
                ))
            rec.state = 'cancelled'
        return True

    def _send_notification(self, event):
        template_map = {
            'submitted': 'nfc_purchase_request.mail_template_pr_submitted',
            'approved': 'nfc_purchase_request.mail_template_pr_approved',
            'rejected': 'nfc_purchase_request.mail_template_pr_rejected',
            'accepted': 'nfc_purchase_request.mail_template_pr_accepted',
        }
        template_ref = template_map.get(event)
        if template_ref:
            template = self.env.ref(template_ref, raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=False)

    # ─────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────

    def action_create_rfq(self):
        """Tạo RFQ (Purchase Order in draft) từ PR."""
        self.ensure_one()
        if self.state != 'accepted':
            raise UserError(_('Chỉ tạo RFQ từ PR đã được Mua Hàng xác nhận.'))

        order_lines = []
        for line in self.line_ids:
            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.name,
                'product_qty': line.qty,
                'product_uom': line.uom_id.id,
                'price_unit': line.estimated_price or 0.0,
                'date_planned': self.date_required,
            }))

        rfq = self.env['purchase.order'].create({
            'partner_id': False,
            'purchase_request_id': self.id,
            'origin': self.name,
            'date_order': fields.Datetime.now(),
            'order_line': order_lines,
            'notes': f'Tạo từ {self.name} - {self.purpose}',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQ'),
            'res_model': 'purchase.order',
            'res_id': rfq.id,
            'view_mode': 'form',
        }

    def action_view_rfq(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQ / PO'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('purchase_request_id', '=', self.id)],
            'context': {'default_purchase_request_id': self.id},
        }

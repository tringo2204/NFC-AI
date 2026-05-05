# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'purchase.request', string='PR',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)

    # ── Product ───────────────────────────────────────────────────────────
    product_id = fields.Many2one(
        'product.product', string='Sản phẩm / Dịch vụ',
        domain=[('purchase_ok', '=', True)],
    )
    description = fields.Char(
        string='Mô tả',
        compute='_compute_description', store=True, readonly=False,
        required=True,
    )
    product_category_id = fields.Many2one(
        'product.category', string='Nhóm hàng',
        compute='_compute_product_category', store=True,
    )

    # ── Quantity & UoM ────────────────────────────────────────────────────
    qty = fields.Float(string='Số lượng', required=True, default=1.0)
    uom_id = fields.Many2one(
        'uom.uom', string='ĐVT',
        compute='_compute_uom', store=True, readonly=False,
        required=True,
    )
    uom_category_id = fields.Many2one(
        related='uom_id.category_id', string='Nhóm ĐVT',
    )

    # ── Price ────────────────────────────────────────────────────────────
    estimated_price = fields.Float(string='Đơn giá ước tính')
    subtotal = fields.Float(
        string='Thành tiền ước tính',
        compute='_compute_subtotal', store=True,
    )
    currency_id = fields.Many2one(related='request_id.currency_id')

    # ── Dates & Context ───────────────────────────────────────────────────
    date_required = fields.Date(
        string='Ngày cần',
        related='request_id.date_required', store=True,
    )

    # ── State (mirrored for domain/search) ────────────────────────────────
    request_state = fields.Selection(
        related='request_id.state', store=True, string='Trạng thái PR',
    )
    pr_type = fields.Selection(
        related='request_id.pr_type', store=True, string='Loại PR',
    )

    # ── Notes ────────────────────────────────────────────────────────────
    technical_spec = fields.Char(string='Quy cách / Thông số kỹ thuật')
    note = fields.Char(string='Ghi chú dòng')

    # ─────────────────────────────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.name
            elif not line.description:
                line.description = ''

    @api.depends('product_id')
    def _compute_uom(self):
        for line in self:
            if line.product_id and line.product_id.uom_po_id:
                line.uom_id = line.product_id.uom_po_id
            elif line.product_id:
                line.uom_id = line.product_id.uom_id

    @api.depends('product_id')
    def _compute_product_category(self):
        for line in self:
            line.product_category_id = line.product_id.categ_id if line.product_id else False

    @api.depends('qty', 'estimated_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * (line.estimated_price or 0.0)

    # ─────────────────────────────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────────────────────────────

    @api.constrains('qty')
    def _check_qty(self):
        for line in self:
            if line.qty <= 0:
                raise ValidationError(_('Số lượng phải lớn hơn 0.'))

# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    purchase_request_ids = fields.One2many(
        'purchase.request', 'requester_id',
        string='Yêu Cầu Mua Hàng',
    )
    approve_request_ids = fields.One2many(
        'purchase.request', 'approver_id',
        string='PR Cần Duyệt',
    )

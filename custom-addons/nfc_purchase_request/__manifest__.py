# -*- coding: utf-8 -*-
{
    'name': 'NFC Purchase Request',
    'version': '18.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Purchase Request (PR) workflow: SKU / Investment / Operation',
    'description': """
NFC Purchase Request Module
============================
Quản lý toàn bộ luồng Yêu Cầu Mua Hàng (PR) theo quy trình NFC:

- 3 loại PR: SKU (Nguyên liệu/PL/BB), Investment (Máy móc), Operation (VPP/DV)
- State machine: Draft → Submitted → Approved → Accepted / Rejected / Cancelled
- Auto-routing duyệt theo manager trực tiếp (hr.employee parent_id)
- Liên kết PR → RFQ → PO
- Phân biệt yêu cầu duyệt giá theo hạn mức (>50M → BGĐ duyệt)
    """,
    'author': 'NFC',
    'depends': [
        'purchase',
        'purchase_stock',
        'stock',
        'mail',
        'hr',
        'product',
        'account',
        'quality_control',
    ],
    'data': [
        'security/nfc_pr_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/mail_template.xml',
        'data/stock_data.xml',
        'data/nfc_approver_params.xml',
        'wizard/pr_action_wizard_views.xml',
        'wizard/qa_fail_wizard_views.xml',
        'views/purchase_request_views.xml',
        'views/purchase_request_line_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

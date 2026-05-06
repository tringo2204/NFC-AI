"""
Seed script: Cấu hình người duyệt RFQ theo loại PR.

Chạy từ Odoo shell:
  /opt/odoo18/odoo-bin shell -c /etc/odoo/nfc.conf -d nfc_erp < \
      /opt/odoo18/custom_addons/nfc_purchase_request/data/seed_rfq_approvers.py

Logic: tìm user theo tên, gán vào ir.config_parameter.
Điều chỉnh `name_hints` nếu tên nhân viên khác trên server.
"""

# Mapping: pr_type → danh sách từ khóa trong tên người dùng (case-insensitive)
APPROVER_HINTS = {
    'nfc.rfq_approver.sku':        ['hương', 'huong'],   # Chị Hương — Nguyên liệu / SKU
    'nfc.rfq_approver.investment': ['khâm',  'kham'],    # Anh Khâm  — Máy móc / Đầu tư
    'nfc.rfq_approver.operation':  ['ân',    'an'],      # Anh Ân    — Dịch vụ / Operation
}


def _find_user(env, keywords):
    """Tìm res.users đầu tiên có tên chứa một trong các từ khóa (case-insensitive)."""
    all_users = env['res.users'].search([('active', '=', True), ('share', '=', False)])
    for user in all_users:
        name_lower = (user.name or '').lower()
        if any(kw in name_lower for kw in keywords):
            return user
    return None


results = []
for param_key, hints in APPROVER_HINTS.items():
    user = _find_user(env, hints)
    param = env['ir.config_parameter'].sudo().search([('key', '=', param_key)], limit=1)
    if user:
        if param:
            param.sudo().write({'value': str(user.id)})
        else:
            env['ir.config_parameter'].sudo().set_param(param_key, str(user.id))
        results.append(f'  ✅ {param_key} → {user.name} (id={user.id})')
    else:
        results.append(f'  ⚠️  {param_key} → không tìm thấy user (hints={hints})')

env.cr.commit()

print('\n=== RFQ Approver Config ===')
for r in results:
    print(r)
print('===========================\n')

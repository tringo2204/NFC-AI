#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFC Transaction Data Seed Script
Tạo dữ liệu giao dịch: PR, RFQ, PO, Phiếu Nhập Kho, Hóa Đơn
Chạy: odoo-bin shell -c odoo.conf --no-http < seed_transactions.py
"""
from datetime import date, timedelta
import logging
from odoo import fields
_log = logging.getLogger(__name__)

today = date.today()
D = lambda n: today + timedelta(days=n)

# ── Load users và sản phẩm ─────────────────────────────────────────────────
company   = env['res.company'].browse(1)
user_sx   = env['res.users'].search([('login', '=', 'hung.vo.sx')],   limit=1)
user_nv   = env['res.users'].search([('login', '=', 'linh.pham')],    limit=1)
user_tp   = env['res.users'].search([('login', '=', 'huong.le')],     limit=1)
user_bgd  = env['res.users'].search([('login', '=', 'an.nguyen')],    limit=1)
user_kk   = env['res.users'].search([('login', '=', 'kham.tran')],    limit=1)
user_kho  = env['res.users'].search([('login', '=', 'minh.nguyen.kho')], limit=1)
user_qa   = env['res.users'].search([('login', '=', 'thu.tran.qa')],  limit=1)
user_kt   = env['res.users'].search([('login', '=', 'nga.hoang.kt')], limit=1)

def p(ref):
    prod = env['product.product'].search([('default_code', '=', ref)], limit=1)
    if not prod:
        print(f"  ⚠ Không tìm thấy sản phẩm: {ref}")
    return prod

def pt(ref):
    prod = env['product.template'].search([('default_code', '=', ref)], limit=1)
    return prod

def v(name_part):
    vendor = env['res.partner'].search([('name', 'ilike', name_part), ('supplier_rank', '>', 0)], limit=1)
    if not vendor:
        print(f"  ⚠ Không tìm thấy vendor: {name_part}")
    return vendor

ncc_nl1   = v('NÔNG SẢN SÀI GÒN')
ncc_nl2   = v('ĐỒNG NAI XANH')
ncc_bb1   = v('BAO BÌ TIẾN PHÁT')
ncc_bb2   = v('BÌNH DƯƠNG PRINT')
ncc_pl    = v('HÓA CHẤT PHỤ GIA')
ncc_may   = v('ANH KHOA')
ncc_van   = v('VẬN TẢI LẠNH')

kg  = env['uom.uom'].search([('name', '=', 'kg')], limit=1)
cai = env['uom.uom'].search([('name', '=', 'Cái')], limit=1)
hop = env['uom.uom'].search([('name', '=', 'Hộp')], limit=1)
cuon= env['uom.uom'].search([('name', '=', 'Cuộn')], limit=1)

print("=" * 65)
print("NFC — Seed Transaction Data")
print("=" * 65)

# ══════════════════════════════════════════════════════════════════════════════
# HELPER: tạo PR + lines (bypass state machine bằng write trực tiếp)
# ══════════════════════════════════════════════════════════════════════════════

PR_ctx = {'mail_create_nosubscribe': True, 'tracking_disable': True, 'mail_notrack': True}

def make_pr(requester, pr_type, source_type, purpose, date_required_delta,
            lines, state='draft', approver=None, purchase_user=None,
            planning_confirmed=False, reject_reason=None):
    vals = {
        'pr_type': pr_type,
        'source_type': source_type,
        'requester_id': requester.id,
        'purpose': purpose,
        'date_required': D(date_required_delta),
        'planning_confirmed': planning_confirmed,
        'company_id': company.id,
    }
    if approver:
        vals['approver_id'] = approver.id
    pr = env['purchase.request'].with_context(**PR_ctx).create(vals)
    for line_vals in lines:
        line_vals['request_id'] = pr.id
        env['purchase.request.line'].with_context(**PR_ctx).create(line_vals)
    # Set state trực tiếp (bypass validation email)
    state_vals = {'state': state}
    if state in ('accepted',) and purchase_user:
        state_vals['purchase_user_id'] = purchase_user.id
    if reject_reason:
        state_vals['reject_reason'] = reject_reason
    pr.with_context(**PR_ctx).write(state_vals)
    return pr

# ══════════════════════════════════════════════════════════════════════════════
# 1. PURCHASE REQUESTS
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Tạo Purchase Requests...")

# ── PR-1: Bản nháp — NV SX tạo mua nguyên liệu ───────────────────────────
pr1 = make_pr(
    requester=user_sx, pr_type='sku', source_type='production_plan',
    purpose='Mua nguyên liệu sản xuất iSOUP tháng 6/2026 theo kế hoạch SX-2026-06',
    date_required_delta=30,
    lines=[
        {'product_id': p('NL-DAU-TAY').id, 'description': 'Dâu Tây Tươi (Strawberry)', 'qty': 500, 'uom_id': kg.id, 'estimated_price': 85_000},
        {'product_id': p('NL-ATISO-DO').id,'description': 'Atiso Đỏ Sấy', 'qty': 120, 'uom_id': kg.id, 'estimated_price': 420_000},
        {'product_id': p('NL-LONG-NHAN').id,'description': 'Long Nhãn Sấy', 'qty': 80, 'uom_id': kg.id, 'estimated_price': 280_000},
    ],
    state='draft',
    approver=user_tp,
)
print(f"  ✓ {pr1.name} | Draft | NL iSOUP tháng 6")

# ── PR-2: Chờ duyệt — NV SX xin mua phụ liệu ────────────────────────────
pr2 = make_pr(
    requester=user_sx, pr_type='sku', source_type='long_term_material',
    purpose='Mua phụ liệu sản xuất tháng 5/2026 — hợp đồng HĐ-PL-2026-01',
    date_required_delta=14,
    planning_confirmed=True,
    lines=[
        {'product_id': p('PL-DUONG-TRANG').id, 'description': 'Đường Kính Trắng', 'qty': 2000, 'uom_id': kg.id, 'estimated_price': 22_000},
        {'product_id': p('PL-MUOI').id,         'description': 'Muối Tinh Chế', 'qty': 500, 'uom_id': kg.id, 'estimated_price': 8_500},
        {'product_id': p('PL-DAU-HD').id,        'description': 'Dầu Hướng Dương', 'qty': 300, 'uom_id': kg.id, 'estimated_price': 28_000},
        {'product_id': p('PL-BOT-NGOT').id,      'description': 'Bột Ngọt (Mono)', 'qty': 100, 'uom_id': kg.id, 'estimated_price': 42_000},
    ],
    state='submitted',
    approver=user_tp,
)
print(f"  ✓ {pr2.name} | Chờ Duyệt | Phụ liệu SX tháng 5")

# ── PR-3: Chờ duyệt — NV MH xin mua VPP ─────────────────────────────────
pr3 = make_pr(
    requester=user_nv, pr_type='operation', source_type='adhoc',
    purpose='Mua vật tư BHLD & VPP kho tháng 5/2026',
    date_required_delta=10,
    lines=[
        {'product_id': p('VPP-GANG-TAY').id,   'description': 'Găng Tay Nitrile (hộp 100 cái)', 'qty': 20, 'uom_id': hop.id, 'estimated_price': 95_000},
        {'product_id': p('VPP-KHAU-TRANG').id, 'description': 'Khẩu Trang Y Tế (hộp 50 cái)',  'qty': 15, 'uom_id': hop.id, 'estimated_price': 45_000},
        {'product_id': p('VPP-MUC-ZEBRA').id,  'description': 'Mực In Nhãn Máy Zebra', 'qty': 2, 'uom_id': cai.id, 'estimated_price': 850_000},
        {'product_id': p('VPP-GIAY-NHAN').id,  'description': 'Giấy In Nhãn Cuộn 4x6', 'qty': 5, 'uom_id': cuon.id, 'estimated_price': 220_000},
    ],
    state='submitted',
    approver=user_tp,
)
print(f"  ✓ {pr3.name} | Chờ Duyệt | VPP & BHLD")

# ── PR-4: Đã duyệt — NV SX mua nguyên liệu đặc biệt ─────────────────────
pr4 = make_pr(
    requester=user_sx, pr_type='sku', source_type='adhoc',
    purpose='Mua NL đặc biệt: Sâm HQ & Nấm Tuyết cho dòng sản phẩm PREMIUM Q2',
    date_required_delta=21,
    planning_confirmed=True,
    lines=[
        {'product_id': p('NL-SAM-HQ').id,    'description': 'Sâm Hàn Quốc Khô', 'qty': 50, 'uom_id': kg.id, 'estimated_price': 1_800_000},
        {'product_id': p('NL-NAM-TUYET').id, 'description': 'Nấm Tuyết Khô', 'qty': 30, 'uom_id': kg.id, 'estimated_price': 650_000},
        {'product_id': p('NL-TAO-DO').id,    'description': 'Táo Đỏ (Táo Tàu) Khô', 'qty': 100, 'uom_id': kg.id, 'estimated_price': 220_000},
    ],
    state='approved',
    approver=user_tp,
)
print(f"  ✓ {pr4.name} | Đã Duyệt | NL Premium (Sâm, Nấm Tuyết)")

# ── PR-5: Đã duyệt — TP Kỹ Thuật mua đầu tư máy móc ────────────────────
pr5 = make_pr(
    requester=user_kk, pr_type='investment', source_type='adhoc',
    purpose='Đầu tư máy seal ly nhựa tự động thay thế máy cũ đã hỏng',
    date_required_delta=45,
    lines=[
        {'product_id': False, 'description': 'Máy Seal Ly Nhựa Tự Động (Công suất 4.000 ly/h)', 'qty': 1, 'uom_id': cai.id, 'estimated_price': 85_000_000},
        {'product_id': False, 'description': 'Phụ kiện lắp đặt & vận chuyển', 'qty': 1, 'uom_id': cai.id, 'estimated_price': 5_000_000},
    ],
    state='approved',
    approver=user_bgd,
)
pr5.write({'investment_amount': 90_000_000, 'investment_justification': 'Máy seal hiện tại đã hỏng encoder, chi phí sửa > 50% giá máy mới. Đầu tư mới giúp tăng công suất 40%.', 'asset_type': 'Máy Móc Sản Xuất'})
print(f"  ✓ {pr5.name} | Đã Duyệt | Investment: Máy Seal 90M VND")

# ── PR-6: MH Xác Nhận → có 2 RFQ ─────────────────────────────────────────
pr6 = make_pr(
    requester=user_nv, pr_type='sku', source_type='production_plan',
    purpose='Mua bao bì cho đợt sản xuất tháng 5 — iSOUP, HUUPS, iCHILL',
    date_required_delta=12,
    planning_confirmed=True,
    lines=[
        {'product_id': p('BB-HOP-ISOUP-30G').id, 'description': 'Hộp Giấy iSOUP 30g', 'qty': 50_000, 'uom_id': cai.id, 'estimated_price': 2_800},
        {'product_id': p('BB-LY-HUUPS-14G').id,  'description': 'Ly Nhựa HUUPS 14g',   'qty': 30_000, 'uom_id': cai.id, 'estimated_price': 1_500},
        {'product_id': p('BB-LY-ICHILL-29G').id, 'description': 'Ly Nhựa iCHILL 29g',  'qty': 20_000, 'uom_id': cai.id, 'estimated_price': 1_800},
        {'product_id': p('BB-NHAN-ISOUP').id,    'description': 'Nhãn In Decal iSOUP',  'qty': 10, 'uom_id': cuon.id, 'estimated_price': 450_000},
    ],
    state='accepted',
    approver=user_tp,
    purchase_user=user_nv,
)
print(f"  ✓ {pr6.name} | MH Xác Nhận | Bao bì iSOUP + HUUPS (→ sẽ tạo RFQ)")

# ── PR-7: MH Xác Nhận → PO đã xác nhận (< 50M) ──────────────────────────
pr7 = make_pr(
    requester=user_nv, pr_type='sku', source_type='long_term_material',
    purpose='Mua NL Cá Hồi & Tôm Biển cho sản xuất batch SX-2026-05-B — HĐ NL-2026-02',
    date_required_delta=7,
    planning_confirmed=True,
    lines=[
        {'product_id': p('NL-CA-HOI').id,  'description': 'Cá Hồi Phi Lê (Đông Lạnh)', 'qty': 150, 'uom_id': kg.id, 'estimated_price': 480_000},
        {'product_id': p('NL-TOM-BIEN').id,'description': 'Tôm Biển Khô', 'qty': 80, 'uom_id': kg.id, 'estimated_price': 520_000},
        {'product_id': p('NL-HAI-SAN').id, 'description': 'Hải Sản Hỗn Hợp (Đông Lạnh)', 'qty': 60, 'uom_id': kg.id, 'estimated_price': 185_000},
    ],
    state='accepted',
    approver=user_tp,
    purchase_user=user_nv,
)
print(f"  ✓ {pr7.name} | MH Xác Nhận | Cá Hồi + Tôm Biển (→ sẽ tạo PO < 50M)")

# ── PR-8: MH Xác Nhận → PO cần BGĐ duyệt (> 50M) ────────────────────────
pr8 = make_pr(
    requester=user_nv, pr_type='sku', source_type='adhoc',
    purpose='Mua NL Sâm & Hương Liệu dự trữ cho Q3/2026 — ưu tiên mua khi giá tốt',
    date_required_delta=20,
    planning_confirmed=True,
    lines=[
        {'product_id': p('NL-SAM-HQ').id,   'description': 'Sâm Hàn Quốc Khô', 'qty': 30, 'uom_id': kg.id, 'estimated_price': 1_800_000},
        {'product_id': p('PL-HL-DAU').id,   'description': 'Hương Liệu Tự Nhiên Dâu', 'qty': 20, 'uom_id': kg.id, 'estimated_price': 850_000},
        {'product_id': p('PL-MAU-DO').id,   'description': 'Màu Thực Phẩm Đỏ Tự Nhiên', 'qty': 10, 'uom_id': kg.id, 'estimated_price': 1_200_000},
    ],
    state='accepted',
    approver=user_tp,
    purchase_user=user_nv,
)
print(f"  ✓ {pr8.name} | MH Xác Nhận | Sâm + Hương Liệu (→ sẽ tạo PO > 50M, cần BGĐ)")

# ── PR-9: Bị từ chối ─────────────────────────────────────────────────────
pr9 = make_pr(
    requester=user_sx, pr_type='sku', source_type='adhoc',
    purpose='Mua thêm Rong Biển dự trữ thêm 6 tháng',
    date_required_delta=30,
    lines=[
        {'product_id': p('NL-RONG-BIEN').id,'description': 'Rong Biển Khô', 'qty': 500, 'uom_id': kg.id, 'estimated_price': 290_000},
    ],
    state='rejected',
    approver=user_tp,
    reject_reason='Tồn kho hiện tại còn 800kg, đủ dùng đến tháng 9. Đề nghị trả lại, tạo PR lại khi sắp hết (tháng 8).',
)
print(f"  ✓ {pr9.name} | Bị Từ Chối | Rong Biển dự trữ")

# ── PR-10: Hủy ───────────────────────────────────────────────────────────
pr10 = make_pr(
    requester=user_nv, pr_type='operation', source_type='adhoc',
    purpose='Thuê xe vận chuyển mẫu đi triển lãm Food Expo 2026',
    date_required_delta=5,
    lines=[
        {'product_id': False, 'description': 'Thuê xe tải lạnh 5 tấn (1 ngày)', 'qty': 1, 'uom_id': cai.id, 'estimated_price': 3_500_000},
    ],
    state='cancelled',
    approver=user_tp,
)
print(f"  ✓ {pr10.name} | Đã Hủy | Thuê xe triển lãm")

env.cr.commit()
print(f"\n  → Đã tạo 10 PR [{pr1.name} → {pr10.name}]")

# ══════════════════════════════════════════════════════════════════════════════
# 2. RFQ (Request For Quotation)
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Tạo RFQ (Báo giá từ nhà cung cấp)...")

PO_ctx = {'mail_create_nosubscribe': True, 'tracking_disable': True}

def make_rfq(pr, vendor, lines_override=None, vendor_quote_count=1, has_evidence=False,
             bypass=False, bypass_reason='', state='draft'):
    """Tạo RFQ (purchase.order ở trạng thái draft hoặc sent)."""
    order_lines = []
    for pr_line in pr.line_ids:
        price = (lines_override or {}).get(pr_line.product_id.default_code, pr_line.estimated_price)
        order_lines.append((0, 0, {
            'product_id': pr_line.product_id.id if pr_line.product_id else False,
            'name': pr_line.description,
            'product_qty': pr_line.qty,
            'product_uom': pr_line.uom_id.id,
            'price_unit': price,
            'date_planned': pr.date_required,
        }))
    rfq = env['purchase.order'].with_context(**PO_ctx).create({
        'partner_id': vendor.id if vendor else False,
        'purchase_request_id': pr.id,
        'origin': pr.name,
        'date_order': fields.Datetime.now(),
        'order_line': order_lines,
        'vendor_quote_count': vendor_quote_count,
        'has_quote_evidence': has_evidence,
        'bypass_quote_requirement': bypass,
        'bypass_reason': bypass_reason,
        'notes': f'RFQ cho {pr.name} — {pr.purpose[:60]}',
    })
    return rfq

# RFQ-A: PR-6 / Bao bì — Tiến Phát (báo giá 1)
rfq_a = make_rfq(pr6, ncc_bb1, vendor_quote_count=1, has_evidence=False,
    lines_override={
        'BB-HOP-ISOUP-30G': 2_750, 'BB-LY-HUUPS-14G': 1_480,
        'BB-LY-ICHILL-29G': 1_760, 'BB-NHAN-ISOUP': 440_000,
    })
print(f"  ✓ RFQ {rfq_a.name} | PR-6 Bao Bì | NCC: Tiến Phát | {rfq_a.amount_total:,.0f} VND")

# RFQ-B: PR-6 / Bao bì — BD Print (báo giá 2)
rfq_b = make_rfq(pr6, ncc_bb2, vendor_quote_count=1, has_evidence=False,
    lines_override={
        'BB-HOP-ISOUP-30G': 2_900, 'BB-LY-HUUPS-14G': 1_550,
        'BB-LY-ICHILL-29G': 1_820, 'BB-NHAN-ISOUP': 460_000,
    })
print(f"  ✓ RFQ {rfq_b.name} | PR-6 Bao Bì | NCC: BD Print | {rfq_b.amount_total:,.0f} VND")

# RFQ-C: PR-6 / 1 NCC nữa — đủ 3 báo giá, đã có bằng chứng
rfq_c = make_rfq(pr6, ncc_nl2, vendor_quote_count=3, has_evidence=True,
    lines_override={
        'BB-HOP-ISOUP-30G': 2_820, 'BB-LY-HUUPS-14G': 1_510,
        'BB-LY-ICHILL-29G': 1_790, 'BB-NHAN-ISOUP': 455_000,
    })
# Update tổng quote count trên tất cả RFQ của PR6
rfq_a.vendor_quote_count = 3
rfq_a.has_quote_evidence = True
rfq_b.vendor_quote_count = 3
rfq_b.has_quote_evidence = True
print(f"  ✓ RFQ {rfq_c.name} | PR-6 Bao Bì | NCC: Đồng Nai Xanh | 3 báo giá ✓")

# RFQ-D: PR-4 / NL Premium — NCC Nông Sản (đã bypass vì vendor độc quyền)
rfq_d = make_rfq(pr4, ncc_nl1, vendor_quote_count=1, has_evidence=True,
    bypass=True, bypass_reason='Vendor độc quyền nhập khẩu Sâm HQ, chỉ có 1 nguồn cung',
    lines_override={
        'NL-SAM-HQ': 1_750_000, 'NL-NAM-TUYET': 640_000, 'NL-TAO-DO': 215_000,
    })
print(f"  ✓ RFQ {rfq_d.name} | PR-4 NL Premium | NCC: Nông Sản SG | Bypass 3-quote ✓")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 3. PURCHASE ORDERS (Xác nhận)
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Tạo Purchase Orders (đã xác nhận)...")

def make_po(pr, vendor, lines_data, vendor_quote_count=3, has_evidence=True,
            bypass=False, bypass_reason='', ceo_approved=False, confirm=True):
    order_lines = []
    for ld in lines_data:
        prod = p(ld['ref']) if ld.get('ref') else None
        order_lines.append((0, 0, {
            'product_id': prod.id if prod else False,
            'name': ld['name'],
            'product_qty': ld['qty'],
            'product_uom': ld['uom'].id,
            'price_unit': ld['price'],
            'date_planned': D(ld.get('days', 10)),
        }))
    po = env['purchase.order'].with_context(**PO_ctx).create({
        'partner_id': vendor.id,
        'purchase_request_id': pr.id if pr else False,
        'origin': pr.name if pr else '',
        'order_line': order_lines,
        'vendor_quote_count': vendor_quote_count,
        'has_quote_evidence': has_evidence,
        'bypass_quote_requirement': bypass,
        'bypass_reason': bypass_reason,
        'notes': f'PO cho {pr.name if pr else ""} — {pr.purpose[:60] if pr else ""}',
    })
    if confirm:
        po.with_context(**PO_ctx).button_confirm()
    if ceo_approved:
        po.write({
            'ceo_approved': True,
            'ceo_approved_by': user_bgd.id,
            'ceo_approved_date': fields.Datetime.now(),
        })
    return po

# PO-1: từ PR-7, Cá Hồi + Tôm Biển, NCC Nông Sản, ~107M → cần BGĐ
po1 = make_po(
    pr=pr7, vendor=ncc_nl1,
    vendor_quote_count=3, has_evidence=True,
    lines_data=[
        {'ref': 'NL-CA-HOI',  'name': 'Cá Hồi Phi Lê (Đông Lạnh)', 'qty': 150, 'uom': kg,  'price': 475_000, 'days': 7},
        {'ref': 'NL-TOM-BIEN','name': 'Tôm Biển Khô',               'qty': 80,  'uom': kg,  'price': 510_000, 'days': 7},
        {'ref': 'NL-HAI-SAN', 'name': 'Hải Sản Hỗn Hợp (Đông Lạnh)','qty': 60, 'uom': kg,  'price': 182_000, 'days': 7},
    ],
    ceo_approved=False,   # cần BGĐ nhưng chưa duyệt
)
print(f"  ✓ PO {po1.name} | PR-7 | Cá Hồi + Tôm | {po1.amount_total:,.0f} VND | Cần BGĐ: {'✓' if po1.requires_ceo_approval else '—'}")

# PO-2: từ PR-8, Sâm + Hương liệu, NCC Nông Sản, ~71M → BGĐ đã duyệt
po2 = make_po(
    pr=pr8, vendor=ncc_nl1,
    vendor_quote_count=3, has_evidence=True,
    lines_data=[
        {'ref': 'NL-SAM-HQ', 'name': 'Sâm Hàn Quốc Khô',        'qty': 30, 'uom': kg, 'price': 1_780_000, 'days': 20},
        {'ref': 'PL-HL-DAU', 'name': 'Hương Liệu Tự Nhiên Dâu',  'qty': 20, 'uom': kg, 'price': 840_000,   'days': 20},
        {'ref': 'PL-MAU-DO', 'name': 'Màu Thực Phẩm Đỏ Tự Nhiên','qty': 10, 'uom': kg, 'price': 1_190_000, 'days': 20},
    ],
    ceo_approved=True,   # BGĐ đã duyệt
)
print(f"  ✓ PO {po2.name} | PR-8 | Sâm + Hương Liệu | {po2.amount_total:,.0f} VND | BGĐ đã duyệt ✓")

# PO-3: mua phụ liệu từ HĐ dài hạn, bypass 3-quote, NCC Hóa Chất, ~15M
po3 = make_po(
    pr=pr2, vendor=ncc_pl,
    vendor_quote_count=1, has_evidence=True,
    bypass=True, bypass_reason='Hợp đồng dài hạn HĐ-PL-2026-01, giá cố định 12 tháng',
    lines_data=[
        {'ref': 'PL-DUONG-TRANG','name': 'Đường Kính Trắng', 'qty': 2000, 'uom': kg, 'price': 21_500, 'days': 14},
        {'ref': 'PL-MUOI',       'name': 'Muối Tinh Chế',     'qty': 500,  'uom': kg, 'price': 8_200,  'days': 14},
        {'ref': 'PL-DAU-HD',     'name': 'Dầu Hướng Dương',   'qty': 300,  'uom': kg, 'price': 27_500, 'days': 14},
        {'ref': 'PL-BOT-NGOT',   'name': 'Bột Ngọt (Mono)',   'qty': 100,  'uom': kg, 'price': 41_000, 'days': 14},
    ],
    ceo_approved=False,
)
print(f"  ✓ PO {po3.name} | PR-2 | Phụ Liệu HĐ dài hạn | {po3.amount_total:,.0f} VND | Bypass ✓")

# PO-4: VPP standalone (operation), ~3.5M, đã xác nhận và nhận hàng xong
po4 = make_po(
    pr=pr3, vendor=ncc_nl1,
    vendor_quote_count=3, has_evidence=True,
    lines_data=[
        {'ref': 'VPP-GANG-TAY',   'name': 'Găng Tay Nitrile (hộp 100 cái)', 'qty': 20, 'uom': hop,  'price': 92_000, 'days': 5},
        {'ref': 'VPP-KHAU-TRANG', 'name': 'Khẩu Trang Y Tế (hộp 50 cái)',   'qty': 15, 'uom': hop,  'price': 43_000, 'days': 5},
        {'ref': 'VPP-MUC-ZEBRA',  'name': 'Mực In Nhãn Máy Zebra',           'qty': 2,  'uom': cai,  'price': 840_000,'days': 5},
    ],
    ceo_approved=False,
)
print(f"  ✓ PO {po4.name} | PR-3 | VPP & BHLD | {po4.amount_total:,.0f} VND")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 4. PHIẾU NHẬP KHO (Stock Picking — Receipt)
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Xử lý phiếu nhập kho (QA Gate)...")

def get_receipt(po):
    """Lấy phiếu nhập kho (WH/IN) từ PO."""
    return env['stock.picking'].search([
        ('purchase_id', '=', po.id),
        ('picking_type_code', '=', 'incoming'),
        ('state', 'not in', ('done', 'cancel')),
    ], limit=1)

def assign_lots_and_qty(picking, lot_prefix=None):
    """Gán số lô và số lượng nhận cho tất cả move trong phiếu."""
    for move in picking.move_ids:
        qty = move.product_uom_qty
        if move.product_id.tracking in ('lot', 'serial'):
            lot_name = f"LOT-{move.product_id.default_code or 'XX'}-{today.strftime('%Y%m')}"
            lot = env['stock.lot'].search([
                ('name', '=', lot_name),
                ('product_id', '=', move.product_id.id),
            ], limit=1)
            if not lot:
                lot = env['stock.lot'].create({
                    'name': lot_name,
                    'product_id': move.product_id.id,
                    'company_id': company.id,
                })
            if move.move_line_ids:
                move.move_line_ids.write({'lot_id': lot.id, 'quantity': qty})
            else:
                env['stock.move.line'].create({
                    'move_id': move.id,
                    'picking_id': picking.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'quantity': qty,
                    'lot_id': lot.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                })
        else:
            move.quantity = qty

# Phiếu nhập kho PO-3 (phụ liệu) → validate QA Pass → done
picking3 = get_receipt(po3)
if picking3:
    assign_lots_and_qty(picking3)
    picking3.write({
        'nfc_qa_required': True,
        'nfc_qa_passed': True,
        'nfc_qa_note': 'Đã kiểm tra mẫu đại diện. Đường: độ ẩm <0.1%, màu trắng. Muối: đúng chuẩn NaCl >99%. Dầu: cảm quan OK. QA PASS.',
        'nfc_qa_done_by': user_qa.id,
        'nfc_qa_date': fields.Datetime.now(),
    })
    try:
        picking3.with_context(skip_backorder=True).button_validate()
        print(f"  ✓ Nhập kho {picking3.name} → Done | PO-3 Phụ Liệu | QA Pass ✓")
    except Exception as e:
        print(f"  ~ Nhập kho {picking3.name}: {e}")
else:
    print("  ⚠ Không tìm thấy phiếu nhập cho PO-3")

# Phiếu nhập kho PO-4 (VPP) → validate nhanh không cần QA
picking4 = get_receipt(po4)
if picking4:
    assign_lots_and_qty(picking4)
    picking4.write({
        'nfc_qa_required': False,
        'nfc_qa_note': 'VPP không cần QA kiểm định',
    })
    try:
        picking4.with_context(skip_backorder=True).button_validate()
        print(f"  ✓ Nhập kho {picking4.name} → Done | PO-4 VPP | Không cần QA")
    except Exception as e:
        print(f"  ~ Nhập kho {picking4.name}: {e}")
else:
    print("  ⚠ Không tìm thấy phiếu nhập cho PO-4")

# Phiếu nhập kho PO-1 (Cá Hồi + Tôm) → đang chờ QA, chưa validate
picking1 = get_receipt(po1)
if picking1:
    for move in picking1.move_ids:
        move.quantity = move.product_uom_qty
    picking1.write({
        'nfc_qa_required': True,
        'nfc_qa_passed': False,
        'nfc_qa_note': 'Hàng về ngày hôm nay, chờ QA lấy mẫu kiểm định vi sinh và cảm quan.',
    })
    print(f"  ✓ Phiếu {picking1.name} | PO-1 Cá Hồi+Tôm | Đang chờ QA kiểm định ⏳")
else:
    print("  ⚠ Không tìm thấy phiếu nhập cho PO-1")

# Phiếu nhập kho PO-2 (Sâm + Hương Liệu) → sắp về
picking2 = get_receipt(po2)
if picking2:
    picking2.write({
        'nfc_qa_required': True,
        'nfc_qa_passed': False,
    })
    print(f"  ✓ Phiếu {picking2.name} | PO-2 Sâm+Hương Liệu | Chờ nhận hàng ⏳")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 5. HÓA ĐƠN NHẬP (Vendor Bills)
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Tạo hóa đơn nhập (Vendor Bills)...")

def make_vendor_bill(po, invoice_date=None, state='draft'):
    """Tạo hóa đơn nhà cung cấp từ PO."""
    try:
        bill = po.action_create_invoice()
        # action_create_invoice có thể trả về action dict, tìm bill trực tiếp
        bill_rec = env['account.move'].search([
            ('purchase_id', '=', po.id),
            ('move_type', '=', 'in_invoice'),
        ], limit=1)
        if bill_rec:
            if invoice_date:
                bill_rec.invoice_date = invoice_date
            if state == 'posted':
                bill_rec.action_post()
            return bill_rec
    except Exception as e:
        print(f"    ⚠ Lỗi tạo bill: {e}")
    return None

# Bill từ PO-3 (phụ liệu đã nhận xong) — đã đăng, chờ thanh toán
bill3 = make_vendor_bill(po3, invoice_date=today - timedelta(days=2), state='posted')
if bill3:
    print(f"  ✓ Bill {bill3.name} | PO-3 Phụ Liệu | {bill3.amount_total:,.0f} VND | Đã Đăng → Chờ Thanh Toán")

# Bill từ PO-4 (VPP đã nhận) — bản nháp
bill4 = make_vendor_bill(po4, invoice_date=today - timedelta(days=1), state='draft')
if bill4:
    print(f"  ✓ Bill {bill4.name} | PO-4 VPP | {bill4.amount_total:,.0f} VND | Bản Nháp")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 6. GẮN NCC VÀO SẢN PHẨM (vendor pricelist)
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Cấu hình giá NCC cho sản phẩm...")

vendor_product_map = [
    # (NCC, [(product_ref, min_qty, price, delay), ...])
    (ncc_nl1, [
        ('NL-DAU-TAY',  100, 83_000,     7),
        ('NL-ATISO-DO',  20, 415_000,   14),
        ('NL-SAM-HQ',    10, 1_780_000, 30),
        ('NL-LONG-NHAN', 50, 275_000,   10),
        ('NL-NAM-TUYET', 20, 640_000,   14),
        ('NL-CA-HOI',    50, 475_000,    5),
        ('NL-TOM-BIEN',  30, 510_000,    7),
        ('NL-HAI-SAN',   30, 182_000,    5),
    ]),
    (ncc_nl2, [
        ('NL-DAU-TAY',  100, 85_000,     7),
        ('NL-DAO-TUOI',  50, 63_000,     5),
        ('NL-GA-LOC',   100, 93_000,     3),
        ('NL-SUA-CHUA',  50, 37_000,     3),
        ('NL-KHOAI-MO',  50, 73_000,     7),
    ]),
    (ncc_pl, [
        ('PL-DUONG-TRANG', 500, 21_500, 7),
        ('PL-MUOI',        200, 8_200,  5),
        ('PL-DAU-HD',      100, 27_500, 7),
        ('PL-BOT-NGOT',     50, 41_000, 7),
        ('PL-E551',         10, 175_000,14),
        ('PL-HL-DAU',       10, 840_000,21),
        ('PL-MAU-DO',       10, 1_190_000,21),
        ('PL-BO-DONG-VAT',  50, 142_000,  7),
    ]),
    (ncc_bb1, [
        ('BB-HOP-ISOUP-30G',  5000, 2_750, 10),
        ('BB-LY-HUUPS-14G',   5000, 1_480, 10),
        ('BB-LY-ICHILL-29G',  5000, 1_760, 10),
        ('BB-TUI-ZIP-78G',    5000, 1_180, 10),
        ('BB-GOI-DEMI-23G',  10000,   630, 10),
        ('BB-THUNG-CARTON',    500, 11_500,  7),
        ('BB-HOP-IKIRO-27G',  5000, 2_450, 10),
        ('BB-TUI-IYAUA-50G',  5000,   960, 10),
    ]),
    (ncc_bb2, [
        ('BB-NHAN-ISOUP',  5, 440_000, 14),
        ('BB-GOI-DUONG-3G', 10000, 175, 14),
        ('BB-NAP-NHOM-ICHILL', 10000, 370, 14),
    ]),
]

count = 0
for vendor, products in vendor_product_map:
    if not vendor:
        continue
    for ref, min_qty, price, delay in products:
        prod_tmpl = pt(ref)
        if not prod_tmpl:
            continue
        existing = env['product.supplierinfo'].search([
            ('partner_id', '=', vendor.id),
            ('product_tmpl_id', '=', prod_tmpl.id),
        ], limit=1)
        if not existing:
            env['product.supplierinfo'].create({
                'partner_id': vendor.id,
                'product_tmpl_id': prod_tmpl.id,
                'min_qty': min_qty,
                'price': price,
                'delay': delay,
            })
            count += 1

env.cr.commit()
print(f"  ✓ Đã cấu hình {count} bảng giá NCC")

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

all_pr  = env['purchase.request'].search_count([('company_id','=',company.id)])
all_po  = env['purchase.order'].search_count([('company_id','=',company.id)])
all_rfq = env['purchase.order'].search_count([('company_id','=',company.id), ('state','=','draft')])
all_pick= env['stock.picking'].search_count([('company_id','=',company.id)])
all_bill= env['account.move'].search_count([('company_id','=',company.id),('move_type','=','in_invoice')])

print(f"""
{'='*65}
✅  NFC TRANSACTION DATA — HOÀN TẤT
{'='*65}

📋 Purchase Requests : {all_pr} PR
   • Draft           : 1  (PR-1 — chưa nộp)
   • Chờ Duyệt       : 2  (PR-2 phụ liệu, PR-3 VPP)
   • Đã Duyệt        : 2  (PR-4 NL premium, PR-5 máy móc)
   • MH Xác Nhận     : 3  (PR-6 bao bì, PR-7 cá hồi, PR-8 sâm)
   • Bị Từ Chối      : 1  (PR-9)
   • Đã Hủy          : 1  (PR-10)

📄 RFQ (Báo giá)     : {all_rfq} RFQ
   • PR-6 Bao Bì: 3 RFQ từ 3 vendor khác nhau (gate đủ điều kiện)
   • PR-4 NL Premium: 1 RFQ bypass (vendor độc quyền)

🛒 Purchase Orders   : {all_po} PO (tổng kể cả RFQ)
   • PO-1 Cá Hồi+Tôm  : {po1.amount_total:>14,.0f} VND  | Cần BGĐ duyệt ⏳
   • PO-2 Sâm+Hương Liệu: {po2.amount_total:>12,.0f} VND | BGĐ đã duyệt ✓
   • PO-3 Phụ Liệu    : {po3.amount_total:>14,.0f} VND  | Đã nhập kho ✓
   • PO-4 VPP         : {po4.amount_total:>14,.0f} VND  | Đã nhập kho ✓

📦 Phiếu Nhập Kho    : {all_pick} phiếu
   • Done (QA Pass)   : 2  (PO-3 phụ liệu, PO-4 VPP)
   • Chờ QA           : 1  (PO-1 Cá Hồi+Tôm)
   • Chờ nhận hàng    : 1  (PO-2 Sâm)

💳 Hóa Đơn Nhập      : {all_bill} bill
   • Đã đăng (chờ TT) : 1  (PO-3 — {f"{bill3.amount_total:,.0f} VND" if bill3 else "—"})
   • Bản nháp         : 1  (PO-4)

🌐 Truy cập: http://localhost:8070
""")

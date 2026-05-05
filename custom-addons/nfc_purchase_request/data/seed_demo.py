#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFC Demo Data Seed Script
Chạy bằng: odoo-bin shell -c odoo.conf --no-http < seed_demo.py
Hoặc: exec(open('...path.../seed_demo.py').read())
"""
import logging
_log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 1. CÔNG TY & CẤU HÌNH CƠ BẢN
# ══════════════════════════════════════════════════════════════════════════════

print("▶ Cập nhật thông tin Công ty NFC...")
company = env['res.company'].browse(1)
company.write({
    'name': 'NATURE FOODS CO., LTD',
    'street': 'Số 16 Trương Định, Phường Xuân Hòa',
    'city': 'TP. Hồ Chí Minh',
    'phone': '02513560107',
    'mobile': '0908480023',
    'email': 'mail.info@naturefoods.com.vn',
    'website': 'https://naturefoods.com.vn',
    'vat': '3600610154',
})

# Đơn tiền VND — chỉ đổi nếu chưa có journal entries
vnd = env['res.currency'].with_context(active_test=False).search([('name', '=', 'VND')], limit=1)
if vnd:
    vnd.write({'active': True})
    has_entries = env['account.move.line'].search_count([('company_id', '=', company.id)]) > 0
    if not has_entries:
        company.write({'currency_id': vnd.id})
        print(f"  ✓ Đơn tiền: VND")
    else:
        print(f"  ~ Đơn tiền: giữ nguyên {company.currency_id.name} (đã có journal entries)")
        print(f"    → Đổi VND thủ công: Settings > Accounting > Currencies > Kích hoạt VND")
else:
    print("  ⚠ Không tìm thấy VND")

env.cr.commit()
print("  ✓ Công ty đã cập nhật\n")

# ══════════════════════════════════════════════════════════════════════════════
# 2. KHO HÀNG
# ══════════════════════════════════════════════════════════════════════════════

print("▶ Cấu hình Kho hàng...")
warehouse = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
if warehouse:
    warehouse.write({
        'name': 'Kho NFC - Đồng Nai',
        'code': 'NFC',
    })
    print(f"  ✓ Kho: {warehouse.name}")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 3. ĐƠN VỊ TÍNH (UoM)
# ══════════════════════════════════════════════════════════════════════════════

print("▶ Kiểm tra đơn vị tính...")
uom_data = {}

def find_or_create_uom(search_names, create_name, category_keyword, uom_type='bigger'):
    """Tìm UoM theo nhiều tên, tạo mới nếu không có (không phải reference unit)."""
    for sname in search_names:
        uom = env['uom.uom'].search([('name', 'ilike', sname)], limit=1)
        if uom:
            return uom
    # Tạo mới (không phải reference)
    cat = env['uom.category'].search([('name', 'ilike', category_keyword)], limit=1)
    if not cat:
        return None
    # Kiểm tra có reference chưa — nếu chưa có thì tạo reference, ngược lại tạo bigger
    ref_exists = env['uom.uom'].search([('category_id', '=', cat.id), ('uom_type', '=', 'reference')], limit=1)
    uom_type_val = 'bigger' if ref_exists else 'reference'
    try:
        return env['uom.uom'].create({
            'name': create_name,
            'category_id': cat.id,
            'uom_type': uom_type_val,
            'factor': 1.0,
        })
    except Exception as e:
        print(f"    ⚠ Không tạo được UoM {create_name}: {e}")
        return None

# Weight
uom_data['kg']    = find_or_create_uom(['kg', 'Kilogram', 'Kilo'], 'kg', 'Weight')
uom_data['g']     = find_or_create_uom(['g', 'Gram'], 'g', 'Weight')

# Unit (cái, hộp, gói, cuộn...)
cat_unit = env['uom.category'].search([('name', 'ilike', 'Unit')], limit=1)

def find_or_create_unit(names, create_name):
    for n in names:
        u = env['uom.uom'].search([('name', 'ilike', n)], limit=1)
        if u:
            return u
    if cat_unit:
        try:
            return env['uom.uom'].create({
                'name': create_name,
                'category_id': cat_unit.id,
                'uom_type': 'bigger',
                'factor': 1.0,
            })
        except Exception:
            pass
    return None

uom_data['thùng'] = find_or_create_unit(['Thùng', 'thùng'], 'Thùng')
uom_data['hộp']   = find_or_create_unit(['Hộp', 'hộp', 'Box'], 'Hộp')
uom_data['gói']   = find_or_create_unit(['Gói', 'gói', 'Pack'], 'Gói')
uom_data['cái']   = find_or_create_unit(['Cái', 'cái', 'Units', 'Unit', 'Chiếc'], 'Cái')
uom_data['cuộn']  = find_or_create_unit(['Cuộn', 'cuộn', 'Roll'], 'Cuộn')
uom_data['bộ']    = find_or_create_unit(['Bộ', 'Set', 'set'], 'Bộ')

# Volume
uom_data['lít']   = find_or_create_uom(['Lít', 'lít', 'Liter', 'litre', 'l'], 'Lít', 'Volume')

for key, u in uom_data.items():
    if u:
        print(f"  ✓ UoM [{key}]: {u.name}")
    else:
        print(f"  ⚠ UoM [{key}]: không tìm thấy")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 4. DANH MỤC SẢN PHẨM
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Tạo danh mục sản phẩm...")
categ_data = {}
categories = [
    ('NL Thực Phẩm', 'Nguyên liệu thực phẩm (hoa quả, rau củ, thịt, hải sản)'),
    ('Phụ Liệu', 'Phụ liệu sản xuất (đường, muối, gia vị, phụ gia thực phẩm)'),
    ('Bao Bì', 'Bao bì đóng gói (hộp, túi, ly, gói, nhãn)'),
    ('Máy Móc & Thiết Bị', 'Máy móc sản xuất, thiết bị nhà máy'),
    ('VPP & Dụng Cụ', 'Văn phòng phẩm, dụng cụ văn phòng'),
    ('Dịch Vụ', 'Dịch vụ thuê ngoài, bảo trì, vận chuyển'),
]

parent_categ = env['product.category'].search([('name', '=', 'All')], limit=1)
for name, desc in categories:
    categ = env['product.category'].search([('name', '=', name)], limit=1)
    if not categ:
        categ = env['product.category'].create({
            'name': name,
            'parent_id': parent_categ.id if parent_categ else False,
        })
    categ_data[name] = categ
    print(f"  ✓ Danh mục: {name}")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 5. SẢN PHẨM (SKU — Nguyên liệu / Phụ liệu / Bao bì)
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Tạo sản phẩm SKU (nguyên liệu, phụ liệu, bao bì)...")

kg  = uom_data.get('kg') or env['uom.uom'].search([('name', '=', 'kg')], limit=1)
g   = uom_data.get('g')  or env['uom.uom'].search([('name', '=', 'g')], limit=1)
thung = uom_data.get('thùng') or env['uom.uom'].search([('name', 'ilike', 'thùng')], limit=1)
hop   = uom_data.get('hộp')   or env['uom.uom'].search([('name', 'ilike', 'hộp')], limit=1)
goi   = uom_data.get('gói')   or env['uom.uom'].search([('name', 'ilike', 'gói')], limit=1)
cai   = uom_data.get('cái')   or env['uom.uom'].search([('name', 'ilike', 'cái')], limit=1)
cuon  = uom_data.get('cuộn')  or env['uom.uom'].search([('name', 'ilike', 'cuộn')], limit=1)

def uom_or_kg(u): return u if u else kg

nl_categ  = categ_data.get('NL Thực Phẩm')
pl_categ  = categ_data.get('Phụ Liệu')
bb_categ  = categ_data.get('Bao Bì')
may_categ = categ_data.get('Máy Móc & Thiết Bị')
vpp_categ = categ_data.get('VPP & Dụng Cụ')
dv_categ  = categ_data.get('Dịch Vụ')

# UoM helpers — uom_po phải cùng category với uom
_kg   = uom_data.get('kg')
_g    = uom_data.get('g')
_cai  = uom_data.get('cái')
_hop  = uom_data.get('hộp')  or _cai
_goi  = uom_data.get('gói')  or _cai
_thung= uom_data.get('thùng')or _cai
_cuon = uom_data.get('cuộn') or _cai
_bo   = uom_data.get('bộ')   or _cai

products_to_create = [
    # ── Nguyên liệu thực phẩm (NL) — mua/bán theo kg ────────────────────
    dict(name='Dâu Tây Tươi (Strawberry)', categ=nl_categ, uom=_kg, uom_po=_kg, price=85_000,    ref='NL-DAU-TAY'),
    dict(name='Atiso Đỏ Sấy',              categ=nl_categ, uom=_kg, uom_po=_kg, price=420_000,   ref='NL-ATISO-DO'),
    dict(name='Trà Đào (Đào Tươi)',        categ=nl_categ, uom=_kg, uom_po=_kg, price=65_000,    ref='NL-DAO-TUOI'),
    dict(name='Cam Sả (Vỏ Cam Khô)',       categ=nl_categ, uom=_kg, uom_po=_kg, price=120_000,   ref='NL-CAM-SA'),
    dict(name='Sâm Hàn Quốc Khô',         categ=nl_categ, uom=_kg, uom_po=_kg, price=1_800_000, ref='NL-SAM-HQ'),
    dict(name='Long Nhãn Sấy',             categ=nl_categ, uom=_kg, uom_po=_kg, price=280_000,   ref='NL-LONG-NHAN'),
    dict(name='Nấm Tuyết Khô',             categ=nl_categ, uom=_kg, uom_po=_kg, price=650_000,   ref='NL-NAM-TUYET'),
    dict(name='Hạt Chia',                  categ=nl_categ, uom=_kg, uom_po=_kg, price=180_000,   ref='NL-HAT-CHIA'),
    dict(name='Yến Mạch Rolled Oat',       categ=nl_categ, uom=_kg, uom_po=_kg, price=45_000,    ref='NL-YEN-MACH'),
    dict(name='Thịt Gà Lọc (Đông Lạnh)',  categ=nl_categ, uom=_kg, uom_po=_kg, price=95_000,    ref='NL-GA-LOC'),
    dict(name='Hải Sản Hỗn Hợp (Đông Lạnh)', categ=nl_categ, uom=_kg, uom_po=_kg, price=185_000, ref='NL-HAI-SAN'),
    dict(name='Nấm Hương Khô',             categ=nl_categ, uom=_kg, uom_po=_kg, price=380_000,   ref='NL-NAM-HUONG'),
    dict(name='Rong Biển Khô',             categ=nl_categ, uom=_kg, uom_po=_kg, price=290_000,   ref='NL-RONG-BIEN'),
    dict(name='Cải Chua Sấy Khô',          categ=nl_categ, uom=_kg, uom_po=_kg, price=95_000,    ref='NL-CAI-CHUA'),
    dict(name='Rau Ngót Sấy Khô',          categ=nl_categ, uom=_kg, uom_po=_kg, price=110_000,   ref='NL-RAU-NGOT'),
    dict(name='Khoai Mỡ Sấy',             categ=nl_categ, uom=_kg, uom_po=_kg, price=75_000,    ref='NL-KHOAI-MO'),
    dict(name='Táo Đỏ (Táo Tàu) Khô',     categ=nl_categ, uom=_kg, uom_po=_kg, price=220_000,   ref='NL-TAO-DO'),
    dict(name='Tôm Biển Khô',              categ=nl_categ, uom=_kg, uom_po=_kg, price=520_000,   ref='NL-TOM-BIEN'),
    dict(name='Cá Hồi Phi Lê (Đông Lạnh)',categ=nl_categ, uom=_kg, uom_po=_kg, price=480_000,   ref='NL-CA-HOI'),
    dict(name='Sữa Chua Nguyên Kem',       categ=nl_categ, uom=_kg, uom_po=_kg, price=38_000,    ref='NL-SUA-CHUA'),
    dict(name='Hành Lá Sấy Khô',           categ=nl_categ, uom=_kg, uom_po=_kg, price=145_000,   ref='NL-HANH-LA'),

    # ── Phụ liệu (PL) — mua theo kg ──────────────────────────────────────
    dict(name='Đường Kính Trắng',             categ=pl_categ, uom=_kg, uom_po=_kg, price=22_000,    ref='PL-DUONG-TRANG'),
    dict(name='Muối Tinh Chế',                categ=pl_categ, uom=_kg, uom_po=_kg, price=8_500,     ref='PL-MUOI'),
    dict(name='Bột Ngọt (Mono)',              categ=pl_categ, uom=_kg, uom_po=_kg, price=42_000,    ref='PL-BOT-NGOT'),
    dict(name='Tinh Bột Khoai Tây',           categ=pl_categ, uom=_kg, uom_po=_kg, price=35_000,    ref='PL-TINH-BOT'),
    dict(name='Dầu Hướng Dương',              categ=pl_categ, uom=_kg, uom_po=_kg, price=28_000,    ref='PL-DAU-HD'),
    dict(name='Phụ Gia Chống Vón Cục (E551)', categ=pl_categ, uom=_kg, uom_po=_kg, price=180_000,   ref='PL-E551'),
    dict(name='Hương Liệu Tự Nhiên Dâu',      categ=pl_categ, uom=_kg, uom_po=_kg, price=850_000,   ref='PL-HL-DAU'),
    dict(name='Màu Thực Phẩm Đỏ Tự Nhiên',   categ=pl_categ, uom=_kg, uom_po=_kg, price=1_200_000, ref='PL-MAU-DO'),
    dict(name='Bơ Động Vật Lạt',              categ=pl_categ, uom=_kg, uom_po=_kg, price=145_000,   ref='PL-BO-DONG-VAT'),
    dict(name='Tỏi Sấy Khô Vụn',             categ=pl_categ, uom=_kg, uom_po=_kg, price=195_000,   ref='PL-TOI-SAY'),

    # ── Bao bì (BB) — mua theo cái / cuộn (cùng category Unit) ──────────
    dict(name='Hộp Giấy iSOUP 30g',          categ=bb_categ, uom=_cai, uom_po=_cai, price=2_800,   ref='BB-HOP-ISOUP-30G'),
    dict(name='Ly Nhựa HUUPS 14g',           categ=bb_categ, uom=_cai, uom_po=_cai, price=1_500,   ref='BB-LY-HUUPS-14G'),
    dict(name='Ly Nhựa iCHILL 29g',          categ=bb_categ, uom=_cai, uom_po=_cai, price=1_800,   ref='BB-LY-ICHILL-29G'),
    dict(name='Túi Zip Stand-Up 78g',         categ=bb_categ, uom=_cai, uom_po=_cai, price=1_200,   ref='BB-TUI-ZIP-78G'),
    dict(name='Gói Demi 23g (Màng PA/PE)',    categ=bb_categ, uom=_cai, uom_po=_cai, price=650,     ref='BB-GOI-DEMI-23G'),
    dict(name='Nắp Nhôm Seal iCHILL',        categ=bb_categ, uom=_cai, uom_po=_cai, price=380,     ref='BB-NAP-NHOM-ICHILL'),
    dict(name='Nhãn In Decal iSOUP (cuộn)',   categ=bb_categ, uom=_cuon, uom_po=_cuon, price=450_000, ref='BB-NHAN-ISOUP'),
    dict(name='Thùng Carton 5 lớp',          categ=bb_categ, uom=_cai, uom_po=_cai, price=12_000,  ref='BB-THUNG-CARTON'),
    dict(name='Hộp Giấy iKIRO 27g',          categ=bb_categ, uom=_cai, uom_po=_cai, price=2_500,   ref='BB-HOP-IKIRO-27G'),
    dict(name='Túi Đứng iYAUA 50g',          categ=bb_categ, uom=_cai, uom_po=_cai, price=980,     ref='BB-TUI-IYAUA-50G'),
    dict(name='Gói Đường Riêng (3g)',         categ=bb_categ, uom=_cai, uom_po=_cai, price=180,     ref='BB-GOI-DUONG-3G'),

    # ── VPP & Dụng cụ ─────────────────────────────────────────────────────
    dict(name='Găng Tay Nitrile (hộp 100 cái)', categ=vpp_categ, uom=_hop, uom_po=_hop, price=95_000,  ref='VPP-GANG-TAY'),
    dict(name='Khẩu Trang Y Tế (hộp 50 cái)',   categ=vpp_categ, uom=_hop, uom_po=_hop, price=45_000,  ref='VPP-KHAU-TRANG'),
    dict(name='Mực In Nhãn Máy Zebra',           categ=vpp_categ, uom=_cai, uom_po=_cai, price=850_000, ref='VPP-MUC-ZEBRA'),
    dict(name='Giấy In Nhãn Cuộn 4x6',          categ=vpp_categ, uom=_cuon, uom_po=_cuon, price=220_000, ref='VPP-GIAY-NHAN'),
]

created_products = []
for p in products_to_create:
    existing = env['product.template'].search([('default_code', '=', p['ref'])], limit=1)
    if existing:
        created_products.append(existing)
        continue
    vals = {
        'name': p['name'],
        'default_code': p['ref'],
        'categ_id': p['categ'].id if p['categ'] else False,
        'uom_id': p['uom'].id if p['uom'] else kg.id,
        'uom_po_id': p['uom_po'].id if p['uom_po'] else kg.id,
        'standard_price': p['price'],
        'purchase_ok': True,
        'sale_ok': False,
        'type': 'consu',
        'tracking': 'lot' if p['categ'] in (nl_categ, pl_categ, bb_categ) else 'none',
    }
    prod = env['product.template'].create(vals)
    created_products.append(prod)
    print(f"  ✓ [{p['ref']}] {p['name']}")

env.cr.commit()
print(f"  → Tổng: {len(created_products)} sản phẩm\n")

# ══════════════════════════════════════════════════════════════════════════════
# 6. NHÀ CUNG CẤP (VENDORS)
# ══════════════════════════════════════════════════════════════════════════════

print("▶ Tạo nhà cung cấp...")
vendors_data = [
    dict(name='CTY TNHH NGUYÊN LIỆU NÔNG SẢN SÀI GÒN',
         vat='0312345678', phone='0283 888 1234', email='purchase@nongsansaigon.vn',
         street='12 Nguyễn Thị Minh Khai, Q1', city='TP. Hồ Chí Minh',
         tags=['NCC Nguyên Liệu']),
    dict(name='CTY CP THỰC PHẨM ĐỒNG NAI XANH',
         vat='3600987654', phone='0251 3321 456', email='sales@dongnaixanh.vn',
         street='KCN Nhơn Trạch 2, Đồng Nai', city='Đồng Nai',
         tags=['NCC Nguyên Liệu']),
    dict(name='CTY TNHH BAO BÌ TIẾN PHÁT',
         vat='0312111222', phone='0283 999 5678', email='order@baobitienphát.vn',
         street='45 Đường số 3, KCN Tân Bình', city='TP. Hồ Chí Minh',
         tags=['NCC Bao Bì']),
    dict(name='CTY CP IN ẤN BÌNH DƯƠNG PRINT',
         vat='3700444555', phone='0274 3812 789', email='quotation@bdprint.vn',
         street='78 Mỹ Phước – Tân Vạn, Bình Dương', city='Bình Dương',
         tags=['NCC Bao Bì']),
    dict(name='CTY TNHH HÓA CHẤT PHỤ GIA VIỆT NAM',
         vat='0313222333', phone='0283 777 9012', email='sales@hcpgvietnam.vn',
         street='89 Bình Long, Bình Tân', city='TP. Hồ Chí Minh',
         tags=['NCC Phụ Liệu']),
    dict(name='CTY TNHH MÁY MÓC THIẾT BỊ THỰC PHẨM ANH KHOA',
         vat='0314333444', phone='0909 123 456', email='anhkhoa.equipment@gmail.com',
         street='156 Tân Kỳ Tân Quý, Bình Tân', city='TP. Hồ Chí Minh',
         tags=['NCC Máy Móc']),
    dict(name='CTY DỊCH VỤ VẬN TẢI LẠNH ĐÔNG NAM',
         vat='0315444555', phone='0908 654 321', email='booking@dongnam-cold.vn',
         street='23 Nguyễn Hữu Thọ, Q7', city='TP. Hồ Chí Minh',
         tags=['NCC Dịch Vụ']),
]

vendor_objs = {}
for v in vendors_data:
    partner = env['res.partner'].search([('name', '=', v['name'])], limit=1)
    if not partner:
        partner = env['res.partner'].create({
            'name': v['name'],
            'company_type': 'company',
            'supplier_rank': 1,
            'vat': v.get('vat'),
            'phone': v.get('phone'),
            'email': v.get('email'),
            'street': v.get('street'),
            'city': v.get('city'),
            'country_id': env.ref('base.vn').id,
        })
    vendor_objs[v['name']] = partner
    print(f"  ✓ NCC: {v['name']}")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 7. NHÂN VIÊN + CƠ CẤU QUẢN LÝ
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Tạo nhân viên và cơ cấu quản lý...")

def get_or_create_dept(name, parent=None):
    dept = env['hr.department'].search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if not dept:
        dept = env['hr.department'].create({
            'name': name,
            'company_id': company.id,
            'parent_id': parent.id if parent else False,
        })
    return dept

dept_mua_hang    = get_or_create_dept('Phòng Mua Hàng')
dept_san_xuat    = get_or_create_dept('Phòng Sản Xuất')
dept_kho         = get_or_create_dept('Phòng Kho')
dept_qa          = get_or_create_dept('Phòng QA')
dept_ke_toan     = get_or_create_dept('Phòng Kế Toán')
dept_ke_hoach    = get_or_create_dept('Phòng Kế Hoạch')
dept_rd          = get_or_create_dept('Phòng R&D')
dept_kinh_doanh  = get_or_create_dept('Phòng Kinh Doanh')

print("  ✓ Phòng ban đã tạo")
env.cr.commit()

# ── Demo Users (với login/password) ──────────────────────────────────────────
def get_or_create_user(login, name, email, groups_xml_ids=None):
    user = env['res.users'].search([('login', '=', login)], limit=1)
    if not user:
        user = env['res.users'].create({
            'name': name,
            'login': login,
            'email': email,
            'password': 'nfc2026',
            'company_id': company.id,
            'groups_id': [(6, 0, [
                env.ref(g).id for g in (groups_xml_ids or []) if env.ref(g, False)
            ])],
        })
        print(f"  ✓ User tạo mới: {login} (pwd: nfc2026)")
    else:
        print(f"  ~ User đã có: {login}")
    return user

# BGĐ / CEO
user_bgd = get_or_create_user(
    login='an.nguyen',
    name='Nguyễn Văn Ân (BGĐ)',
    email='an.nguyen@naturefoods.com.vn',
    groups_xml_ids=[
        'purchase.group_purchase_manager',
        'stock.group_stock_manager',
        'account.group_account_manager',
        'nfc_purchase_request.group_nfc_purchase_manager',
    ]
)

# Trưởng phòng Mua Hàng
user_tp_mh = get_or_create_user(
    login='huong.le',
    name='Lê Thị Hương (TP Mua Hàng)',
    email='huong.le@naturefoods.com.vn',
    groups_xml_ids=[
        'purchase.group_purchase_manager',
        'nfc_purchase_request.group_nfc_purchase_manager',
    ]
)

# Trưởng phòng SX / Kỹ thuật
user_tp_kk = get_or_create_user(
    login='kham.tran',
    name='Trần Văn Khâm (TP Kỹ Thuật)',
    email='kham.tran@naturefoods.com.vn',
    groups_xml_ids=[
        'purchase.group_purchase_user',
        'nfc_purchase_request.group_nfc_pr_manager',
    ]
)

# Nhân viên Mua Hàng
user_nv_mh = get_or_create_user(
    login='linh.pham',
    name='Phạm Thị Linh (NV Mua Hàng)',
    email='linh.pham@naturefoods.com.vn',
    groups_xml_ids=[
        'purchase.group_purchase_user',
        'nfc_purchase_request.group_nfc_purchase_manager',
    ]
)

# Nhân viên Kho
user_kho = get_or_create_user(
    login='minh.nguyen.kho',
    name='Nguyễn Văn Minh (Thủ Kho)',
    email='minh.nguyen@naturefoods.com.vn',
    groups_xml_ids=[
        'stock.group_stock_user',
        'nfc_purchase_request.group_nfc_pr_user',
    ]
)

# QA
user_qa = get_or_create_user(
    login='thu.tran.qa',
    name='Trần Thị Thu (QA)',
    email='thu.tran@naturefoods.com.vn',
    groups_xml_ids=[
        'stock.group_stock_user',
        'nfc_purchase_request.group_nfc_pr_user',
    ]
)

# Kế Toán
user_kt = get_or_create_user(
    login='nga.hoang.kt',
    name='Hoàng Thị Nga (Kế Toán)',
    email='nga.hoang@naturefoods.com.vn',
    groups_xml_ids=[
        'account.group_account_user',
        'nfc_purchase_request.group_nfc_pr_user',
    ]
)

# Nhân viên SX (người tạo PR thường xuyên)
user_sx = get_or_create_user(
    login='hung.vo.sx',
    name='Võ Văn Hùng (NV Sản Xuất)',
    email='hung.vo@naturefoods.com.vn',
    groups_xml_ids=[
        'nfc_purchase_request.group_nfc_pr_user',
    ]
)

env.cr.commit()

# ── Gắn nhân viên với phòng ban & manager ─────────────────────────────────

def get_or_create_employee(user, dept, job_title, manager_user=None):
    emp = env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
    vals = {
        'name': user.name,
        'user_id': user.id,
        'department_id': dept.id,
        'job_title': job_title,
        'work_email': user.email,
        'company_id': company.id,
    }
    if manager_user:
        mgr_emp = env['hr.employee'].search([('user_id', '=', manager_user.id)], limit=1)
        if mgr_emp:
            vals['parent_id'] = mgr_emp.id
    if not emp:
        emp = env['hr.employee'].create(vals)
        print(f"  ✓ Employee: {emp.name} — {dept.name}")
    else:
        emp.write(vals)
        print(f"  ~ Employee update: {emp.name}")
    return emp

emp_bgd   = get_or_create_employee(user_bgd,   dept_mua_hang,  'Giám Đốc Chuỗi Cung Ứng')
emp_tp_mh = get_or_create_employee(user_tp_mh, dept_mua_hang,  'Trưởng Phòng Mua Hàng',  manager_user=user_bgd)
emp_tp_kk = get_or_create_employee(user_tp_kk, dept_san_xuat,  'Trưởng Phòng Kỹ Thuật',   manager_user=user_bgd)
emp_nv_mh = get_or_create_employee(user_nv_mh, dept_mua_hang,  'Nhân Viên Mua Hàng',       manager_user=user_tp_mh)
emp_kho   = get_or_create_employee(user_kho,   dept_kho,       'Thủ Kho',                  manager_user=user_bgd)
emp_qa    = get_or_create_employee(user_qa,    dept_qa,        'Nhân Viên QA',             manager_user=user_bgd)
emp_kt    = get_or_create_employee(user_kt,    dept_ke_toan,   'Kế Toán Mua Hàng',         manager_user=user_bgd)
emp_sx    = get_or_create_employee(user_sx,    dept_san_xuat,  'Nhân Viên Sản Xuất',       manager_user=user_tp_kk)

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 8. CẤU HÌNH PURCHASE SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

print("\n▶ Cấu hình Purchase Settings...")
try:
    # Bật purchase order approval bằng ir.config_parameter
    env['ir.config_parameter'].sudo().set_param('purchase.use_po_lead', '0')
    # Group purchase approval
    grp = env.ref('purchase.group_purchase_order_approval', raise_if_not_found=False)
    if grp:
        grp.write({})  # ensure exists
        # Thêm vào base_user để active
        print("  ✓ Purchase group approval: OK")
    print("  ✓ Purchase Settings configured")
except Exception as e:
    print(f"  ~ Purchase Settings (bỏ qua, cài thủ công): {e}")

env.cr.commit()

# ══════════════════════════════════════════════════════════════════════════════
# 9. SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("✅ SEED DATA HOÀN TẤT — NATURE FOODS CO., LTD (NFC)")
print("="*60)
print(f"""
🏢 Công ty  : NATURE FOODS CO., LTD
💱 Tiền tệ  : VND
🏭 Kho      : Kho NFC - Đồng Nai
📦 Sản phẩm : {len(created_products)} SKU (NL / Phụ liệu / Bao bì / VPP)
🏪 NCC      : {len(vendor_objs)} nhà cung cấp
👥 Users    :
   admin       → admin/admin           (Odoo Admin)
   an.nguyen   → nfc2026               (BGĐ — duyệt PO > 50M)
   huong.le    → nfc2026               (TP Mua Hàng — duyệt NL)
   kham.tran   → nfc2026               (TP Kỹ Thuật — duyệt máy móc)
   linh.pham   → nfc2026               (NV Mua Hàng)
   minh.nguyen.kho → nfc2026           (Thủ Kho)
   thu.tran.qa → nfc2026               (QA)
   nga.hoang.kt → nfc2026              (Kế Toán)
   hung.vo.sx  → nfc2026               (NV SX — người tạo PR)

🌐 Truy cập : http://localhost:8070
""")

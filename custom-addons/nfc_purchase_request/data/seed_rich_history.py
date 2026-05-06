#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seed lịch sử mua hàng phong phú — 12 tháng × nhiều SP × 3-4 NCC
Phục vụ demo: Anomaly Detection, NCC Scoring, Price Analytics.

Idempotent: xóa PO cũ có origin RICH-HIST| rồi tạo lại.
Chạy: odoo-bin shell -c /opt/odoo18/nfc.conf --no-http < seed_rich_history.py
"""
import random
from datetime import date
from dateutil.relativedelta import relativedelta

ORIGIN_PREFIX = "RICH-HIST|"
random.seed(42)

print("=" * 65)
print("NFC — Seed lịch sử mua hàng phong phú (12 tháng)")
print("=" * 65)

company = env["res.company"].browse(1)
PO_ctx = {"mail_create_nosubscribe": True, "tracking_disable": True, "mail_notrack": True}

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_product(code):
    p = env["product.product"].search([("default_code", "=", code)], limit=1)
    return p if p else None

def get_uom(name_fragment):
    u = env["uom.uom"].search([("name", "ilike", name_fragment)], limit=1)
    return u

def get_partner(pid):
    return env["res.partner"].browse(pid)

def po_date(months_ago, day=15):
    d = date.today() - relativedelta(months=months_ago)
    return date(d.year, d.month, min(day, 28))

def vary(base, pct_range=0.08):
    """Biến động ±pct_range so với base."""
    factor = 1 + random.uniform(-pct_range, pct_range)
    return round(base * factor, 0)

def spike(base, direction=1, magnitude=0.35):
    """Tạo spike bất thường cho demo anomaly detection."""
    return round(base * (1 + direction * magnitude), 0)

# ── Cấu hình sản phẩm & NCC ───────────────────────────────────────────────────
# partner_id: 7=SaiGon, 8=DongNai, 9=TienPhat, 10=BinhDuong, 11=HoaChat

PRODUCTS = [
    # NL nhóm — NCC: SàiGòn(7) + ĐồngNai(8), đôi khi cả hai
    {
        "code": "NL-ATISO-DO",   "base_price": 420_000, "unit": "kg",
        "vendors": [
            {"pid": 7, "base": 420_000, "min_qty": 50},
            {"pid": 8, "base": 400_000, "min_qty": 100},
        ],
        "months": 12, "qty_range": (50, 200),
        "anomaly_month": 3, "anomaly_vendor": 7, "anomaly_dir": 1,  # spike tháng 3
    },
    {
        "code": "NL-SAM-HQ",     "base_price": 1_780_000, "unit": "kg",
        "vendors": [
            {"pid": 7, "base": 1_780_000, "min_qty": 5},
        ],
        "months": 12, "qty_range": (5, 30),
        "anomaly_month": 6, "anomaly_vendor": 7, "anomaly_dir": -1,  # drop bất thường
    },
    {
        "code": "NL-NAM-TUYET",   "base_price": 640_000, "unit": "kg",
        "vendors": [
            {"pid": 7, "base": 640_000, "min_qty": 20},
            {"pid": 8, "base": 620_000, "min_qty": 50},
        ],
        "months": 12, "qty_range": (20, 100),
        "anomaly_month": None,
    },
    {
        "code": "NL-TOM-BIEN",    "base_price": 510_000, "unit": "kg",
        "vendors": [
            {"pid": 7, "base": 510_000, "min_qty": 30},
            {"pid": 13, "base": 495_000, "min_qty": 100},
        ],
        "months": 12, "qty_range": (30, 150),
        "anomaly_month": 2, "anomaly_vendor": 7, "anomaly_dir": 1,
    },
    {
        "code": "NL-CA-HOI",      "base_price": 475_000, "unit": "kg",
        "vendors": [
            {"pid": 7, "base": 475_000, "min_qty": 20},
            {"pid": 13, "base": 460_000, "min_qty": 50},
        ],
        "months": 12, "qty_range": (20, 80),
        "anomaly_month": None,
    },
    {
        "code": "NL-HAI-SAN",     "base_price": 182_000, "unit": "kg",
        "vendors": [
            {"pid": 7, "base": 182_000, "min_qty": 50},
            {"pid": 8, "base": 175_000, "min_qty": 100},
            {"pid": 13, "base": 170_000, "min_qty": 200},
        ],
        "months": 10, "qty_range": (50, 300),
        "anomaly_month": 4, "anomaly_vendor": 8, "anomaly_dir": 1,
    },
    # PL nhóm — NCC: HoaChat(11) + SàiGòn(7)
    {
        "code": "PL-DAU-HD",      "base_price": 27_500, "unit": "kg",
        "vendors": [
            {"pid": 11, "base": 27_500, "min_qty": 100},
            {"pid": 7,  "base": 28_200, "min_qty": 50},
        ],
        "months": 12, "qty_range": (100, 500),
        "anomaly_month": 1, "anomaly_vendor": 11, "anomaly_dir": 1,
    },
    {
        "code": "PL-DUONG-TRANG", "base_price": 21_500, "unit": "kg",
        "vendors": [
            {"pid": 11, "base": 21_500, "min_qty": 200},
        ],
        "months": 12, "qty_range": (200, 1000),
        "anomaly_month": None,
    },
    {
        "code": "PL-BOT-NGOT",    "base_price": 41_000, "unit": "kg",
        "vendors": [
            {"pid": 11, "base": 41_000, "min_qty": 100},
            {"pid": 7,  "base": 43_000, "min_qty": 50},
        ],
        "months": 10, "qty_range": (100, 400),
        "anomaly_month": None,
    },
    {
        "code": "PL-HL-DAU",      "base_price": 840_000, "unit": "kg",
        "vendors": [
            {"pid": 11, "base": 840_000, "min_qty": 10},
            {"pid": 7,  "base": 855_000, "min_qty": 5},
        ],
        "months": 8, "qty_range": (10, 50),
        "anomaly_month": 3, "anomaly_vendor": 7, "anomaly_dir": 1,
    },
    # BB nhóm — NCC: TienPhat(9) + BinhDuong(10)
    {
        "code": "BB-HOP-ISOUP-30G","base_price": 2_800, "unit": "cái",
        "vendors": [
            {"pid": 9,  "base": 2_750, "min_qty": 5000},
            {"pid": 10, "base": 2_935, "min_qty": 1000},
            {"pid": 8,  "base": 2_880, "min_qty": 1000},
        ],
        "months": 12, "qty_range": (5000, 20000),
        "anomaly_month": 2, "anomaly_vendor": 10, "anomaly_dir": 1,
    },
    {
        "code": "BB-LY-ICHILL-29G","base_price": 1_760, "unit": "cái",
        "vendors": [
            {"pid": 9,  "base": 1_760, "min_qty": 5000},
            {"pid": 10, "base": 1_850, "min_qty": 2000},
        ],
        "months": 10, "qty_range": (5000, 15000),
        "anomaly_month": None,
    },
    {
        "code": "BB-THUNG-CARTON", "base_price": 11_500, "unit": "cái",
        "vendors": [
            {"pid": 9,  "base": 11_500, "min_qty": 500},
        ],
        "months": 12, "qty_range": (500, 2000),
        "anomaly_month": 5, "anomaly_vendor": 9, "anomaly_dir": 1,
    },
]

# ── Cleanup ───────────────────────────────────────────────────────────────────
print("\n▶ Xóa PO cũ (RICH-HIST|)...")
old = env["purchase.order"].search([("origin", "=ilike", f"{ORIGIN_PREFIX}%")])
removed = 0
for po in old:
    try:
        if po.state in ("purchase", "done"):
            po.with_context(**PO_ctx).button_cancel()
        po.with_context(**PO_ctx).unlink()
        removed += 1
    except Exception as ex:
        print(f"  ~ Không xóa {po.name}: {ex}")
print(f"  ✓ Đã xóa {removed} PO cũ")

# ── Tạo PO mới ───────────────────────────────────────────────────────────────
print("\n▶ Tạo PO lịch sử...")
total_created = 0
po_names = []

for cfg in PRODUCTS:
    prod = get_product(cfg["code"])
    if not prod:
        print(f"  ✗ Không tìm thấy {cfg['code']}")
        continue

    uom = env["uom.uom"].search([("name", "ilike", cfg["unit"])], limit=1)
    if not uom:
        uom = prod.uom_po_id

    months = cfg["months"]
    anomaly_month = cfg.get("anomaly_month")
    anomaly_vendor = cfg.get("anomaly_vendor")

    for m in range(months, 0, -1):
        for v in cfg["vendors"]:
            partner = get_partner(v["pid"])
            if not partner:
                continue

            base = float(v["base"])
            is_anomaly = (anomaly_month is not None and m == anomaly_month
                          and v["pid"] == anomaly_vendor)

            if is_anomaly:
                price = spike(base, cfg.get("anomaly_dir", 1), magnitude=0.40)
            else:
                # Thêm seasonal trend: tăng nhẹ cuối năm, giảm đầu năm
                season_factor = 1.0 + 0.05 * (1 - abs(m - 6) / 6)
                price = vary(base * season_factor, pct_range=0.06)

            qty = random.randint(*cfg["qty_range"])
            order_date = po_date(m, day=random.randint(5, 25))

            po = env["purchase.order"].with_context(**PO_ctx).create({
                "partner_id": partner.id,
                "company_id": company.id,
                "currency_id": company.currency_id.id,
                "currency_rate": 1.0,
                "origin": f"{ORIGIN_PREFIX}{cfg['code']}|M{m:02d}|V{v['pid']}",
                "date_order": order_date,
                "order_line": [(0, 0, {
                    "product_id": prod.id,
                    "name": prod.name,
                    "product_qty": float(qty),
                    "product_uom": uom.id or prod.uom_po_id.id,
                    "price_unit": price,
                    "date_planned": order_date,
                })],
            })
            po.with_context(**PO_ctx).button_confirm()
            total_created += 1
            if total_created <= 3:
                po_names.append(po.name)

print(f"  ✓ Tạo {total_created} PO xác nhận")
print(f"  → Ví dụ: {', '.join(po_names)}…")

# ── QA data: mark một số picking là passed ────────────────────────────────────
print("\n▶ Gắn QA pass cho stock.picking...")
pickings = env["stock.picking"].search([
    ("origin", "=ilike", f"{ORIGIN_PREFIX}%"),
    ("state", "=", "assigned"),
])
qa_passed = 0
for pick in pickings[:60]:   # 60 picking đầu
    try:
        pick.nfc_qa_passed = True
        pick.nfc_qa_note = "Đạt — seed demo"
        qa_passed += 1
    except Exception:
        pass
env.cr.commit()
print(f"  ✓ QA passed: {qa_passed} picking")

# ── Summary ───────────────────────────────────────────────────────────────────
po_total = env["purchase.order"].search_count([("origin", "=ilike", f"{ORIGIN_PREFIX}%")])
products_covered = len(PRODUCTS)
print(f"""
{'=' * 65}
✅  Seed hoàn tất
{'=' * 65}
  PO đã tạo        : {total_created}
  Sản phẩm         : {products_covered}
  Tháng lịch sử    : 8-12 tháng mỗi SP
  Anomaly plants   : {sum(1 for c in PRODUCTS if c.get('anomaly_month'))} SP có spike giá bất thường
  QA data          : {qa_passed} picking passed
{'=' * 65}
""")

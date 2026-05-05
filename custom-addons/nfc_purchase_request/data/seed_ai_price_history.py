#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seed lịch sử giá mua (PO đã xác nhận) nhiều tháng + nhiều NCC — phục vụ test nfc_ai_insight
(banner passive + biểu đồ đa NCC).

Chạy sau seed_demo.py (và tùy chọn seed_transactions.py):

  odoo-bin shell -c /opt/odoo18/nfc.conf --no-http < seed_ai_price_history.py

Idempotent: xóa các PO có origin bắt đầu bằng NFC-AI-PH| rồi tạo lại bộ 6 tháng × 3 NCC.
"""
from datetime import date, datetime, time

from dateutil.relativedelta import relativedelta

ORIGIN_PREFIX = "NFC-AI-PH|"

print("=" * 65)
print("NFC — Seed lịch sử giá (AI insight / biểu đồ NCC)")
print("=" * 65)

company = env["res.company"].browse(1)
PO_ctx = {
    "mail_create_nosubscribe": True,
    "tracking_disable": True,
    "mail_notrack": True,
}


def partner_ilike(fragment):
    return env["res.partner"].search(
        [("name", "ilike", fragment), ("supplier_rank", ">", 0)],
        limit=1,
    )


prod = env["product.product"].search(
    [("default_code", "=", "BB-HOP-ISOUP-30G")], limit=1
)
if not prod:
    print("  ✗ Không tìm thấy sản phẩm BB-HOP-ISOUP-30G — chạy seed_demo.py trước.")
else:
    v_tp = partner_ilike("TIẾN PHÁT")
    v_bd = partner_ilike("BÌNH DƯƠNG PRINT")
    v_dn = partner_ilike("ĐỒNG NAI XANH")
    partners = [x for x in (v_tp, v_bd, v_dn) if x]
    if len(partners) < 2:
        print("  ✗ Cần ít nhất 2 NCC (Tiến Phát, BD Print, Đồng Nai Xanh).")
    else:
        # --- cleanup ---
        old = env["purchase.order"].search([("origin", "=ilike", f"{ORIGIN_PREFIX}%")])
        for po in old:
            if po.state in ("draft", "sent"):
                po.with_context(**PO_ctx).unlink()
            elif po.state in ("purchase", "done"):
                try:
                    po.with_context(**PO_ctx).button_cancel()
                except Exception as ex:
                    print(f"  ~ Hủy {po.name}: {ex}")
                try:
                    po.with_context(**PO_ctx).unlink()
                except Exception as ex:
                    print(f"  ~ Xóa {po.name}: {ex}")

        env.cr.commit()

        today = date.today()
        uom = prod.uom_po_id or prod.uom_id
        # Giá gợi ý theo tháng (đơn vị VND / cái), mỗi NCC một "đường" khác nhau
        base = [2750.0, 2920.0, 2850.0][: len(partners)]
        slope = [12.0, -10.0, 6.0][: len(partners)]

        created = []
        for mi in range(6):
            mday = today + relativedelta(months=-(5 - mi))
            first = mday.replace(day=1)
            dt_order = datetime.combine(first, time(9, 0, 0))

            for vi, partner in enumerate(partners):
                pu = round(base[vi] + mi * slope[vi] + vi * 15.0, 2)
                origin = f"{ORIGIN_PREFIX}{first.strftime('%Y-%m')}|{partner.id}"
                po = env["purchase.order"].with_context(**PO_ctx).create(
                    {
                        "partner_id": partner.id,
                        "company_id": company.id,
                        "date_order": dt_order,
                        "origin": origin,
                        "notes": "Dữ liệu seed tự động — NFC AI price history demo.",
                        "order_line": [
                            (
                                0,
                                0,
                                {
                                    "product_id": prod.id,
                                    "name": prod.display_name,
                                    "product_qty": 500 + mi * 100 + vi * 50,
                                    "product_uom": uom.id,
                                    "price_unit": pu,
                                    "date_planned": dt_order,
                                },
                            )
                        ],
                    }
                )
                po.with_context(**PO_ctx).button_confirm()
                created.append(po.name)

        env.cr.commit()
        print(f"  ✓ Đã tạo {len(created)} PO xác nhận (6 tháng × {len(partners)} NCC).")
        print(f"  → VD: {', '.join(created[:3])}…")
        print("  → Mở RFQ draft có SP Hộp iSOUP 30g, tab Tóm tắt BGĐ để xem biểu đồ.")

print("=" * 65)

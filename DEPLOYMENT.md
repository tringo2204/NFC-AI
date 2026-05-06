# Hướng dẫn Triển khai — NFC ERP (Odoo 18)

> **Môi trường demo:** `165.245.182.237:8070`  
> **Stack:** Odoo 18 · Python 3.12 · PostgreSQL 16 · Ubuntu 24.04  
> Tài liệu này mô tả quy trình triển khai đầy đủ từ máy local lên server demo.

---

## Mục lục

1. [Cấu trúc dự án](#1-cấu-trúc-dự-án)
2. [Thông tin kết nối](#2-thông-tin-kết-nối)
3. [Quy trình deploy (hàng ngày)](#3-quy-trình-deploy-hàng-ngày)
4. [Upgrade module Odoo](#4-upgrade-module-odoo)
5. [Seed dữ liệu demo](#5-seed-dữ-liệu-demo)
6. [Quản lý service](#6-quản-lý-service)
7. [Các lưu ý quan trọng](#7-các-lưu-ý-quan-trọng)
8. [Xử lý sự cố thường gặp](#8-xử-lý-sự-cố-thường-gặp)

---

## 1. Cấu trúc dự án

```
NFC-ERP/
├── custom-addons/                 # Source code local (gốc để chỉnh sửa)
│   ├── nfc_purchase_request/      # Module luồng mua hàng + PR/RFQ/PO workflow
│   │   ├── models/
│   │   │   ├── purchase_request.py       # Model PR + state machine
│   │   │   ├── purchase_order.py         # Mở rộng PO: CEO approval, anomaly detection
│   │   │   └── purchase_order_line.py    # Patch ZeroDivisionError currency_rate
│   │   ├── views/
│   │   ├── wizard/
│   │   └── data/
│   │       ├── seed_config.py            # Config Odoo cơ bản (currency, warehouse…)
│   │       └── seed_rich_history.py      # Seed 278 PO lịch sử (12 tháng × 13 SP × 3-4 NCC)
│   └── nfc_ai_insight/            # Module AI analytics cho Mua hàng
│       ├── models/
│       │   └── purchase_order.py         # Passive banner, multi-line chart, NCC scorecard
│       ├── views/
│       │   └── purchase_order_views.xml  # Tab "Tóm tắt BGĐ"
│       └── static/src/
│           └── components/
│               ├── insight_badge.js      # Badge AI trên price_unit
│               └── multi_line_chart_field.js  # Widget biểu đồ OWL/SVG
├── ai/                            # FastAPI backend (Price Analyzer)
│   └── backend/
│       └── analytics/
│           └── price_analyzer.py         # Pure SQL: phân tích giá không cần LLM
└── DEPLOYMENT.md                  # File này
```

### ⚠️ Lưu ý đường dẫn quan trọng

| Máy local | Server (Odoo đọc từ đây) |
|-----------|--------------------------|
| `custom-addons/` (gạch **ngang**) | `/opt/odoo18/custom_addons/` (gạch **dưới**) |

**Luôn sync lên `custom_addons` (gạch dưới)**, không phải `custom-addons`.

---

## 2. Thông tin kết nối

| Thành phần | Giá trị |
|-----------|---------|
| Server IP | `165.245.182.237` |
| SSH key | `~/.ssh/github-personal` |
| SSH user | `root` |
| Odoo URL | `http://165.245.182.237:8070` |
| Odoo admin password | `nfc_admin_2026` |
| PostgreSQL DB | `nfc_erp` |
| PostgreSQL user | `odoo18` / `odoo18` |
| Odoo config | `/opt/odoo18/nfc.conf` |
| Custom addons | `/opt/odoo18/custom_addons/` |
| Log file | `/var/log/odoo/nfc-erp.log` |
| Service | `odoo18` (systemd) |

---

## 3. Quy trình deploy (hàng ngày)

### Bước 1 — Sync code lên server

```bash
rsync -avz -e "ssh -i ~/.ssh/github-personal" \
  --exclude='__pycache__' --exclude='*.pyc' \
  /Users/tony/E-Project/NFC-ERP/custom-addons/ \
  root@165.245.182.237:/opt/odoo18/custom_addons/
```

> **Quan trọng:** Destination là `custom_addons/` (gạch dưới).

### Bước 2 — Upgrade module

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  /opt/odoo18/.venv/bin/python /opt/odoo18/odoo-bin \
    -c /opt/odoo18/nfc.conf \
    --update nfc_purchase_request,nfc_ai_insight \
    --stop-after-init
'
```

### Bước 3 — Restart service

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 'systemctl restart nfc-erp.service'
```

### Bước 4 — Kiểm tra

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 'curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:8070/web/login'
# Kỳ vọng: HTTP 200
```

---

## 4. Upgrade module Odoo

### Upgrade 1 module cụ thể

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  /opt/odoo18/.venv/bin/python /opt/odoo18/odoo-bin \
    -c /opt/odoo18/nfc.conf \
    --update nfc_ai_insight \
    --stop-after-init
'
```

### Force upgrade (khi field mới không được nhận)

```bash
# Clear cache trước
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  find /opt/odoo18/custom_addons -name "*.pyc" -delete
  find /opt/odoo18/custom_addons -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null; true
  /opt/odoo18/.venv/bin/python /opt/odoo18/odoo-bin \
    -c /opt/odoo18/nfc.conf \
    --update nfc_purchase_request,nfc_ai_insight \
    --stop-after-init
'
```

### Kiểm tra field đã được đăng ký chưa

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  PGPASSWORD=odoo18 psql -U odoo18 -h localhost nfc_erp -tc "
    SELECT name FROM ir_model_fields
    WHERE model = '"'"'purchase.order'"'"' AND name LIKE '"'"'nfc_%'"'"'
    ORDER BY name;
  "
'
```

---

## 5. Seed dữ liệu demo

### Seed cơ bản (config Odoo)

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  /opt/odoo18/.venv/bin/python /opt/odoo18/odoo-bin \
    shell -c /opt/odoo18/nfc.conf --no-http \
    < /opt/odoo18/custom_addons/nfc_purchase_request/data/seed_config.py
'
```

### Seed lịch sử mua hàng (278 PO × 13 SP × 3-4 NCC × 12 tháng)

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  /opt/odoo18/.venv/bin/python /opt/odoo18/odoo-bin \
    shell -c /opt/odoo18/nfc.conf --no-http \
    < /opt/odoo18/custom_addons/nfc_purchase_request/data/seed_rich_history.py
'
```

> Script seed là **idempotent** — xóa data cũ (`RICH-HIST|…`) trước khi tạo lại. An toàn khi chạy nhiều lần.

### Gắn QA Pass cho picking sau seed

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  PGPASSWORD=odoo18 psql -U odoo18 -h localhost nfc_erp -c "
    UPDATE stock_picking sp
    SET nfc_qa_passed = true, nfc_qa_note = '"'"'Đạt — seed demo'"'"'
    FROM stock_move sm
    JOIN purchase_order_line pol ON pol.id = sm.purchase_line_id
    JOIN purchase_order po ON po.id = pol.order_id
    WHERE sm.picking_id = sp.id
      AND po.origin ILIKE '"'"'RICH-HIST|%'"'"'
      AND sp.state IN ('"'"'done'"'"', '"'"'assigned'"'"');
  "
'
```

---

## 6. Quản lý service

```bash
# Xem trạng thái
ssh -i ~/.ssh/github-personal root@165.245.182.237 'systemctl status nfc-erp.service --no-pager'

# Restart
ssh -i ~/.ssh/github-personal root@165.245.182.237 'systemctl restart nfc-erp.service'

# Stop / Start
ssh -i ~/.ssh/github-personal root@165.245.182.237 'systemctl stop nfc-erp.service'
ssh -i ~/.ssh/github-personal root@165.245.182.237 'systemctl start nfc-erp.service'

# Xem log realtime
ssh -i ~/.ssh/github-personal root@165.245.182.237 'journalctl -u nfc-erp.service -f'

# Xem log file (tail)
ssh -i ~/.ssh/github-personal root@165.245.182.237 'tail -100 /var/log/odoo/nfc-erp.log'

# Xem log lỗi gần nhất
ssh -i ~/.ssh/github-personal root@165.245.182.237 'journalctl -u nfc-erp.service --since "-10 min" --no-pager | grep -E "(ERROR|error|Traceback)"'
```

---

## 7. Các lưu ý quan trọng

### 7.1 Đường dẫn addons

Odoo đọc từ **`/opt/odoo18/custom_addons/`** (gạch dưới).  
Thư mục `/opt/odoo18/custom-addons/` (gạch ngang) tồn tại nhưng **không được dùng** — sync sai đường sẽ không có tác dụng.

### 7.2 Tỷ giá tiền tệ

Odoo cần tỷ giá VND = 1.0 để tránh `ZeroDivisionError`. Nếu thấy lỗi khi vào Inventory/Kế toán:

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
  PGPASSWORD=odoo18 psql -U odoo18 -h localhost nfc_erp -c "
    -- Đảm bảo VND có rate = 1.0
    INSERT INTO res_currency_rate (currency_id, rate, name, company_id, create_uid, write_uid, create_date, write_date)
    SELECT id, 1.0, CURRENT_DATE, 1, 1, 1, NOW(), NOW()
    FROM res_currency WHERE name = '"'"'VND'"'"'
    ON CONFLICT DO NOTHING;

    -- Fix PO có currency_rate = 0/NULL
    UPDATE purchase_order SET currency_rate = 1.0
    WHERE (currency_rate IS NULL OR currency_rate = 0)
      AND currency_id = (SELECT id FROM res_currency WHERE name = '"'"'VND'"'"');
  "
'
```

### 7.3 Odoo shell — cách chạy script Python

```bash
# Dùng stdin redirect (không dùng -c vì Odoo shell không hỗ trợ)
/opt/odoo18/.venv/bin/python /opt/odoo18/odoo-bin \
  shell -c /opt/odoo18/nfc.conf --no-http \
  < /path/to/script.py
```

> Biến `env` được inject tự động bởi Odoo shell. Gọi `env.cr.commit()` để lưu thay đổi.

### 7.4 Field mới không hiển thị sau upgrade

Nguyên nhân thường gặp: file `.pyc` cache cũ hoặc sync nhầm đường dẫn.

**Checklist:**
1. Sync đúng đường dẫn `custom_addons/` (gạch dưới)?
2. Xóa `__pycache__` rồi upgrade lại?
3. Kiểm tra field có trong `ir_model_fields` chưa (xem [Bước upgrade](#force-upgrade-khi-field-mới-không-được-nhận))?

---

## 8. Xử lý sự cố thường gặp

### Lỗi: `ZeroDivisionError: float division by zero`

**Vị trí:** `purchase_requisition/models/purchase.py`  
**Nguyên nhân:** `purchase_order.currency_rate = 0` hoặc `NULL`  
**Fix:** Xem [mục 7.2](#72-tỷ-giá-tiền-tệ)

---

### Lỗi: `Tokenizer error: could not tokenize 'var(...)'`

**Nguyên nhân:** OWL template dùng `t-att-*` với giá trị CSS `var(--...)` — OWL xử lý như JavaScript expression.  
**Fix:** Khai báo màu trong CSS class, không dùng `t-att-stroke` hay `t-att-style` với `var()`.

---

### Lỗi: Field mới thêm vào model không hiển thị

**Nguyên nhân:** Sync nhầm `custom-addons/` (gạch ngang) thay vì `custom_addons/` (gạch dưới).  
**Fix:**
```bash
rsync ... root@165.245.182.237:/opt/odoo18/custom_addons/   # ✅ Đúng
rsync ... root@165.245.182.237:/opt/odoo18/custom-addons/   # ❌ Sai
```

---

### Lỗi: `KeyError: 'res.currency_rate'`

**Nguyên nhân:** Tên model sai — trong Odoo 18 là `res.currency.rate` (có dấu chấm thứ hai).  
**Fix:** Dùng `env['res.currency.rate']`.

---

### Lỗi: `ERROR: column reference "id" is ambiguous`

**Nguyên nhân:** SQL JOIN nhiều bảng đều có cột `id`, không dùng table alias.  
**Fix:** Prefix với alias, ví dụ `pt.id`, `pp.id`.

---

### Kiểm tra nhanh hệ thống

```bash
ssh -i ~/.ssh/github-personal root@165.245.182.237 '
echo "=== Odoo service ==="
systemctl status nfc-erp.service --no-pager | head -5

echo "=== HTTP check ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8070/web/login

echo "=== Database ==="
PGPASSWORD=odoo18 psql -U odoo18 -h localhost nfc_erp -tc "
  SELECT
    (SELECT COUNT(*) FROM purchase_order WHERE origin ILIKE '"'"'RICH-HIST|%'"'"') AS demo_po,
    (SELECT COUNT(*) FROM purchase_order WHERE state IN ('"'"'purchase'"'"','"'"'done'"'"')) AS confirmed_po,
    (SELECT COUNT(DISTINCT product_id) FROM purchase_order_line pol
     JOIN purchase_order po ON po.id = pol.order_id
     WHERE po.state IN ('"'"'purchase'"'"','"'"'done'"'"')) AS products_with_history;
"
'
```

---

## Tính năng đã triển khai

| Tính năng | Module | Mô tả |
|-----------|--------|-------|
| **Passive RFQ Banner** | `nfc_ai_insight` | Strip 4 chỉ số giá trên form RFQ/PO (chỉ hiện khi draft/sent) |
| **Biểu đồ giá NCC** | `nfc_ai_insight` | Multi-line SVG chart, top 4 NCC × 6 tháng — tab "Tóm tắt BGĐ" |
| **Bảng chi tiết BGĐ** | `nfc_ai_insight` | Bảng giá min/max/avg theo SP và NCC |
| **Bảng điểm NCC** | `nfc_ai_insight` | Rank NCC: giá TB + QA pass rate + ngày trễ trung bình |
| **AI Badge (price_unit)** | `nfc_ai_insight` | Badge nhỏ trên đơn giá: level (good/normal/high/critical) + popover |
| **Anomaly Detection** | `nfc_purchase_request` | Cảnh báo chatter 🟡/🔴 khi xác nhận PO có giá bất thường (Z-score > 1.5σ) |
| **PR Workflow** | `nfc_purchase_request` | State machine PR: Draft → Submitted → Approved → Accepted |
| **CEO Approval** | `nfc_purchase_request` | Tự động yêu cầu BGĐ duyệt khi PO > 50M VND |
| **RFQ Validation Gate** | `nfc_purchase_request` | Bắt buộc ≥ 3 báo giá + bằng chứng cho PR-SKU |
| **Price Analyzer API** | `ai/backend` | FastAPI endpoint `/api/insight` — pure SQL, không cần LLM |

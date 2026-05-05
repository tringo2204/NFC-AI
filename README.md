# NFC ERP — Nature Foods Co., Ltd

Odoo 18 Enterprise + AI Decision Platform cho NFC (naturefoods.com.vn).

## Cấu trúc project

```
NFC-ERP/
├── custom-addons/
│   └── nfc_purchase_request/    # Module mua hàng tùy chỉnh
│       ├── models/              # PR, PO extension, Stock QA Gate
│       ├── views/               # Form, List, Kanban, Menu
│       ├── wizard/              # PR Approve/Reject, QA Fail
│       └── data/                # Seed scripts, sequences, templates
├── ai/
│   ├── backend/                 # FastAPI + LangGraph AI engine
│   │   ├── api/                 # REST endpoints
│   │   ├── agents/              # LangGraph agent
│   │   ├── events/              # Event Aggregator + Domain Router
│   │   ├── tools/               # @tool functions theo domain
│   │   │   ├── purchase/        # 6 tools: price_history, supplier...
│   │   │   ├── hr/              # 4 tools: salary_benchmark...
│   │   │   ├── stock/           # 4 tools: reorder_suggestion...
│   │   │   └── sale/            # 3 tools: margin_analysis...
│   │   ├── cache/               # Redis TTL cache
│   │   ├── logger/              # Decision Logger + Feedback Loop
│   │   └── schemas/             # Pydantic models, Decision JSON schema
│   └── odoo_module/             # OWL 2 widget (InsightBadge)
└── docs/                        # Tài liệu nghiệp vụ, ADR
```

## Module tùy chỉnh đã xây dựng

### `nfc_purchase_request`
- **PR Workflow:** Bản Nháp → Chờ Duyệt → Đã Duyệt → MH Xác Nhận (3 loại: SKU / Investment / Operation)
- **RFQ Validation Gate:** Bắt buộc ≥ 3 vendor báo giá trước khi xác nhận PO
- **PO CEO Approval:** Tự động yêu cầu BGĐ duyệt khi tổng PO > 50 triệu VND
- **QA Gate:** Hàng nhập kho phải qua kiểm định QA, block validate nếu chưa pass

## AI Decision Platform (đang phát triển)

AI Layer chạy song song với Odoo — phân tích dữ liệu tại điểm quyết định.

| Sprint | Nội dung | Status |
|--------|----------|--------|
| S0 | FastAPI skeleton, Tool Registry, DB adapter | 🚧 In Progress |
| S1 | Event Aggregator, Domain Router, Purchase tools | ⏳ Planned |
| S2 | HR tools, Cache Redis, Decision Logger | ⏳ Planned |
| S3 | OWL InsightBadge | ⏳ Planned |
| S4 | Guided cards, Decision Panel | ⏳ Planned |
| S5 | Feedback Loop | ⏳ Planned |

## Demo

| URL | Mô tả |
|-----|-------|
| http://165.245.182.237:8070 | NFC ERP (Odoo 18) |
| http://165.245.182.237:8100 | AI API (Sprint 0+) |

## Users demo

| Login | Password | Vai trò |
|-------|----------|---------|
| admin | admin | Admin |
| linh.pham | nfc2026 | NV Mua Hàng |
| huong.le | nfc2026 | TP Mua Hàng |
| an.nguyen | nfc2026 | BGĐ |
| thu.tran.qa | nfc2026 | QA |

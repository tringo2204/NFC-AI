# -*- coding: utf-8 -*-
"""Tóm tắt một cửa cho BGĐ: thống kê giá nội bộ + lịch sử riêng NCC trên RFQ/PO."""
import json
from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import html_escape


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # Tương thích DB/view còn sót sau khi gỡ tính năng cảnh báo giá + wizard (không dùng logic).
    nfc_ai_price_risk = fields.Boolean(
        string="(legacy) Cảnh báo giá NFC",
        compute="_compute_nfc_ai_price_risk_legacy",
        store=False,
    )
    nfc_ai_price_risk_message = fields.Text(
        string="(legacy) Chi tiết cảnh báo",
        compute="_compute_nfc_ai_price_risk_legacy",
        store=False,
    )

    nfc_executive_summary_html = fields.Html(
        string="Tóm tắt BGĐ (giá nội bộ)",
        compute="_compute_nfc_executive_summary_html",
        sanitize=False,
        store=False,
    )
    nfc_passive_rfq_banner_html = fields.Html(
        string="NFC — Insight passive (RFQ)",
        compute="_compute_nfc_passive_rfq_banner_html",
        sanitize=False,
        store=False,
    )
    nfc_price_multiline_json = fields.Text(
        string="NFC — Biểu đồ giá theo tháng (JSON)",
        compute="_compute_nfc_price_multiline_json",
        store=False,
    )

    def _compute_nfc_ai_price_risk_legacy(self):
        for order in self:
            order.nfc_ai_price_risk = False
            order.nfc_ai_price_risk_message = False

    def _nfc_price_stats_for_product(
        self, product_id, months, partner_id=None, exclude_po_id=None
    ):
        """Trả (cnt, min, max, avg) từ PO đã xác nhận, có thể lọc theo partner_id."""
        self.env.cr.execute(
            """
            SELECT
                COUNT(*)::integer,
                COALESCE(MIN(pol.price_unit), 0)::float,
                COALESCE(MAX(pol.price_unit), 0)::float,
                COALESCE(AVG(pol.price_unit), 0)::float
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE pol.product_id = %s
              AND po.state IN ('purchase', 'done')
              AND po.date_order >= CURRENT_DATE - make_interval(months => %s)
              AND (%s IS NULL OR po.partner_id = %s)
              AND (%s IS NULL OR po.id <> %s)
            """,
            (
                product_id,
                months,
                partner_id,
                partner_id,
                exclude_po_id,
                exclude_po_id,
            ),
        )
        row = self.env.cr.fetchone()
        if not row:
            return 0, 0.0, 0.0, 0.0
        return int(row[0] or 0), float(row[1] or 0), float(row[2] or 0), float(row[3] or 0)

    @staticmethod
    def _nfc_fmt_vnd(val):
        return f"{round(val):,}".replace(",", ".")

    def _nfc_primary_po_line(self):
        lines = self.order_line.filtered(lambda l: l.product_id and l.price_unit)
        if not lines:
            return self.order_line.browse()
        return max(
            lines,
            key=lambda l: (l.product_qty or 0.0) * (l.price_unit or 0.0),
        )

    def _nfc_build_monthly_supplier_series(self, product_id, months, exclude_po_id, max_suppliers):
        self.env.cr.execute(
            """
            WITH sup_tot AS (
                SELECT rp.name AS supplier, COUNT(pol.id)::int AS n
                FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                JOIN res_partner rp ON rp.id = po.partner_id
                WHERE pol.product_id = %s
                  AND po.state IN ('purchase', 'done')
                  AND po.date_order >= CURRENT_DATE - make_interval(months => %s)
                  AND (%s IS NULL OR po.id <> %s)
                GROUP BY rp.name
                ORDER BY n DESC
                LIMIT %s
            ),
            per_cell AS (
                SELECT
                    to_char(date_trunc('month', po.date_order::timestamp), 'YYYY-MM') AS ym,
                    rp.name AS supplier,
                    AVG(pol.price_unit)::float AS avg_pu
                FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                JOIN res_partner rp ON rp.id = po.partner_id
                WHERE pol.product_id = %s
                  AND po.state IN ('purchase', 'done')
                  AND po.date_order >= CURRENT_DATE - make_interval(months => %s)
                  AND (%s IS NULL OR po.id <> %s)
                  AND rp.name IN (SELECT supplier FROM sup_tot)
                GROUP BY 1, 2
            )
            SELECT ym, supplier, avg_pu FROM per_cell
            ORDER BY ym, supplier
            """,
            (
                product_id,
                months,
                exclude_po_id,
                exclude_po_id,
                max_suppliers,
                product_id,
                months,
                exclude_po_id,
                exclude_po_id,
            ),
        )
        rows = self.env.cr.fetchall()
        if not rows:
            return None
        months_order = sorted({r[0] for r in rows})
        suppliers = []
        for r in rows:
            if r[1] not in suppliers:
                suppliers.append(r[1])
        by_sup = defaultdict(dict)
        for ym, sup, avg in rows:
            by_sup[sup][ym] = avg
        series = []
        for sup in suppliers:
            data = [by_sup[sup].get(m) for m in months_order]
            if any(v is not None for v in data):
                series.append({"name": sup, "data": data})
        good_lines = sum(
            1 for s in series if sum(1 for v in s["data"] if v is not None) >= 2
        )
        if len(months_order) < 2 and good_lines == 0:
            return None
        product = self.env["product.product"].browse(product_id)
        return {
            "title": f"Giá TB theo tháng — {product.display_name}",
            "subtitle": (
                f"{months} tháng — tối đa {max_suppliers} NCC tích cực nhất (dữ liệu nội bộ)."
            ),
            "categories": months_order,
            "series": series,
        }

    @api.depends(
        "order_line",
        "order_line.product_id",
        "order_line.product_qty",
        "order_line.price_unit",
        "partner_id",
        "state",
    )
    def _compute_nfc_passive_rfq_banner_html(self):
        months = 12
        for order in self:
            order.nfc_passive_rfq_banner_html = False
            if order.state not in ("draft", "sent"):
                continue
            primary = order._nfc_primary_po_line()
            if not primary:
                continue
            ex = order.id if isinstance(order.id, int) else None
            pu = primary.price_unit or 0.0
            pname = html_escape(primary.product_id.display_name)
            c, mn, _mx, av = order._nfc_price_stats_for_product(
                primary.product_id.id, months, partner_id=None, exclude_po_id=ex
            )
            vname = html_escape(order.partner_id.display_name) if order.partner_id else "—"
            dev_txt = "—"
            dev_cls = "text-muted"
            if c >= 3 and av > 0 and pu:
                d = (pu - av) / av * 100.0
                dev_txt = f"{d:+.1f}%"
                if d > 5:
                    dev_cls = "text-danger"
                elif d < -5:
                    dev_cls = "text-success"
                else:
                    dev_cls = "text-body"
            best = order._nfc_fmt_vnd(mn) if c else "—"
            avg_s = order._nfc_fmt_vnd(av) if c else "—"
            prop_s = order._nfc_fmt_vnd(pu) if pu else "—"
            if c < 3:
                callout = (
                    f"Chưa đủ lịch sử mua nội bộ (&lt;3 giao dịch trong {months} tháng) "
                    f"cho <strong>{pname}</strong>."
                )
            else:
                callout = (
                    f"<strong>{pname}</strong> — Đơn giá RFQ: <strong>{prop_s} đ</strong> "
                    f"(NCC: {vname}). TB nội bộ: <strong>{avg_s} đ</strong>, "
                    f"thấp nhất ghi nhận: <strong>{best} đ</strong>. "
                )
                if pu and av > 0:
                    if pu > av * 1.05:
                        callout += (
                            " Giá đang cao hơn TB — xem tab <em>Tóm tắt BGĐ</em> "
                            "và biểu đồ so sánh NCC."
                        )
                    elif pu < av * 0.95:
                        callout += " Giá đang tốt hơn TB nội bộ."
            order.nfc_passive_rfq_banner_html = f"""
<div class="nfc-passive-banner border rounded p-3 mb-2 bg-view">
  <div class="row g-2 text-center small">
    <div class="col-6 col-md-3">
      <div class="p-2 border rounded bg-view">
        <div class="text-muted">Đơn giá (dòng chính)</div>
        <strong>{prop_s} đ</strong>
        <div class="text-muted text-truncate" title="{pname}">{pname}</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="p-2 border rounded bg-view">
        <div class="text-muted">So với TB 12 tháng</div>
        <strong class="{dev_cls}">{dev_txt}</strong>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="p-2 border rounded bg-view">
        <div class="text-muted">TB nội bộ</div>
        <strong>{avg_s} đ</strong>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="p-2 border rounded bg-view">
        <div class="text-muted">Thấp nhất ghi nhận</div>
        <strong>{best} đ</strong>
      </div>
    </div>
  </div>
  <div class="alert alert-warning mt-3 mb-0 py-2 small">{callout}</div>
</div>"""

    @api.depends(
        "order_line",
        "order_line.product_id",
        "order_line.product_qty",
        "order_line.price_unit",
        "partner_id",
        "state",
    )
    def _compute_nfc_price_multiline_json(self):
        chart_months = 6
        max_sup = 4
        for order in self:
            order.nfc_price_multiline_json = False
            if order.state not in ("draft", "sent", "purchase", "done"):
                continue
            primary = order._nfc_primary_po_line()
            if not primary:
                continue
            ex = order.id if isinstance(order.id, int) else None
            payload = order._nfc_build_monthly_supplier_series(
                primary.product_id.id, chart_months, ex, max_sup
            )
            if payload:
                order.nfc_price_multiline_json = json.dumps(payload, ensure_ascii=False)

    @api.depends(
        "order_line",
        "order_line.product_id",
        "order_line.price_unit",
        "partner_id",
        "state",
    )
    def _compute_nfc_executive_summary_html(self):
        months = 12
        min_hist = 1
        for order in self:
            if order.state not in ("draft", "sent", "purchase", "done"):
                order.nfc_executive_summary_html = False
                continue
            lines = order.order_line.filtered(lambda l: l.product_id)
            if not lines:
                order.nfc_executive_summary_html = (
                    "<p class='text-muted'>Chưa có dòng sản phẩm.</p>"
                )
                continue
            pid = order.partner_id.id if order.partner_id else None
            ex = order.id if isinstance(order.id, int) else None
            vname = html_escape(order.partner_id.display_name) if order.partner_id else ""

            rows_html = []
            for line in lines:
                pn = html_escape(line.product_id.display_name)
                pu = line.price_unit or 0.0
                cur = self._nfc_fmt_vnd(pu)

                c_all, mn_all, mx_all, av_all = order._nfc_price_stats_for_product(
                    line.product_id.id, months, partner_id=None, exclude_po_id=ex
                )
                c_pv, mn_pv, mx_pv, av_pv = order._nfc_price_stats_for_product(
                    line.product_id.id, months, partner_id=pid, exclude_po_id=ex
                )

                def row_block(title, cnt, mn, mx, av):
                    if cnt < min_hist:
                        return (
                            f"<td colspan='4' class='text-muted'>{html_escape(title)}: "
                            f"chưa đủ lịch sử (0 giao dịch trong {months} tháng)</td>"
                        )
                    dev = ""
                    if av > 0:
                        d = (pu - av) / av * 100.0
                        dev = f" ({d:+.0f}% so với TB phạm vi đang xét)"
                    return (
                        f"<td><small>{html_escape(title)}</small></td>"
                        f"<td class='text-end'>{self._nfc_fmt_vnd(mn)}</td>"
                        f"<td class='text-end'>{self._nfc_fmt_vnd(mx)}</td>"
                        f"<td class='text-end'><strong>{self._nfc_fmt_vnd(av)}</strong>"
                        f"<small>{html_escape(dev)}</small></td>"
                    )

                r_all = row_block("Toàn bộ NCC NFC", c_all, mn_all, mx_all, av_all)
                if pid:
                    r_pv = row_block(f"Cùng NCC: {vname}", c_pv, mn_pv, mx_pv, av_pv)
                else:
                    r_pv = (
                        "<td colspan='4' class='text-muted'>Chưa chọn nhà cung cấp — "
                        "chưa có cột lịch sử riêng NCC.</td>"
                    )

                rows_html.append(
                    "<tr>"
                    f"<td rowspan='2' class='align-middle'><strong>{pn}</strong><br/>"
                    f"<span class='text-muted'>Đơn giá RFQ/PO:</span> <strong>{cur} đ</strong></td>"
                    f"{r_all}</tr><tr>{r_pv}</tr>"
                )

            table = (
                "<div class='o_inner_group nfc_executive_summary'>"
                "<p class='mb-2'><strong>Phạm vi:</strong> dữ liệu mua nội bộ NFC "
                f"(PO đã xác nhận, {months} tháng gần nhất). "
                "Không bao gồm giá thị trường bên ngoài.</p>"
                "<table class='table table-sm table-striped o_list_table'>"
                "<thead><tr>"
                "<th>Sản phẩm / Giá hiện tại</th>"
                "<th>Phạm vi</th>"
                "<th class='text-end'>Thấp nhất</th>"
                "<th class='text-end'>Cao nhất</th>"
                "<th class='text-end'>Trung bình</th>"
                "</tr></thead><tbody>"
                + "".join(rows_html)
                + "</tbody></table></div>"
            )
            order.nfc_executive_summary_html = table

# -*- coding: utf-8 -*-
"""Tóm tắt một cửa cho BGĐ: thống kê giá nội bộ + lịch sử riêng NCC trên RFQ/PO."""
from odoo import api, fields, models
from odoo.tools import html_escape


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    nfc_executive_summary_html = fields.Html(
        string="Tóm tắt BGĐ (giá nội bộ)",
        compute="_compute_nfc_executive_summary_html",
        sanitize=False,
        store=False,
    )

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

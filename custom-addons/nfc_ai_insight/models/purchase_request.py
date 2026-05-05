# -*- coding: utf-8 -*-
"""Tóm tắt BGĐ trên PR: thống kê giá toàn NCC NFC (chưa gắn NCC cố định)."""
from odoo import api, fields, models
from odoo.tools import html_escape


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    nfc_executive_summary_html = fields.Html(
        string="Tóm tắt BGĐ (giá tham khảo nội bộ)",
        compute="_compute_nfc_executive_summary_html",
        sanitize=False,
        store=False,
    )

    def _nfc_pr_line_stats(self, product_id, months):
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
            """,
            (product_id, months),
        )
        row = self.env.cr.fetchone()
        if not row:
            return 0, 0.0, 0.0, 0.0
        return int(row[0] or 0), float(row[1] or 0), float(row[2] or 0), float(row[3] or 0)

    @staticmethod
    def _fmt_vnd(val):
        return f"{round(val):,}".replace(",", ".")

    @api.depends("line_ids", "line_ids.product_id", "line_ids.estimated_price", "state")
    def _compute_nfc_executive_summary_html(self):
        months = 12
        for pr in self:
            lines = pr.line_ids.filtered(lambda l: l.product_id)
            if not lines:
                pr.nfc_executive_summary_html = (
                    "<p class='text-muted'>Chưa có dòng sản phẩm trên PR.</p>"
                )
                continue
            body = []
            for line in lines:
                pn = html_escape(line.product_id.display_name)
                est = line.estimated_price or 0.0
                c, mn, mx, av = pr._nfc_pr_line_stats(line.product_id.id, months)
                if c < 1:
                    body.append(
                        f"<tr><td><strong>{pn}</strong></td>"
                        f"<td colspan='4' class='text-muted'>Chưa có lịch sử mua nội bộ "
                        f"({months} tháng).</td></tr>"
                    )
                    continue
                dev = ""
                if av > 0 and est:
                    d = (est - av) / av * 100.0
                    dev = (
                        f" — ước tính {pr._fmt_vnd(est)} đ "
                        f"<strong>({d:+.0f}% so với TB)</strong>"
                    )
                elif est:
                    dev = f" — ước tính {pr._fmt_vnd(est)} đ"
                body.append(
                    "<tr>"
                    f"<td><strong>{pn}</strong><br/><small class='text-muted'>{dev}</small></td>"
                    f"<td class='text-end'>{pr._fmt_vnd(mn)}</td>"
                    f"<td class='text-end'>{pr._fmt_vnd(mx)}</td>"
                    f"<td class='text-end'><strong>{pr._fmt_vnd(av)}</strong></td>"
                    f"<td class='text-end'>{c}</td>"
                    "</tr>"
                )
            pr.nfc_executive_summary_html = (
                "<div class='nfc_executive_summary'>"
                "<p class='mb-2'><strong>Tham khảo cho người lập PR:</strong> "
                f"min / max / trung bình giá mua nội bộ ({months} tháng, mọi NCC). "
                "Khi đã có RFQ, mở đơn mua và xem tab <strong>Tóm tắt BGĐ</strong> "
                "để có thêm cột <strong>cùng NCC</strong> với nhà cung cấp đang chọn.</p>"
                "<table class='table table-sm table-striped'>"
                "<thead><tr>"
                "<th>Sản phẩm</th>"
                "<th class='text-end'>Thấp nhất</th>"
                "<th class='text-end'>Cao nhất</th>"
                "<th class='text-end'>TB</th>"
                "<th class='text-end'>Số lần mua</th>"
                "</tr></thead><tbody>"
                + "".join(body)
                + "</tbody></table></div>"
            )

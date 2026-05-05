/** @odoo-module **/
import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];

/** Parse computed JSON từ server — categories + series[].data[] */
function parsePayload(raw) {
    if (!raw || typeof raw !== "string") return null;
    try {
        const o = JSON.parse(raw);
        if (!o?.categories?.length || !o?.series?.length) return null;
        return o;
    } catch {
        return null;
    }
}

export class NfcMultilineChartField extends Component {
    static template = xml`
        <div class="nfc-multiline-chart-field">
            <div t-if="!svgPayload" class="text-muted small">Chưa đủ dữ liệu nhiều NCC để vẽ biểu đồ theo tháng.</div>
            <div t-else="">
                <div class="nfc-mlc-title small fw-bold mb-1" t-esc="svgPayload.title"/>
                <svg xmlns="http://www.w3.org/2000/svg" t-att-viewBox="svgPayload.viewBox" class="nfc-mlc-svg" preserveAspectRatio="xMidYMid meet">
                    <!-- Legend -->
                    <g class="nfc-mlc-legend">
                        <t t-foreach="svgPayload.legend" t-as="lg" t-key="lg_index">
                            <rect t-att-x="lg.x" y="4" width="10" height="10" t-att-fill="lg.color"/>
                            <text t-att-x="lg.x + 14" y="13" font-size="10" fill="#374151" t-esc="lg.name"/>
                        </t>
                    </g>
                    <!-- Polylines + points -->
                    <t t-foreach="svgPayload.paths" t-as="p" t-key="p_index">
                        <polyline
                            fill="none"
                            t-att-stroke="p.color"
                            stroke-width="2"
                            stroke-linejoin="round"
                            t-att-points="p.pointsStr"
                        />
                        <t t-foreach="p.dots" t-as="d" t-key="d_index">
                            <circle t-att-cx="d.x" t-att-cy="d.y" r="3" t-att-fill="p.color" stroke="#fff" stroke-width="1"/>
                        </t>
                    </t>
                    <!-- X labels -->
                    <t t-foreach="svgPayload.xlabels" t-as="xl" t-key="xl_index">
                        <text
                            t-att-x="xl.x"
                            t-att-y="xl.y"
                            font-size="9"
                            fill="#6b7280"
                            text-anchor="middle"
                            t-esc="xl.text"
                        />
                    </t>
                </svg>
                <div class="small text-muted mt-1" t-esc="svgPayload.subtitle"/>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };

    get svgPayload() {
        const raw = this.props.record?.data?.[this.props.name];
        const data = parsePayload(raw);
        if (!data) return null;
        const cats = data.categories;
        const series = data.series || [];
        const W = 560;
        const H = 200;
        const pad = { t: 28, r: 16, b: 28, l: 44 };
        const innerW = W - pad.l - pad.r;
        const innerH = H - pad.t - pad.b;
        let minY = Infinity;
        let maxY = -Infinity;
        for (const s of series) {
            for (const v of s.data || []) {
                if (v == null || Number.isNaN(v)) continue;
                minY = Math.min(minY, v);
                maxY = Math.max(maxY, v);
            }
        }
        if (!Number.isFinite(minY) || minY === maxY) {
            minY = minY === maxY && Number.isFinite(minY) ? minY * 0.95 : 0;
            maxY = maxY || 1;
        }
        const yPad = (maxY - minY) * 0.08 || 1;
        minY -= yPad;
        maxY += yPad;
        const xScale = (i) => pad.l + (cats.length <= 1 ? innerW / 2 : (i / (cats.length - 1)) * innerW);
        const yScale = (v) => pad.t + innerH - ((v - minY) / (maxY - minY)) * innerH;

        const paths = [];
        series.forEach((s, si) => {
            const color = COLORS[si % COLORS.length];
            const pts = [];
            const dots = [];
            (s.data || []).forEach((v, i) => {
                if (v == null || Number.isNaN(v)) return;
                const x = xScale(i);
                const y = yScale(v);
                pts.push(`${x},${y}`);
                dots.push({ x, y });
            });
            if (!pts.length) return;
            paths.push({ color, pointsStr: pts.join(" "), dots });
        });
        if (!paths.length) return null;

        const xlabels = cats.map((c, i) => ({
            x: xScale(i),
            y: H - 8,
            text: String(c).length >= 7 ? String(c).slice(2).replace("-", "/") : String(c),
        }));
        const legend = series.slice(0, 6).map((s, i) => ({
            x: 10 + i * 130,
            name: s.name?.length > 18 ? `${s.name.slice(0, 16)}…` : s.name,
            color: COLORS[i % COLORS.length],
        }));

        return {
            title: data.title || "Giá TB theo tháng (đơn vị: đ)",
            subtitle: data.subtitle || "",
            viewBox: `0 0 ${W} ${H}`,
            paths,
            xlabels,
            legend,
        };
    }
}

registry.category("fields").add("nfc_multiline_chart", {
    component: NfcMultilineChartField,
    supportedTypes: ["char", "text"],
});

const style = document.createElement("style");
style.textContent = `
.nfc-multiline-chart-field { width: 100%; overflow-x: auto; }
.nfc-mlc-svg { width: 100%; max-width: 100%; height: auto; min-height: 180px; display: block; }
`;
document.head.appendChild(style);

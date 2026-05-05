/** @odoo-module **/
import { Component, xml, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const COLORS = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];

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

/** Nhãn trục X từ YYYY-MM — ví dụ 2026-05 → "05/26" */
function formatXCategory(cat) {
    const s = String(cat);
    const m = s.match(/^(\d{4})-(\d{2})/);
    if (!m) return s;
    const mo = m[2];
    const yy = m[1].slice(2);
    return `${mo}/${yy}`;
}

function formatVnd(n) {
    if (n == null || Number.isNaN(n)) return "—";
    return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(Math.round(n))} đ`;
}

function compactVndAxis(n) {
    const r = Math.round(n);
    if (Math.abs(r) >= 1_000_000) {
        return `${(r / 1_000_000).toFixed(r % 1_000_000 === 0 ? 0 : 1)}M`;
    }
    if (Math.abs(r) >= 1_000) {
        return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(r)}`;
    }
    return String(r);
}

export class NfcMultilineChartField extends Component {
    static template = xml`
        <div class="nfc-multiline-chart-field">
            <div t-if="!chart" class="text-muted small py-2">Chưa đủ dữ liệu nhiều NCC để vẽ biểu đồ theo tháng.</div>
            <div t-else="" class="nfc-mlc-card">
                <div class="nfc-mlc-head">
                    <h6 class="nfc-mlc-title" t-esc="chart.title"/>
                    <div class="nfc-mlc-legend">
                        <t t-foreach="chart.legendItems" t-as="lg" t-key="lg_index">
                            <span class="nfc-mlc-chip" t-att-title="lg.name">
                                <span class="nfc-mlc-swatch" t-att-style="'background-color:' + lg.color"/>
                                <span class="nfc-mlc-chip-name" t-esc="lg.name"/>
                            </span>
                        </t>
                    </div>
                </div>
                <div class="nfc-mlc-plot" t-ref="plotWrap">
                    <div
                        t-if="state.hoverIdx !== null and state.tipLines?.length"
                        class="nfc-mlc-tooltip"
                        t-att-style="tooltipStyle"
                    >
                        <div class="nfc-mlc-tip-m" t-esc="state.tipTitle"/>
                        <t t-foreach="state.tipLines" t-as="line" t-key="line_index">
                            <div class="nfc-mlc-tip-row" t-esc="line"/>
                        </t>
                    </div>
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        t-att-viewBox="chart.viewBox"
                        class="nfc-mlc-svg"
                        preserveAspectRatio="xMidYMid meet"
                        t-on-mousemove="onSvgMouseMove"
                        t-on-mouseleave="onSvgMouseLeave"
                    >
                        <defs>
                            <linearGradient t-att-id="chart.gradientId" x1="0" x2="0" y1="0" y2="1">
                                <stop offset="0%" stop-color="var(--nfc-mlc-grid-a, currentColor)" stop-opacity="0.12"/>
                                <stop offset="100%" stop-color="var(--nfc-mlc-grid-a, currentColor)" stop-opacity="0.02"/>
                            </linearGradient>
                        </defs>
                        <rect
                            t-att-x="chart.plot.x0"
                            t-att-y="chart.plot.y0"
                            t-att-width="chart.plot.w"
                            t-att-height="chart.plot.h"
                            t-att-fill="'url(#' + chart.gradientId + ')'"
                            class="nfc-mlc-plot-bg"
                        />
                        <t t-foreach="chart.gridLines" t-as="g" t-key="g_index">
                            <line
                                class="nfc-mlc-grid"
                                t-att-x1="chart.plot.x0"
                                t-att-x2="chart.plot.x1"
                                t-att-y1="g.y"
                                t-att-y2="g.y"
                            />
                        </t>
                        <t t-foreach="chart.yTicks" t-as="tk" t-key="tk_index">
                            <text
                                class="nfc-mlc-ytick"
                                t-att-x="chart.plot.x0 - 6"
                                t-att-y="tk.y + 4"
                                text-anchor="end"
                                t-esc="tk.label"
                            />
                        </t>
                        <line
                            class="nfc-mlc-axis-y"
                            t-att-x1="chart.plot.x0"
                            t-att-y1="chart.plot.y0"
                            t-att-x2="chart.plot.x0"
                            t-att-y2="chart.plot.y1"
                        />
                        <line
                            class="nfc-mlc-axis-x"
                            t-att-x1="chart.plot.x0"
                            t-att-y1="chart.plot.y1"
                            t-att-x2="chart.plot.x1"
                            t-att-y2="chart.plot.y1"
                        />
                        <t t-if="state.crosshairX !== null">
                            <line
                                class="nfc-mlc-crosshair"
                                t-att-x1="state.crosshairX"
                                t-att-x2="state.crosshairX"
                                t-att-y1="chart.plot.y0"
                                t-att-y2="chart.plot.y1"
                            />
                        </t>
                        <t t-foreach="chart.paths" t-as="p" t-key="p_index">
                            <polyline
                                class="nfc-mlc-line"
                                fill="none"
                                t-att-stroke="p.color"
                                stroke-width="2.5"
                                stroke-linejoin="round"
                                stroke-linecap="round"
                                t-att-points="p.pointsStr"
                            />
                            <t t-foreach="p.dots" t-as="d" t-key="d_index">
                                <circle
                                    class="nfc-mlc-dot"
                                    t-att-cx="d.x"
                                    t-att-cy="d.y"
                                    r="4"
                                    t-att-fill="p.color"
                                    t-att-stroke="var(--nfc-mlc-dot-stroke, #fff)"
                                    stroke-width="1.5"
                                />
                            </t>
                        </t>
                        <t t-foreach="chart.xlabels" t-as="xl" t-key="xl_index">
                            <text
                                class="nfc-mlc-xlabel"
                                t-att-x="xl.x"
                                t-att-y="xl.y"
                                text-anchor="middle"
                                t-esc="xl.text"
                            />
                        </t>
                        <text
                            class="nfc-mlc-unit"
                            t-att-x="chart.plot.x1"
                            t-att-y="chart.plot.y0 - 4"
                            text-anchor="end"
                        >đ</text>
                    </svg>
                </div>
                <p class="nfc-mlc-subtitle" t-esc="chart.subtitle"/>
            </div>
        </div>
    `;
    static props = { ...standardFieldProps };

    setup() {
        this.plotWrapRef = useRef("plotWrap");
        this.state = useState({
            hoverIdx: null,
            crosshairX: null,
            tipTitle: "",
            tipLines: [],
            tipPx: 0,
            tipPy: 0,
        });
    }

    get chart() {
        const raw = this.props.record?.data?.[this.props.name];
        const data = parsePayload(raw);
        if (!data) return null;

        const cats = data.categories;
        const series = data.series || [];
        const W = 680;
        const H = 240;
        const pad = { t: 10, r: 20, b: 36, l: 56 };
        const innerW = W - pad.l - pad.r;
        const innerH = H - pad.t - pad.b;
        const plot = { x0: pad.l, y0: pad.t, x1: pad.l + innerW, y1: pad.t + innerH, w: innerW, h: innerH };

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
            maxY = Number.isFinite(maxY) && maxY !== 0 ? maxY : 1;
        }
        const yPad = (maxY - minY) * 0.1 || 1;
        minY -= yPad;
        maxY += yPad;

        const xScale = (i) =>
            pad.l + (cats.length <= 1 ? innerW / 2 : (i / (cats.length - 1)) * innerW);
        const yScale = (v) => pad.t + innerH - ((v - minY) / (maxY - minY)) * innerH;

        const tickCount = 4;
        const yTicks = [];
        const gridLines = [];
        for (let ti = 0; ti <= tickCount; ti++) {
            const val = minY + (ti / tickCount) * (maxY - minY);
            const y = yScale(val);
            if (ti > 0 && ti < tickCount) {
                gridLines.push({ y });
            }
            yTicks.push({ y, label: compactVndAxis(val) });
        }

        const paths = [];
        series.forEach((s, si) => {
            const color = COLORS[si % COLORS.length];
            const pts = [];
            const dots = [];
            (s.data || []).forEach((v, i) => {
                if (v == null || Number.isNaN(v)) return;
                const x = xScale(i);
                const yy = yScale(v);
                pts.push(`${x},${yy}`);
                dots.push({ x, y: yy, catIndex: i, value: v, seriesName: s.name, color });
            });
            if (!pts.length) return;
            paths.push({ color, pointsStr: pts.join(" "), dots });
        });
        if (!paths.length) return null;

        const xlabels = cats.map((c, i) => ({
            x: xScale(i),
            y: H - 10,
            text: formatXCategory(c),
        }));

        const legendItems = series.slice(0, 6).map((s, i) => ({
            name: s.name || `NCC ${i + 1}`,
            color: COLORS[i % COLORS.length],
        }));

        const rid = this.props.record?.resId ?? "0";
        const fname = this.props.name ?? "f";
        const gradientId = `nfc-mlc-g-${rid}-${fname}`.replace(/[^a-zA-Z0-9_-]/g, "");

        return {
            title: data.title || "Giá TB theo tháng (đơn vị: đ)",
            subtitle: data.subtitle || "",
            viewBox: `0 0 ${W} ${H}`,
            plot,
            gridLines,
            yTicks,
            paths,
            xlabels,
            legendItems,
            gradientId,
            cats,
            series,
            innerW,
            pad,
            xScale,
            minY,
            maxY,
            W,
            H,
        };
    }

    get tooltipStyle() {
        const { tipPx, tipPy } = this.state;
        return `left:${tipPx}px;top:${tipPy}px;`;
    }

    onSvgMouseLeave() {
        this.state.hoverIdx = null;
        this.state.crosshairX = null;
        this.state.tipTitle = "";
        this.state.tipLines = [];
    }

    onSvgMouseMove(ev) {
        const model = this.chart;
        if (!model) return;

        const svg = ev.currentTarget;
        const ctm = svg.getScreenCTM();
        if (!ctm) return;
        const pt = svg.createSVGPoint();
        pt.x = ev.clientX;
        pt.y = ev.clientY;
        const p = pt.matrixTransform(ctm.inverse());
        const mx = p.x;

        const { cats, pad, innerW, series, xScale } = model;
        let idx = 0;
        if (cats.length <= 1) {
            idx = 0;
        } else {
            const margins = [];
            for (let i = 0; i < cats.length; i++) {
                const xi = xScale(i);
                let left;
                let right;
                if (i === 0) {
                    left = pad.l - 1e6;
                    right = (xi + xScale(1)) / 2;
                } else if (i === cats.length - 1) {
                    left = (xScale(i - 1) + xi) / 2;
                    right = pad.l + innerW + 1e6;
                } else {
                    left = (xScale(i - 1) + xi) / 2;
                    right = (xi + xScale(i + 1)) / 2;
                }
                margins.push({ i, left, right });
            }
            const hit = margins.find((m) => mx >= m.left && mx < m.right);
            idx = hit ? hit.i : Math.max(0, Math.min(cats.length - 1, Math.round(((mx - pad.l) / innerW) * (cats.length - 1))));
        }

        const catLabel = formatXCategory(cats[idx]);
        const lines = [];
        for (const s of series) {
            const v = s.data?.[idx];
            if (v == null || Number.isNaN(v)) continue;
            const name = s.name || "";
            lines.push(`${name}: ${formatVnd(v)}`);
        }

        this.state.hoverIdx = idx;
        this.state.crosshairX = xScale(idx);
        this.state.tipTitle = `Kỳ ${catLabel}`;
        this.state.tipLines = lines;

        const wrap = this.plotWrapRef.el;
        if (wrap) {
            const rect = wrap.getBoundingClientRect();
            const px = ev.clientX - rect.left + 12;
            const py = ev.clientY - rect.top + 8;
            const tw = 280;
            const th = 24 + lines.length * 18;
            let lx = px;
            let ly = py;
            if (lx + tw > rect.width - 8) lx = ev.clientX - rect.left - tw - 12;
            if (ly + th > rect.height - 8) ly = ev.clientY - rect.top - th - 8;
            this.state.tipPx = Math.max(4, lx);
            this.state.tipPy = Math.max(4, ly);
        }
    }
}

registry.category("fields").add("nfc_multiline_chart", {
    component: NfcMultilineChartField,
    supportedTypes: ["char", "text"],
});

const style = document.createElement("style");
style.textContent = `
.nfc-multiline-chart-field { width: 100%; max-width: 100%; }
.nfc-mlc-card {
  border: 1px solid var(--border-color, #dee2e6);
  border-radius: 8px;
  background: var(--nfc-mlc-card-bg, var(--o-view-background-color, #fff));
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
  padding: 12px 14px 10px;
  color: var(--body-color, #212529);
}
.nfc-mlc-head { margin-bottom: 8px; }
.nfc-mlc-title {
  font-size: 0.9375rem;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.35;
  color: var(--body-color, #212529);
}
.nfc-mlc-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: flex-start;
}
.nfc-mlc-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  font-size: 0.75rem;
  line-height: 1.3;
  color: var(--body-color, #374151);
}
.nfc-mlc-swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}
.nfc-mlc-chip-name {
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-word;
}
.nfc-mlc-plot { position: relative; width: 100%; }
.nfc-mlc-svg {
  width: 100%;
  max-width: 100%;
  height: auto;
  min-height: 220px;
  display: block;
  color: var(--body-color, #495057);
}
.nfc-mlc-grid {
  stroke: currentColor;
  stroke-opacity: 0.15;
  stroke-width: 1;
  stroke-dasharray: 4 4;
}
.nfc-mlc-axis-x, .nfc-mlc-axis-y {
  stroke: currentColor;
  stroke-opacity: 0.35;
  stroke-width: 1;
}
.nfc-mlc-crosshair {
  stroke: currentColor;
  stroke-opacity: 0.25;
  stroke-width: 1;
  pointer-events: none;
}
.nfc-mlc-ytick {
  font-size: 10px;
  fill: currentColor;
  fill-opacity: 0.75;
  pointer-events: none;
}
.nfc-mlc-xlabel {
  font-size: 11px;
  fill: currentColor;
  fill-opacity: 0.8;
  font-weight: 500;
  pointer-events: none;
}
.nfc-mlc-unit {
  font-size: 10px;
  fill: currentColor;
  fill-opacity: 0.55;
  pointer-events: none;
}
.nfc-mlc-subtitle {
  font-size: 0.72rem;
  color: var(--text-muted, #6c757d);
  margin: 10px 0 0 0;
  line-height: 1.45;
}
.nfc-mlc-tooltip {
  position: absolute;
  z-index: 10;
  min-width: 180px;
  max-width: min(360px, 92vw);
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  line-height: 1.45;
  pointer-events: none;
  background: var(--nfc-mlc-tip-bg, rgba(33, 37, 41, 0.94));
  color: var(--nfc-mlc-tip-fg, #fff);
  box-shadow: 0 4px 16px rgba(0,0,0,.18);
  border: 1px solid rgba(255,255,255,.08);
}
.nfc-mlc-tip-m {
  font-weight: 600;
  margin-bottom: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255,255,255,.15);
}
.nfc-mlc-tip-row { opacity: 0.95; word-break: break-word; }

@media (prefers-color-scheme: dark) {
  html:not([data-color-scheme="light"]) .nfc-mlc-card {
    --nfc-mlc-card-bg: var(--o-view-background-color, #1e1e1e);
    --nfc-mlc-dot-stroke: #2d2d2d;
    --nfc-mlc-tip-bg: rgba(30, 30, 30, 0.96);
    --nfc-mlc-tip-fg: #f8f9fa;
    box-shadow: 0 1px 3px rgba(0,0,0,.3);
  }
}
`;
document.head.appendChild(style);

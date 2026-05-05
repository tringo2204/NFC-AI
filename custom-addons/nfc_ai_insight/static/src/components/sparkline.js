/** @odoo-module **/
/**
 * PriceSparkline — SVG mini chart lịch sử giá.
 * Không dùng Chart.js — thuần SVG, 0 dependency.
 */
import { Component } from "@odoo/owl";

export class PriceSparkline extends Component {
    static template = "nfc_ai_insight.PriceSparkline";
    static props = {
        data:          Array,    // [{date, price, supplier, qty}]
        currentPrice:  { type: Number, optional: true },
        width:         { type: Number, optional: true },
        height:        { type: Number, optional: true },
    };
    static defaultProps = { width: 320, height: 72 };

    get svgData() {
        const { data, currentPrice, width, height } = this.props;
        if (!data || data.length < 2) return null;

        // Sắp xếp theo ngày tăng dần
        const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
        const prices = sorted.map(d => d.price);
        const minP   = Math.min(...prices) * 0.97;
        const maxP   = Math.max(...prices) * 1.03;
        const pad    = { top: 8, right: 16, bottom: 20, left: 4 };
        const W = width  - pad.left - pad.right;
        const H = height - pad.top  - pad.bottom;

        const xScale = i => pad.left + (i / (sorted.length - 1)) * W;
        const yScale = p => pad.top  + H - ((p - minP) / (maxP - minP)) * H;

        // Polyline points
        const points = sorted.map((d, i) => `${xScale(i)},${yScale(d.price)}`).join(" ");

        // Area fill path
        const areaPath = [
            `M ${xScale(0)},${yScale(sorted[0].price)}`,
            ...sorted.map((d, i) => `L ${xScale(i)},${yScale(d.price)}`),
            `L ${xScale(sorted.length - 1)},${pad.top + H}`,
            `L ${xScale(0)},${pad.top + H}`,
            "Z",
        ].join(" ");

        // Current price line (horizontal dashed)
        const currentY = currentPrice ? yScale(currentPrice) : null;

        // X-axis labels (first + last date)
        const firstLabel = sorted[0].date.slice(0, 7);
        const lastLabel  = sorted[sorted.length - 1].date.slice(0, 7);

        // Dots for each point
        const dots = sorted.map((d, i) => ({
            cx: xScale(i), cy: yScale(d.price),
            price: d.price, date: d.date,
        }));

        return { points, areaPath, currentY, firstLabel, lastLabel, dots, H, pad, W, yScale, minP, maxP };
    }

    fmt(num) {
        if (!num) return "";
        return (num / 1000).toFixed(0) + "k";
    }
}

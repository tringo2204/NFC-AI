/** @odoo-module **/
import { Component, useState, onWillUpdateProps, onMounted, useRef, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { MonetaryField } from "@web/views/fields/monetary/monetary_field";
import { FloatField } from "@web/views/fields/float/float_field";
import { PriceSparkline } from "./sparkline";

// ── Popover Panel (render ngoài table qua Odoo Popover system) ─────────────
class InsightPanel extends Component {
    static template  = "nfc_ai_insight.InsightPanel";
    static components = { PriceSparkline };
    static props = {
        decision:   Object,
        logId:      { type: [Number, Boolean], optional: true },
        onFeedback: { type: Function, optional: true },
        close:      Function,
    };
    setup() {
        this.state = useState({ tab: "overview" }); // overview | chart | suppliers
    }
    setTab = (tab) => { this.state.tab = tab; }

    levelLabel(level) {
        return { good:"Tốt", normal:"Bình thường", high:"Cảnh báo", critical:"Cần xem lại", no_data:"Chưa có data" }[level] || level;
    }
    confidenceLabel(c) {
        return { high:"Cao", medium:"Trung bình", low:"Thấp" }[c] || c;
    }
    fmt(num) {
        if (num == null) return "";
        return Math.round(num).toLocaleString("vi-VN");
    }
    // Arrow function — giữ đúng `this` khi gọi từ OWL template
    feedback = async (action) => {
        this.props.onFeedback?.(action);
        this.props.close();
    }
}

// ── InsightBadge: badge nhỏ, click mở Popover ─────────────────────────────
class InsightBadge extends Component {
    static template = "nfc_ai_insight.InsightBadge";
    static props = {
        decision: { type: Object, optional: true },
        loading:  Boolean,
        logId:    { type: [Number, Boolean], optional: true },
        onFeedback: { type: Function, optional: true },
    };

    setup() {
        this.badgeRef = useRef("badge");
        this.popover  = usePopover(InsightPanel, { position: "bottom-start", closeOnClickAway: true });
    }

    openPanel = () => {
        if (!this.props.decision) return;
        this.popover.open(this.badgeRef.el, {
            decision:   this.props.decision,
            logId:      this.props.logId,
            onFeedback: this.props.onFeedback,
        });
    }

    levelIcon(level) {
        return { good:"fa-check-circle", normal:"fa-info-circle", high:"fa-exclamation-triangle", critical:"fa-times-circle", no_data:"fa-question-circle" }[level] || "fa-circle";
    }
    levelLabel(level) {
        return { good:"Tốt", normal:"Bình thường", high:"Cảnh báo", critical:"Cần xem lại", no_data:"Chưa có data" }[level] || level;
    }
    formatDev(pct) {
        if (pct == null) return "";
        return (pct > 0 ? "+" : "") + Math.round(pct) + "%";
    }
}

// ── Main field widget ──────────────────────────────────────────────────────
export class NfcAiInsightField extends Component {
    static template   = "nfc_ai_insight.InsightField";
    static components = { MonetaryField, FloatField, InsightBadge };
    static props      = { ...standardFieldProps };

    setup() {
        this.aiService  = useService("nfc_ai_insight");
        this.state      = useState({ loading: false, decision: null, logId: null });
        this._lastValue = null;

        onMounted(() => this._fetch());
        onWillUpdateProps((next) => {
            const v = next.record?.data?.[next.name];
            if (v !== this._lastValue) { this._lastValue = v; this._fetch(next); }
        });
    }

    _fetch(props = this.props) {
        const value    = props.record?.data?.[props.name];
        const recordId = props.record?.resId;
        if (!value || !recordId) return;
        this.state.loading  = true;
        this.state.decision = null;
        this.aiService.requestInsight(
            { model: props.record.resModel, record_id: recordId, field: props.name, value,
              context: { company_id: props.record.context?.allowed_company_ids?.[0] || 1,
                         user_id:    props.record.context?.uid || 0 } },
            (decision, log_id) => {
                this.state.loading  = false;
                this.state.decision = decision;
                this.state.logId    = log_id;
            }
        );
    }

    onFeedback = async (action) => {
        await this.aiService.sendFeedback(this.state.logId, action);
        this.state.decision = null;
    }

    get isMonetary() { return !!this.props.record?.data?.currency_id; }
}

registry.category("fields").add("nfc_ai_insight", {
    component: NfcAiInsightField,
    supportedTypes: ["float", "monetary", "integer"],
});

// ── CSS ─────────────────────────────────────────────────────────────────────
const style = document.createElement("style");
style.textContent = `
.nfc-ai-field-wrap { display:flex; align-items:center; gap:6px; width:100%; }
.nfc-ai-field-wrap .o_field_widget { flex:1; min-width:0; }

.nfc-ai-badge {
  display:inline-flex; align-items:center; gap:3px;
  padding:1px 8px; border-radius:10px; font-size:11px; font-weight:600;
  cursor:pointer; white-space:nowrap; flex-shrink:0; border:none; background:none;
}
.nfc-ai-badge--good     { background:#d1f5d3; color:#155724; }
.nfc-ai-badge--normal   { background:#d1ecf1; color:#0c5460; }
.nfc-ai-badge--high     { background:#fff3cd; color:#856404; }
.nfc-ai-badge--critical { background:#f8d7da; color:#721c24; }
.nfc-ai-badge--no_data  { background:#e9ecef; color:#6c757d; }
.nfc-ai-badge--loading  { background:#e9ecef; color:#6c757d; }
.nfc-ai-deviation       { font-weight:400; opacity:.75; }

/* Popover panel */
.nfc-ai-panel-wrap { min-width:320px; max-width:380px; font-size:13px; }
.nfc-ai-panel-header {
  display:flex; justify-content:space-between; align-items:center;
  padding:8px 12px; border-bottom:1px solid #dee2e6;
  background:#f8f9fa; border-radius:6px 6px 0 0; font-weight:700; font-size:12px;
}
.nfc-ai-panel-body { padding:10px 12px; }
.nfc-ai-msg  { font-size:13px; font-weight:500; margin-bottom:4px; }
.nfc-ai-sugg { font-size:12px; color:#495057; margin-bottom:8px; }

.nfc-ai-stats-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:5px; margin:8px 0; }
.nfc-ai-stat { text-align:center; padding:4px 6px; background:#f8f9fa; border-radius:6px; border:1px solid #e9ecef; }
.nfc-ai-stat--highlight { background:#fff3cd; border-color:#ffc107; }
.nfc-ai-stat-label { display:block; font-size:10px; color:#6c757d; }
.nfc-ai-stat-value { display:block; font-size:12px; font-weight:700; }

.nfc-ai-best-supplier {
  font-size:12px; padding:5px 8px; background:#f0fdf4;
  border:1px solid #bbf7d0; border-radius:5px; margin:6px 0;
}
.nfc-ai-history-title { font-size:11px; color:#6c757d; font-weight:600; margin:8px 0 3px; }
.nfc-ai-history-table { width:100%; border-collapse:collapse; font-size:11px; }
.nfc-ai-history-table tr { border-bottom:1px solid #f0f0f0; }
.nfc-ai-history-table td { padding:3px 4px; }
.nfc-ai-history-date     { color:#6c757d; width:80px; }
.nfc-ai-history-supplier { color:#495057; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.nfc-ai-history-price    { text-align:right; white-space:nowrap; }
.nfc-ai-meta { font-size:11px; color:#6c757d; display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; padding-top:6px; border-top:1px solid #f0f0f0; }
.nfc-ai-panel-footer { display:flex; gap:6px; padding:8px 12px; border-top:1px solid #dee2e6; background:#f8f9fa; border-radius:0 0 6px 6px; }

/* Header meta */
.nfc-ai-meta-inline { display:flex; gap:6px; align-items:center; font-size:11px; color:#6c757d; }
.nfc-ai-cache-pill  { background:#dbeafe; color:#1d4ed8; padding:1px 5px; border-radius:4px; font-size:10px; }

/* Tabs */
.nfc-ai-tabs { display:flex; gap:2px; padding:4px 12px 0; border-bottom:1px solid #dee2e6; background:#f8f9fa; }
.nfc-ai-tab  {
  padding:4px 10px; font-size:11px; font-weight:500; border:none; background:none;
  border-bottom:2px solid transparent; cursor:pointer; color:#6c757d;
}
.nfc-ai-tab.active { color:#0d6efd; border-bottom-color:#0d6efd; }
.nfc-ai-tab:hover:not(.active) { color:#495057; }

/* Supplier table */
.nfc-ai-supplier-table { width:100%; border-collapse:collapse; font-size:11px; }
.nfc-ai-supplier-table th { padding:4px; color:#6c757d; font-weight:600; border-bottom:1px solid #dee2e6; text-align:left; }
.nfc-ai-supplier-table td { padding:4px; border-bottom:1px solid #f0f0f0; }
.nfc-ai-best-row { background:#f0fdf4; }

/* Chart */
.nfc-ai-chart-title { font-size:11px; font-weight:600; color:#6c757d; margin-bottom:6px; }
.nfc-ai-chart-legend { display:flex; gap:12px; font-size:10px; color:#9ca3af; margin-top:4px; align-items:center; }
.nfc-ai-legend-line { display:inline-block; width:20px; height:2px; background:#3b82f6; border-radius:1px; }
.nfc-ai-legend-dash { display:inline-block; width:20px; height:2px; background:#ef4444; border-radius:1px; }
.nfc-ai-sparkline-wrap { margin:4px 0; }
.nfc-ai-sparkline-empty { font-size:11px; color:#9ca3af; text-align:center; padding:12px; }

/* Decision Panel trên RFQ form */
.nfc-ai-decision-panel {
  margin: 0 0 12px; padding: 10px 14px;
  background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%);
  border: 1px solid #bfdbfe; border-radius: 8px;
  display: flex; align-items: flex-start; gap: 12px;
}
.nfc-ai-decision-panel-header {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: #1e40af; flex-shrink: 0;
}
.nfc-ai-decision-panel-hint { font-size: 11px; color: #6b7280; font-weight: 400; }
.nfc-ai-decision-panel-body {
  display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #374151;
}
.nfc-ai-dp-item { display: flex; align-items: center; gap: 4px; }
`;
document.head.appendChild(style);

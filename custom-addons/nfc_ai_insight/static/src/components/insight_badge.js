/** @odoo-module **/
/**
 * NFC AI InsightBadge — Sprint 3 approach (canvas design):
 *
 * Dùng patch() để override MonetaryField/FloatField rendering.
 * Widget KHÔNG thay thế field — nó WRAP field gốc, thêm badge AI bên cạnh.
 *
 * Cách dùng trong XML view:
 *   <field name="price_unit" widget="nfc_ai_insight"/>
 *
 * Widget tự đọc: model, record_id, field name, value → gọi AI API.
 */
import { Component, useState, onWillUpdateProps, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { MonetaryField } from "@web/views/fields/monetary/monetary_field";
import { FloatField } from "@web/views/fields/float/float_field";

// ── AI Badge UI Component ──────────────────────────────────────────────────
class AiBadge extends Component {
    static template = "nfc_ai_insight.AiBadge";
    static props = {
        decision: { type: Object, optional: true },
        loading:  { type: Boolean },
        logId:    { type: [Number, Boolean], optional: true },
        onFeedback: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ open: false });
    }

    toggle() { this.state.open = !this.state.open; }

    levelIcon(level) {
        return {
            good:     "fa-check-circle",
            normal:   "fa-info-circle",
            high:     "fa-exclamation-triangle",
            critical: "fa-times-circle",
            no_data:  "fa-question-circle",
        }[level] || "fa-circle";
    }
    levelLabel(level) {
        return { good:"Tốt", normal:"Bình thường", high:"Cảnh báo", critical:"Cần xem lại", no_data:"Chưa có data" }[level] || level;
    }
    confidenceLabel(c) {
        return { high:"Cao", medium:"Trung bình", low:"Thấp" }[c] || c;
    }
    formatDev(pct) {
        if (pct == null) return "";
        return (pct > 0 ? "+" : "") + Math.round(pct) + "%";
    }
}

// ── Main field widget: wraps MonetaryField + thêm AiBadge ─────────────────
export class NfcAiInsightField extends Component {
    static template  = "nfc_ai_insight.InsightField";
    static components = { MonetaryField, FloatField, AiBadge };
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.aiService = useService("nfc_ai_insight");
        this.state = useState({
            loading:  false,
            decision: null,
            logId:    null,
        });
        this._lastValue = null;

        // Fetch khi mount
        onMounted(() => this._fetchInsight());

        // Fetch khi value thay đổi
        onWillUpdateProps((nextProps) => {
            const nextVal = nextProps.record?.data?.[nextProps.name];
            if (nextVal !== this._lastValue) {
                this._lastValue = nextVal;
                this._fetchInsight(nextProps);
            }
        });
    }

    _fetchInsight(props = this.props) {
        const value    = props.record?.data?.[props.name];
        const recordId = props.record?.resId;
        if (!value || !recordId) return;

        const model   = props.record.resModel;
        const field   = props.name;
        const context = {
            company_id: props.record.context?.allowed_company_ids?.[0] || 1,
            user_id:    props.record.context?.uid || 0,
        };

        this.state.loading  = true;
        this.state.decision = null;

        this.aiService.requestInsight(
            { model, record_id: recordId, field, value, context },
            (decision, log_id) => {
                this.state.loading  = false;
                this.state.decision = decision;
                this.state.logId    = log_id;
            }
        );
    }

    async onFeedback(action) {
        await this.aiService.sendFeedback(this.state.logId, action);
        this.state.decision = null; // reset sau khi feedback
    }

    /** Dùng MonetaryField nếu có currency, FloatField nếu không */
    get isMonetary() {
        return !!this.props.record?.data?.currency_id;
    }
}

// ── Đăng ký widget ──────────────────────────────────────────────────────────
registry.category("fields").add("nfc_ai_insight", {
    component: NfcAiInsightField,
    supportedTypes: ["float", "monetary", "integer"],
    extractProps: ({ attrs, field }) => ({
        digits: attrs.digits && JSON.parse(attrs.digits),
        inputType: attrs.options?.input_type ?? "number",
    }),
});

// ── CSS ─────────────────────────────────────────────────────────────────────
const style = document.createElement("style");
style.textContent = `
.nfc-ai-field-wrap {
  display: flex; align-items: center; gap: 6px; width: 100%;
}
.nfc-ai-field-wrap .o_field_widget { flex: 1; min-width: 0; }

.nfc-ai-badge {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 1px 7px; border-radius: 10px; font-size: 11px; font-weight: 600;
  cursor: pointer; white-space: nowrap; flex-shrink: 0;
  border: none; background: none;
}
.nfc-ai-badge--good     { background:#d1f5d3; color:#155724; }
.nfc-ai-badge--normal   { background:#d1ecf1; color:#0c5460; }
.nfc-ai-badge--high     { background:#fff3cd; color:#856404; }
.nfc-ai-badge--critical { background:#f8d7da; color:#721c24; }
.nfc-ai-badge--no_data  { background:#e9ecef; color:#6c757d; }
.nfc-ai-badge--loading  { background:#e9ecef; color:#6c757d; }
.nfc-ai-deviation { font-weight:400; opacity:.75; }

.nfc-ai-panel {
  position: absolute; z-index: 1050; min-width: 300px; max-width: 360px;
  background: #fff; border:1px solid #dee2e6; border-radius:8px;
  box-shadow: 0 6px 20px rgba(0,0,0,.13);
  top: calc(100% + 4px); left: 0;
}
.nfc-ai-panel-header {
  display:flex; justify-content:space-between; align-items:center;
  padding: 8px 12px; border-bottom:1px solid #dee2e6;
  background:#f8f9fa; border-radius:8px 8px 0 0; font-weight:700; font-size:12px;
}
.nfc-ai-panel-body { padding:10px 12px; }
.nfc-ai-msg   { font-size:13px; font-weight:500; margin-bottom:4px; }
.nfc-ai-sugg  { font-size:12px; color:#495057; margin-bottom:6px; }
.nfc-ai-meta  { font-size:11px; color:#6c757d; display:flex; gap:10px; flex-wrap:wrap; }
.nfc-ai-panel-footer {
  display:flex; gap:6px; padding:8px 12px;
  border-top:1px solid #dee2e6; background:#f8f9fa; border-radius:0 0 8px 8px;
}
.nfc-ai-wrap-relative { position: relative; display:inline-block; }
`;
document.head.appendChild(style);

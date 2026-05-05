/** @odoo-module **/
/**
 * InsightBadge — OWL 2 component.
 * Gắn vào bất kỳ field nào qua widget="nfc_ai_insight".
 *
 * Props:
 *   - model      : Odoo model name (vd: "purchase.order.line")
 *   - recordId   : ID của record
 *   - field      : tên field đang theo dõi (vd: "price_unit")
 *   - value      : giá trị hiện tại của field
 *   - context    : dict context (company_id, user_id, ...)
 */
import { Component, useState, useEffect, useService } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class InsightBadge extends Component {
    static template = "nfc_ai_insight.InsightBadge";
    static props = {
        ...standardFieldProps,
        aiModel:   { type: String, optional: true },
        aiField:   { type: String, optional: true },
    };

    setup() {
        this.aiService = useService("nfc_ai_insight");
        this.state = useState({
            visible:    false,
            loading:    false,
            decision:   null,
            panelOpen:  false,
            logId:      null,
        });

        useEffect(
            () => {
                const value = this.props.record.data[this.props.name];
                const recordId = this.props.record.resId;
                if (!value || !recordId) return;

                const model   = this.props.aiModel || this.props.record.resModel;
                const field   = this.props.aiField  || this.props.name;
                const context = {
                    company_id: this.props.record.context?.allowed_company_ids?.[0] || 1,
                    user_id:    this.props.record.context?.uid || 0,
                };

                this.state.visible = true;
                this.state.loading = true;
                this.state.decision = null;

                this.aiService.requestInsight(
                    { model, record_id: recordId, field, value, context },
                    (decision, log_id) => {
                        this.state.loading  = false;
                        this.state.decision = decision;
                        this.state.logId    = log_id;
                    }
                );
            },
            () => [this.props.record.data[this.props.name], this.props.record.resId]
        );
    }

    togglePanel() {
        this.state.panelOpen = !this.state.panelOpen;
    }

    async sendFeedback(action) {
        await this.aiService.sendFeedback(this.state.logId, action);
        this.state.panelOpen = false;
    }

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
        return {
            good:     "Tốt",
            normal:   "Bình thường",
            high:     "Cảnh báo",
            critical: "Nghiêm trọng",
            no_data:  "Chưa có data",
        }[level] || level;
    }

    confidenceLabel(confidence) {
        return { high: "Cao", medium: "Trung bình", low: "Thấp" }[confidence] || confidence;
    }

    formatDeviation(pct) {
        if (pct === null || pct === undefined) return "";
        const sign = pct > 0 ? "+" : "";
        return `${sign}${Math.round(pct)}%`;
    }
}

// Đăng ký field widget — dùng widget="nfc_ai_insight" trong XML view
registry.category("fields").add("nfc_ai_insight", {
    component: InsightBadge,
    supportedTypes: ["float", "monetary", "integer"],
});

// CSS inline (không cần file SCSS riêng)
const style = document.createElement("style");
style.textContent = `
.nfc-ai-badge-wrap { display: inline-flex; align-items: center; gap: 4px; position: relative; }

.nfc-ai-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
  cursor: pointer; user-select: none; white-space: nowrap;
}
.nfc-ai-badge--good     { background: #d4edda; color: #155724; }
.nfc-ai-badge--normal   { background: #d1ecf1; color: #0c5460; }
.nfc-ai-badge--high     { background: #fff3cd; color: #856404; }
.nfc-ai-badge--critical { background: #f8d7da; color: #721c24; }
.nfc-ai-badge--no_data  { background: #e2e3e5; color: #383d41; }
.nfc-ai-badge--loading  { background: #e2e3e5; color: #6c757d; }
.nfc-ai-deviation { font-weight: 400; opacity: 0.8; margin-left: 2px; }

.nfc-ai-panel {
  position: absolute; top: calc(100% + 4px); left: 0; z-index: 1000;
  background: #fff; border: 1px solid #dee2e6; border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,.12); min-width: 300px; max-width: 380px;
}
.nfc-ai-panel__header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; border-bottom: 1px solid #dee2e6;
  background: #f8f9fa; border-radius: 6px 6px 0 0;
}
.nfc-ai-panel__title { font-weight: 700; font-size: 12px; color: #495057; }
.nfc-ai-panel__close  { cursor: pointer; color: #6c757d; }
.nfc-ai-panel__body   { padding: 10px 12px; }
.nfc-ai-panel__message    { font-size: 13px; margin-bottom: 6px; font-weight: 500; }
.nfc-ai-panel__suggestion { font-size: 12px; color: #495057; margin-bottom: 6px; }
.nfc-ai-panel__meta {
  display: flex; gap: 12px; font-size: 11px; color: #6c757d;
  margin-top: 8px; padding-top: 6px; border-top: 1px solid #f0f0f0;
}
.nfc-ai-cache-badge { background: #e7f3ff; color: #0056b3; padding: 0 4px; border-radius: 4px; }
.nfc-ai-panel__actions {
  display: flex; gap: 6px; padding: 8px 12px;
  border-top: 1px solid #dee2e6; background: #f8f9fa; border-radius: 0 0 6px 6px;
}
`;
document.head.appendChild(style);

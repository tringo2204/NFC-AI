/** @odoo-module **/
/**
 * AI Service — giao tiếp với NFC AI backend.
 * Singleton service, inject vào bất kỳ component nào cần.
 */
import { registry } from "@web/core/registry";
import { session } from "@web/session";

const AI_API_URL = session.nfc_ai_url || "http://localhost:8100";
const DEBOUNCE_MS = 600;

class AiInsightService {
    constructor() {
        this._timers = new Map();   // debounce timers per field key
        this._cache  = new Map();   // in-memory cache per (model, record_id, field, value)
    }

    /**
     * Gửi ERPEvent đến AI backend (debounced).
     * @param {Object} event  - { model, record_id, field, value, context }
     * @param {Function} callback - fn(decision, log_id)
     */
    requestInsight(event, callback) {
        const key = `${event.model}:${event.record_id}:${event.field}`;

        // Clear timer cũ (debounce)
        if (this._timers.has(key)) {
            clearTimeout(this._timers.get(key));
        }

        const timer = setTimeout(async () => {
            this._timers.delete(key);
            const cacheKey = `${key}:${event.value}`;

            // In-memory cache (tab session)
            if (this._cache.has(cacheKey)) {
                const cached = this._cache.get(cacheKey);
                callback(cached.decision, cached.log_id);
                return;
            }

            try {
                const resp = await fetch(`${AI_API_URL}/api/insight`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(event),
                });
                if (!resp.ok) return;
                const data = await resp.json();
                this._cache.set(cacheKey, data);
                callback(data.decision, data.log_id);
            } catch (err) {
                // AI không available → fail silently, không block Odoo
                console.debug("[NFC AI] Service unavailable:", err.message);
            }
        }, DEBOUNCE_MS);

        this._timers.set(key, timer);
    }

    /**
     * Ghi lại user action sau khi user quyết định.
     * @param {number} log_id
     * @param {string} action  - accepted | ignored | overridden | negotiated
     * @param {string} outcome
     */
    async sendFeedback(log_id, action, outcome = "") {
        if (!log_id) return;
        try {
            await fetch(`${AI_API_URL}/api/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ log_id, user_action: action, outcome }),
            });
        } catch (err) {
            console.debug("[NFC AI] Feedback error:", err.message);
        }
    }
}

export const aiInsightService = {
    name: "nfc_ai_insight",
    start() {
        return new AiInsightService();
    },
};

registry.category("services").add("nfc_ai_insight", aiInsightService);

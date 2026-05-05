/** @odoo-module **/
/**
 * AI Service — giao tiếp với NFC AI backend.
 * Timeout + hủy request cũ cùng khóa để tránh treo tab / hàng loạt pending.
 */
import { registry } from "@web/core/registry";
import { session } from "@web/session";

const AI_API_URL = session.nfc_ai_url ||
    `${window.location.protocol}//${window.location.hostname}:8100`;
const DEBOUNCE_MS = 900;
/** Ngắt fetch sau N ms — tránh pending vô hạn (browser / OpenAI chậm) */
const FETCH_TIMEOUT_MS = 45000;

function fallbackDecision(message) {
    return {
        level: "no_data",
        message: message || "Không nhận được phản hồi từ AI.",
        confidence: "low",
        data_points: 0,
        actions: [],
        tools_used: [],
        cached: false,
    };
}

class AiInsightService {
    constructor() {
        this._timers = new Map();
        this._cache = new Map();
        /** @type {Map<string, AbortController>} */
        this._aborters = new Map();
    }

    /**
     * Gửi ERPEvent đến AI backend (debounced).
     * Luôn gọi callback (kể cả lỗi / timeout) để OWL tắt loading.
     */
    requestInsight(event, callback) {
        const key = `${event.model}:${event.record_id}:${event.field}`;

        if (this._timers.has(key)) {
            clearTimeout(this._timers.get(key));
        }

        const timer = setTimeout(async () => {
            this._timers.delete(key);
            const cacheKey = `${key}:${event.value}`;

            if (this._cache.has(cacheKey)) {
                const cached = this._cache.get(cacheKey);
                callback(cached.decision, cached.log_id);
                return;
            }

            const prev = this._aborters.get(cacheKey);
            if (prev) {
                prev.abort();
            }
            const ac = new AbortController();
            this._aborters.set(cacheKey, ac);
            const tmax = setTimeout(() => ac.abort(), FETCH_TIMEOUT_MS);

            try {
                const resp = await fetch(`${AI_API_URL}/api/insight`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(event),
                    signal: ac.signal,
                });
                if (!resp.ok) {
                    callback(
                        fallbackDecision(`AI HTTP ${resp.status}. Thử lại sau.`),
                        null
                    );
                    return;
                }
                const data = await resp.json();
                this._cache.set(cacheKey, data);
                callback(data.decision, data.log_id);
            } catch (err) {
                const msg =
                    err.name === "AbortError"
                        ? "Hết thời gian chờ AI (45s). Thử lại hoặc xem tab Tóm tắt BGĐ."
                        : `Lỗi mạng: ${err.message || err}`;
                console.debug("[NFC AI]", err);
                callback(fallbackDecision(msg), null);
            } finally {
                clearTimeout(tmax);
                this._aborters.delete(cacheKey);
            }
        }, DEBOUNCE_MS);

        this._timers.set(key, timer);
    }

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

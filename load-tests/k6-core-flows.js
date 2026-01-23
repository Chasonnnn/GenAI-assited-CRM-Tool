import http from "k6/http";
import { check, sleep, group } from "k6";

const BASE_URL = normalizeBaseUrl(__ENV.BASE_URL || "http://localhost:8000");
const AUTH_COOKIE_RAW = (__ENV.AUTH_COOKIE || "").trim();
const AUTH_COOKIE = buildCookieHeader(AUTH_COOKIE_RAW);
const CSRF_TOKEN =
    (__ENV.CSRF_TOKEN || "").trim() || parseCookieValue(AUTH_COOKIE, "crm_csrf");

const DEFAULT_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
};

const ENABLE_SEARCH = truthyEnv(__ENV.ENABLE_SEARCH ?? "1");
const ENABLE_WORKFLOWS = truthyEnv(__ENV.ENABLE_WORKFLOWS ?? "1");
const ENABLE_ANALYTICS = truthyEnv(__ENV.ENABLE_ANALYTICS ?? "1");
const ENABLE_MUTATIONS = truthyEnv(__ENV.ENABLE_MUTATIONS ?? "0");

const DURATION = __ENV.DURATION || "2m";
const VUS_SURROGATES = parseInt(__ENV.VUS_SURROGATES || "3", 10);
const VUS_TASKS = parseInt(__ENV.VUS_TASKS || "2", 10);
const VUS_DASHBOARD = parseInt(__ENV.VUS_DASHBOARD || "2", 10);
const VUS_AUTOMATION = parseInt(__ENV.VUS_AUTOMATION || "1", 10);
const VUS_MUTATIONS = parseInt(__ENV.VUS_MUTATIONS || "1", 10);

const ALLOW_FORBIDDEN = truthyEnv(__ENV.ALLOW_FORBIDDEN ?? "1");

function buildParams({ includeJson = false, includeCsrf = false, tags = {} } = {}) {
    const headers = { ...DEFAULT_HEADERS };
    if (AUTH_COOKIE) headers.Cookie = AUTH_COOKIE;
    if (includeJson) headers["Content-Type"] = "application/json";
    if (includeCsrf && CSRF_TOKEN) headers["X-CSRF-Token"] = CSRF_TOKEN;
    return { headers, tags };
}

export const options = {
    scenarios: {
        surrogates: {
            executor: "constant-vus",
            vus: VUS_SURROGATES,
            duration: DURATION,
            exec: "surrogatesFlow",
        },
        tasks: {
            executor: "constant-vus",
            vus: VUS_TASKS,
            duration: DURATION,
            exec: "tasksFlow",
        },
        dashboard: {
            executor: "constant-vus",
            vus: VUS_DASHBOARD,
            duration: DURATION,
            exec: "dashboardFlow",
        },
        ...(ENABLE_WORKFLOWS
            ? {
                  automation: {
                      executor: "constant-vus",
                      vus: VUS_AUTOMATION,
                      duration: DURATION,
                      exec: "automationFlow",
                  },
              }
            : {}),
        ...(ENABLE_SEARCH
            ? {
                  search: {
                      executor: "constant-vus",
                      // Keep this low by default; /search is rate-limited (30/min by default).
                      vus: 1,
                      duration: DURATION,
                      exec: "searchFlow",
                  },
              }
            : {}),
        ...(ENABLE_MUTATIONS
            ? {
                  mutations: {
                      executor: "constant-vus",
                      vus: VUS_MUTATIONS,
                      duration: DURATION,
                      exec: "mutationsFlow",
                  },
              }
            : {}),
    },
    thresholds: {
        http_req_failed: ["rate<0.01"],
        http_req_duration: ["p(95)<800"],
    },
};

export function surrogatesFlow() {
    const params = buildParams({ tags: { flow: "surrogates" } });

    group("surrogates:list", () => {
        const res = http.get(`${BASE_URL}/surrogates?per_page=20`, params);
        check(res, {
            "surrogates list 200": (r) => r.status === 200,
            "surrogates list json": (r) => !!safeJson(r),
        });

        const body = safeJson(res);
        const items = body?.items || [];
        if (!Array.isArray(items) || items.length === 0) return;

        // Pick a random surrogate for downstream reads.
        const pick = randomItem(items);
        if (!pick?.id) return;
        const id = String(pick.id);

        group("surrogates:detail", () => {
            const detail = http.get(`${BASE_URL}/surrogates/${id}`, params);
            check(detail, { "surrogate detail ok": (r) => r.status === 200 });
        });

        group("surrogates:notes", () => {
            const notes = http.get(`${BASE_URL}/surrogates/${id}/notes`, params);
            check(notes, {
                // Depending on permissions, notes may be forbidden; treat that as OK unless STRICT.
                "surrogate notes ok": (r) =>
                    r.status === 200 || (ALLOW_FORBIDDEN && r.status === 403),
            });
        });

        group("surrogates:journey", () => {
            const journey = http.get(`${BASE_URL}/journey/surrogates/${id}`, params);
            check(journey, { "surrogate journey ok": (r) => r.status === 200 });
        });
    });

    sleep(jitterSeconds(0.6, 1.4));
}

export function tasksFlow() {
    const params = buildParams({ tags: { flow: "tasks" } });

    const list = http.get(
        `${BASE_URL}/tasks?per_page=20&is_completed=false&exclude_approvals=true`,
        params
    );
    check(list, {
        "tasks list 200": (r) => r.status === 200,
        "tasks list json": (r) => !!safeJson(r),
    });

    const body = safeJson(list);
    const items = body?.items || [];
    if (Array.isArray(items) && items.length > 0) {
        const pick = randomItem(items);
        if (pick?.id) {
            const detail = http.get(`${BASE_URL}/tasks/${pick.id}`, params);
            check(detail, { "task detail ok": (r) => r.status === 200 });
        }
    }

    sleep(jitterSeconds(0.5, 1.2));
}

export function dashboardFlow() {
    const params = buildParams({ tags: { flow: "dashboard" } });

    // Simulate the dashboard initial load: multiple independent queries in parallel.
    const requests = {
        stats: ["GET", `${BASE_URL}/surrogates/stats`, null, params],
        tasks: [
            "GET",
            `${BASE_URL}/tasks?per_page=5&is_completed=false&exclude_approvals=true&my_tasks=true`,
            null,
            params,
        ],
        upcoming: ["GET", `${BASE_URL}/dashboard/upcoming?days=7&include_overdue=true`, null, params],
        attention: ["GET", `${BASE_URL}/dashboard/attention?days_unreached=7&days_stuck=30`, null, params],
    };

    if (ENABLE_ANALYTICS) {
        requests.analytics_summary = ["GET", `${BASE_URL}/analytics/summary`, null, params];
        requests.trend = ["GET", `${BASE_URL}/analytics/surrogates/trend?period=day`, null, params];
        requests.by_status = ["GET", `${BASE_URL}/analytics/surrogates/by-status`, null, params];
    }

    const res = http.batch(requests);

    check(res.stats, { "surrogates stats ok": (r) => r.status === 200 });
    check(res.tasks, { "dashboard tasks ok": (r) => r.status === 200 });
    check(res.upcoming, { "dashboard upcoming ok": (r) => r.status === 200 });
    check(res.attention, { "dashboard attention ok": (r) => r.status === 200 });

    if (ENABLE_ANALYTICS) {
        check(res.analytics_summary, {
            "analytics summary ok": (r) =>
                r.status === 200 || (ALLOW_FORBIDDEN && r.status === 403),
        });
        check(res.trend, {
            "analytics trend ok": (r) =>
                r.status === 200 || (ALLOW_FORBIDDEN && r.status === 403),
        });
        check(res.by_status, {
            "analytics by-status ok": (r) =>
                r.status === 200 || (ALLOW_FORBIDDEN && r.status === 403),
        });
    }

    sleep(jitterSeconds(0.7, 1.6));
}

export function automationFlow() {
    const params = buildParams({ tags: { flow: "automation" } });
    const workflows = http.get(`${BASE_URL}/workflows`, params);
    check(workflows, {
        "workflows list ok": (r) =>
            r.status === 200 || (ALLOW_FORBIDDEN && r.status === 403),
    });

    const stats = http.get(`${BASE_URL}/workflows/stats`, params);
    check(stats, {
        "workflows stats ok": (r) =>
            r.status === 200 || (ALLOW_FORBIDDEN && r.status === 403),
    });

    sleep(jitterSeconds(0.8, 1.8));
}

export function searchFlow() {
    const params = buildParams({ tags: { flow: "search" } });

    // /search is rate-limited; keep volume low unless you increase RATE_LIMIT_SEARCH.
    const q = randomItem(["smith", "john", "test", "S100", "I100"]);
    const res = http.get(`${BASE_URL}/search?q=${encodeURIComponent(q)}&limit=10`, params);
    check(res, {
        "search ok": (r) => r.status === 200 || r.status === 429,
    });
    if (res.status === 200) {
        const body = safeJson(res);
        check(res, { "search json": () => !!body && Array.isArray(body.results) });
    }

    // Aim to stay under the default 30/minute global search limit.
    sleep(jitterSeconds(2.2, 2.8));
}

export function mutationsFlow() {
    // This flow requires CSRF cookies/headers. It is opt-in via ENABLE_MUTATIONS=1.
    const params = buildParams({
        includeJson: true,
        includeCsrf: true,
        tags: { flow: "mutations" },
    });

    if (!CSRF_TOKEN) {
        // Nothing we can do; keep the scenario alive but avoid spamming 403s.
        sleep(5);
        return;
    }

    // Create a task (assigned to self by default) and immediately mark complete.
    const create = http.post(
        `${BASE_URL}/tasks`,
        JSON.stringify({
            title: `[loadtest] Follow up ${Date.now()}`,
            description: "k6 load test task",
            task_type: "other",
        }),
        params
    );
    check(create, {
        "task create ok": (r) => r.status === 201 || (ALLOW_FORBIDDEN && r.status === 403),
    });

    const created = safeJson(create);
    const taskId = created?.id;
    if (create.status === 201 && taskId) {
        const complete = http.post(`${BASE_URL}/tasks/${taskId}/complete`, null, params);
        check(complete, { "task complete ok": (r) => r.status === 200 });
    }

    sleep(jitterSeconds(0.8, 1.6));
}

// =============================================================================
// Helpers
// =============================================================================

function truthyEnv(value) {
    const v = String(value || "").toLowerCase();
    return v === "1" || v === "true" || v === "yes" || v === "on";
}

function normalizeBaseUrl(url) {
    return String(url || "").replace(/\/+$/, "");
}

function buildCookieHeader(raw) {
    if (!raw) return "";
    if (raw.includes("crm_session=")) return raw;
    // Accept passing only the session token for convenience.
    return `crm_session=${raw}`;
}

function parseCookieValue(cookieHeader, name) {
    if (!cookieHeader) return "";
    const parts = cookieHeader.split(";").map((p) => p.trim());
    for (const p of parts) {
        if (p.startsWith(`${name}=`)) return p.slice(name.length + 1);
    }
    return "";
}

function safeJson(res) {
    try {
        return res.json();
    } catch (_) {
        return null;
    }
}

function randomItem(arr) {
    if (!Array.isArray(arr) || arr.length === 0) return null;
    return arr[Math.floor(Math.random() * arr.length)];
}

function jitterSeconds(min, max) {
    const lo = Math.min(min, max);
    const hi = Math.max(min, max);
    return lo + Math.random() * (hi - lo);
}

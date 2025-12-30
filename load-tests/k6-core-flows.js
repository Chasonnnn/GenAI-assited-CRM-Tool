import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const AUTH_COOKIE = __ENV.AUTH_COOKIE || "";

const DEFAULT_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
};

function buildParams() {
    const headers = { ...DEFAULT_HEADERS };
    if (AUTH_COOKIE) {
        headers.Cookie = AUTH_COOKIE;
    }
    return { headers };
}

export const options = {
    scenarios: {
        cases: {
            executor: "constant-vus",
            vus: 5,
            duration: "2m",
            exec: "casesFlow",
        },
        tasks: {
            executor: "constant-vus",
            vus: 3,
            duration: "2m",
            exec: "tasksFlow",
        },
        dashboard: {
            executor: "constant-vus",
            vus: 3,
            duration: "2m",
            exec: "dashboardFlow",
        },
        automation: {
            executor: "constant-vus",
            vus: 2,
            duration: "2m",
            exec: "automationFlow",
        },
    },
    thresholds: {
        http_req_failed: ["rate<0.01"],
        http_req_duration: ["p(95)<800"],
    },
};

export function casesFlow() {
    const params = buildParams();
    const list = http.get(`${BASE_URL}/cases?per_page=20`, params);
    check(list, {
        "cases list ok": (r) => r.status === 200,
    });

    const search = http.get(`${BASE_URL}/search?q=smith&limit=10`, params);
    check(search, {
        "search ok": (r) => r.status === 200,
    });

    sleep(1);
}

export function tasksFlow() {
    const params = buildParams();
    const list = http.get(`${BASE_URL}/tasks?per_page=20&is_completed=false`, params);
    check(list, {
        "tasks list ok": (r) => r.status === 200,
    });

    sleep(1);
}

export function dashboardFlow() {
    const params = buildParams();
    const upcoming = http.get(`${BASE_URL}/dashboard/upcoming`, params);
    check(upcoming, {
        "dashboard upcoming ok": (r) => r.status === 200,
    });

    const summary = http.get(`${BASE_URL}/analytics/summary`, params);
    check(summary, {
        "analytics summary ok": (r) => r.status === 200,
    });

    sleep(1);
}

export function automationFlow() {
    const params = buildParams();
    const workflows = http.get(`${BASE_URL}/workflows`, params);
    check(workflows, {
        "workflows list ok": (r) => r.status === 200,
    });

    const stats = http.get(`${BASE_URL}/workflows/stats`, params);
    check(stats, {
        "workflows stats ok": (r) => r.status === 200,
    });

    sleep(1);
}

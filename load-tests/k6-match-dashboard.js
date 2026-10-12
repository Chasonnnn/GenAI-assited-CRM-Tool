import http from "k6/http";
import { check, fail, sleep } from "k6";
import { Counter } from "k6/metrics";
import { dashboardFlow } from "./k6-core-flows.js";

export { dashboardFlow };

const base = (__ENV.BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const fixtures = __ENV.FIXTURE_FILE ? JSON.parse(open(__ENV.FIXTURE_FILE)) : [];
const completed = new Counter("match_work_completed");
const duration = __ENV.DURATION || "5m";
const scopes = ["case", "attempt", "previous_case"];
const budget = Number(__ENV.P95_MS || 800);

export const options = {
    scenarios: {
        match_work: { executor: "constant-vus", vus: Number(__ENV.VUS_MATCH || 12), duration, exec: "matchWorkFlow" },
        dashboard: { executor: "constant-vus", vus: Number(__ENV.VUS_DASHBOARD || 8), duration, exec: "dashboardFlow" },
    },
    // URL and error tags can contain identifiers. Export only bounded dimensions.
    systemTags: ["status", "method", "name", "scenario", "check", "expected_response"],
    thresholds: {
        checks: ["rate==1"],
        http_req_failed: ["rate<0.01"],
        "http_req_duration{flow:dashboard}": [`p(95)<${budget}`],
        ...Object.fromEntries(scopes.flatMap((scope) => [
            [`http_req_duration{scope:${scope}}`, [`p(95)<${budget}`]],
            [`match_work_completed{scope:${scope}}`, ["count>0"]],
        ])),
    },
};

function readWork(fixture, scope, preflight = false) {
    const id = scope === "previous_case" ? fixture.previous_match_id : fixture.match_id;
    const query = scope === "attempt" ? `?attempt_id=${fixture.attempt_id}` : "";
    const response = http.get(`${base}/matches/${id}/work${query}`, {
        headers: { Cookie: __ENV.AUTH_COOKIE, "X-Requested-With": "XMLHttpRequest" },
        tags: { name: "GET /matches/:id/work", flow: "match_work", scope, phase: preflight ? "preflight" : "load" },
    });
    let body;
    try { body = response.json(); } catch (_) { body = null; }
    const valid = check(response, {
        "match work 200": (r) => r.status === 200,
        "populated work history": () => Array.isArray(body?.activity) && body.activity.length > 0,
        "work collections present": () => Array.isArray(body?.notes) && Array.isArray(body?.tasks),
    });
    if (valid && !preflight) completed.add(1, { scope });
    return valid;
}

export function setup() {
    if (!__ENV.AUTH_COOKIE || !fixtures.length) fail("AUTH_COOKIE and a populated FIXTURE_FILE are required");
    for (const fixture of fixtures) {
        for (const key of ["match_id", "attempt_id", "previous_match_id"]) {
            if (!/^[0-9a-f-]{36}$/i.test(fixture[key] || "")) fail("Invalid benchmark fixture identifier");
        }
        for (const scope of scopes) {
            if (!readWork(fixture, scope, true)) fail("Match history preflight failed; check fixture and permissions");
        }
    }
}

export function matchWorkFlow() {
    const fixture = fixtures[__ITER % fixtures.length];
    for (const scope of scopes) readWork(fixture, scope);
    sleep(0.7 + Math.random() * 0.7);
}

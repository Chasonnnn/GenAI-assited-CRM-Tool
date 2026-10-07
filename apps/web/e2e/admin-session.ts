import type { Browser } from "@e2e-dev/web"

import { API_URL, DEV_SECRET } from "./local-stack"

type SeedResponse = { users: { email: string; user_id: string; role: string }[] }
type Cookie = { url: string; name: string; value: string }

/** Roles of the seeded org users, as the seed endpoint reports them. */
export type SeedRole = "admin" | "intake_specialist" | "case_manager" | "developer"

// A stalled dev request (for example on a locked database) fails the test instead of hanging it.
const REQUEST_TIMEOUT_MS = 10_000
const CSRF_COOKIE = "crm_csrf"

function devRequest(path: string, init: { headers?: Record<string, string>; body?: unknown } = {}) {
    return fetch(`${API_URL}${path}`, {
        method: "POST",
        headers: {
            "X-Dev-Secret": DEV_SECRET,
            ...(init.body === undefined ? {} : { "Content-Type": "application/json" }),
            ...init.headers,
        },
        body: init.body === undefined ? null : JSON.stringify(init.body),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
}

async function failure(response: Response, label: string): Promise<Error> {
    return new Error(`${label} returned ${response.status}: ${await response.text()}`)
}

function sessionCookies(response: Response): Cookie[] {
    return response.headers.getSetCookie().map((header) => {
        const pair = header.slice(0, header.indexOf(";"))
        const separator = pair.indexOf("=")
        return { url: API_URL, name: pair.slice(0, separator), value: pair.slice(separator + 1) }
    })
}

/**
 * Mints a session for a seeded org user through the API's dev endpoints, which replace the
 * OAuth screen locally: seed the test org (idempotent), then log in as the user.
 */
async function seededSession(role: SeedRole): Promise<Cookie[]> {
    const seed = await devRequest("/dev/seed")
    if (!seed.ok) throw await failure(seed, "POST /dev/seed")
    const { users } = (await seed.json()) as SeedResponse
    const user = users.find((candidate) => candidate.role === role)
    if (!user) throw new Error(`The seed returned no ${role} user.`)

    const login = await devRequest(`/dev/login-as/${user.user_id}`)
    if (!login.ok) throw await failure(login, "POST /dev/login-as")
    return sessionCookies(login)
}

/** Signs the browser in as a seeded org user. */
export async function grantSession(browser: Browser, role: SeedRole): Promise<void> {
    await browser.setCookies(await seededSession(role))
}

export function grantAdminSession(browser: Browser): Promise<void> {
    return grantSession(browser, "admin")
}

/**
 * Signs the browser in as if Google had verified `email`. The API resolves the sign-in as its
 * OAuth callback does, so a matching pending invite is accepted and its user created.
 * Returns the callback's error code instead when the API refuses the sign-in.
 */
export async function grantGoogleSession(
    browser: Browser,
    sign: { email: string; displayName: string; inviteId?: string },
): Promise<{ error?: string }> {
    const response = await devRequest("/dev/google-login", {
        body: { email: sign.email, display_name: sign.displayName, invite_id: sign.inviteId },
    })
    if (response.status === 403) return { error: ((await response.json()) as { detail: string }).detail }
    if (!response.ok) throw await failure(response, "POST /dev/google-login")
    await browser.setCookies(sessionCookies(response))
    return {}
}

/**
 * Creates an invitation from the admin session the browser holds, without sending its email:
 * the local stack has no platform sender, so the settings endpoint refuses every invitation.
 */
export async function createInvite(
    browser: Browser,
    invite: { email: string; role: string; expiresAt?: Date },
): Promise<{ id: string }> {
    const cookies = await browser.cookies()
    const csrf = cookies.find((cookie) => cookie.name === CSRF_COOKIE)?.value
    if (!csrf) throw new Error("The browser holds no session; give the test the admin session.")
    const response = await devRequest("/dev/invites", {
        headers: {
            Cookie: cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join("; "),
            "X-CSRF-Token": csrf,
        },
        body: { email: invite.email, role: invite.role, expires_at: invite.expiresAt?.toISOString() },
    })
    if (!response.ok) throw await failure(response, "POST /dev/invites")
    return (await response.json()) as { id: string }
}

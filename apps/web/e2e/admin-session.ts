import type { Browser } from "@e2e-dev/web"

import { API_URL, DEV_SECRET } from "./local-stack"

type SeedResponse = { users: { email: string; user_id: string; role: string }[] }

/** Roles of the seeded org users, as the seed endpoint reports them. */
export type SeedRole = "admin" | "intake_specialist" | "case_manager" | "developer"

/**
 * Signs the browser in as a seeded org user through the API's dev endpoints, which replace
 * the OAuth screen locally: seed the test org (idempotent), mint a session, and hand its
 * cookies to the browser.
 */
export async function grantSession(browser: Browser, role: SeedRole): Promise<void> {
    const headers = { "X-Dev-Secret": DEV_SECRET }

    const seed = await fetch(`${API_URL}/dev/seed`, { method: "POST", headers })
    if (!seed.ok) throw new Error(`POST /dev/seed returned ${seed.status}.`)
    const { users } = (await seed.json()) as SeedResponse
    const user = users.find((candidate) => candidate.role === role)
    if (!user) throw new Error(`The seed returned no ${role} user.`)

    const login = await fetch(`${API_URL}/dev/login-as/${user.user_id}`, { method: "POST", headers })
    if (!login.ok) throw new Error(`POST /dev/login-as returned ${login.status}.`)
    const cookies = login.headers.getSetCookie().map((header) => {
        const pair = header.slice(0, header.indexOf(";"))
        const separator = pair.indexOf("=")
        return { url: API_URL, name: pair.slice(0, separator), value: pair.slice(separator + 1) }
    })
    await browser.setCookies(cookies)
}

export function grantAdminSession(browser: Browser): Promise<void> {
    return grantSession(browser, "admin")
}

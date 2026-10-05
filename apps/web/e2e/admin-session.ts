import type { Browser } from "@e2e-dev/web"

import { API_URL, DEV_SECRET } from "./local-stack"

type SeedResponse = { users: { email: string; user_id: string; role: string }[] }

/**
 * Signs the browser in as the seeded org admin through the API's dev endpoints, which
 * replace the OAuth screen locally: seed the test org (idempotent), mint a session, and
 * hand its cookies to the browser.
 */
export async function grantAdminSession(browser: Browser): Promise<void> {
    const headers = { "X-Dev-Secret": DEV_SECRET }

    const seed = await fetch(`${API_URL}/dev/seed`, { method: "POST", headers })
    if (!seed.ok) throw new Error(`POST /dev/seed returned ${seed.status}.`)
    const { users } = (await seed.json()) as SeedResponse
    const admin = users.find((user) => user.role === "admin")
    if (!admin) throw new Error("The seed returned no admin user.")

    const login = await fetch(`${API_URL}/dev/login-as/${admin.user_id}`, { method: "POST", headers })
    if (!login.ok) throw new Error(`POST /dev/login-as returned ${login.status}.`)
    const cookies = login.headers.getSetCookie().map((header) => {
        const pair = header.slice(0, header.indexOf(";"))
        const separator = pair.indexOf("=")
        return { url: API_URL, name: pair.slice(0, separator), value: pair.slice(separator + 1) }
    })
    await browser.setCookies(cookies)
}

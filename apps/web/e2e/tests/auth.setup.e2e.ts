import { test } from "@e2e-dev/web"
import { expect } from "e2e"

import { grantSession, type SeedRole } from "../admin-session"

const SESSIONS: Array<[string, SeedRole]> = [
    ["admin", "admin"],
    ["case-manager", "case_manager"],
]

for (const [name, role] of SESSIONS) {
    test.setup(`sign in as ${name}`, { sessions: [name] }, async ({ app, browser, screen, session }) => {
        await grantSession(browser, role)

        // A freshly seeded user has no job title, so the app shell sends it to the welcome
        // step. Completing it here leaves every later test on the page it opens.
        await app.open("/welcome")
        await screen.getByRole("textbox", "Job Title *").fill("QA Lead")
        await screen.getByRole("button", "Complete Profile").tap()
        await expect(browser).toHaveURL("/dashboard", { timeout: 15_000 })

        await session.save(name)
    })
}

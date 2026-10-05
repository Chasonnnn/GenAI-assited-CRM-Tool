import { test } from "@e2e-dev/web"
import { expect } from "e2e"

import { grantAdminSession } from "../admin-session"

test.setup("sign in as admin", { sessions: ["admin"] }, async ({ app, browser, screen, session }) => {
    await grantAdminSession(browser)

    // A freshly seeded user has no job title, so the app shell sends it to the welcome
    // step. Completing it here leaves every later test on the page it opens.
    await app.open("/welcome")
    await screen.getByRole("textbox", "Job Title *").fill("QA Lead")
    await screen.getByRole("button", "Complete Profile").tap()
    await expect(browser).toHaveURL("/dashboard", { timeout: 15_000 })

    await session.save("admin")
})

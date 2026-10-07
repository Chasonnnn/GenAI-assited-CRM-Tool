import { test } from "@e2e-dev/web"
import { expect } from "e2e"

test(
    "a case manager works records but cannot manage the team",
    { session: "case-manager", tags: ["access"] },
    async ({ app, screen }) => {
        await app.open("/surrogates")
        await expect(screen.getByRole("heading", "Surrogates")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("link").filter({ hasText: /^#S\d{5}$/ }).first()).toBeVisible({ timeout: 10_000 })

        // The page shell renders, and the API refuses the team data.
        await app.open("/settings/team")
        await expect(screen.getByRole("alert").filter({ hasText: "Missing permission: manage_team" })).toBeVisible({
            timeout: 10_000,
        })
        await expect(screen.getByRole("button", /^Invite/)).toHaveCount(0)

        // Pipeline configuration is an admin surface.
        await app.open("/settings/pipelines")
        await expect(screen.getByRole("heading", "Permission required")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("button", "Add Custom Stage")).toHaveCount(0)
    },
)

test(
    "an admin cannot open the developer data management page",
    { session: "admin", tags: ["access"] },
    async ({ app, screen }) => {
        await app.open("/settings/admin")
        await expect(screen.getByRole("heading", "Permission required")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("link", "Back to Settings")).toBeVisible()
    },
)

test(
    "an organization admin is turned away from the ops console",
    { session: "admin", tags: ["access"] },
    async ({ app, screen, browser }) => {
        await app.open("/ops")
        await expect(browser).toHaveURL("/ops/login?error=not_platform_admin", { timeout: 15_000 })
        await expect(screen.getByRole("alert").filter({ hasText: "This account does not have platform access." })).toBeVisible()
        await expect(screen.getByRole("link", "Agencies")).toHaveCount(0)

        await screen.getByRole("link", "Back to app").tap()
        await expect(browser).toHaveURL("/dashboard", { timeout: 15_000 })
    },
)

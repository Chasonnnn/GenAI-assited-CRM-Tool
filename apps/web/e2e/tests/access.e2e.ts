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
    },
)

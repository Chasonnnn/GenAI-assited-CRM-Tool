import { test } from "@e2e-dev/web"
import { expect } from "e2e"

import { grantAdminSession } from "../admin-session"
import { APPLICANT, publishForm, submitApplication } from "../forms"

test(
    "a form's routing saves, and a reviewed submission becomes a lead",
    { session: "admin", tags: ["forms-routing"] },
    async ({ app, screen, browser }) => {
        await publishForm(app, screen, "E2E routing form", "/intake/e2e-routing-form")
        const builderUrl = await browser.url()

        // Routing settings persist on the form.
        await screen.getByRole("tab", "Routing").tap()
        await expect(screen.getByRole("button", "Save routing")).toBeDisabled({ timeout: 10_000 })
        await screen.getByRole("radiogroup", "One exact match").getByRole("radio", "Link automatically").check()
        await screen.getByRole("button", "Save routing").tap()
        await expect(screen.getByText("Routing saved")).toBeVisible({ timeout: 10_000 })
        await browser.reload()
        await screen.getByRole("tab", "Routing").tap()
        await expect(screen.getByRole("radiogroup", "One exact match").getByRole("radio", "Link automatically")).toBeChecked({
            timeout: 10_000,
        })

        await submitApplication(app, screen, "/intake/e2e-routing-form", APPLICANT.email)
        await expect(screen.getByRole("heading", "Application Submitted!")).toBeVisible({ timeout: 15_000 })

        // Automatic matching ran on submit and found no record, so the review offers to create a lead.
        await grantAdminSession(browser)
        await browser.goto(`${builderUrl}?tab=submissions`)
        const review = screen.getByRole("region", "Routing Review")
        await expect(review.getByRole("row").filter({ hasText: APPLICANT.name })).toContainText("No match", { timeout: 10_000 })
        await review.getByRole("button", `Create lead for ${APPLICANT.name}`).tap()
        await expect(screen.getByText("Intake lead created")).toBeVisible({ timeout: 10_000 })

        // The lead moves to the promotion queue, which opens; promotion creates the surrogate.
        const queue = screen.getByRole("region", "Lead Promotion Queue")
        await queue.getByRole("button", /^Promote/).tap()
        await expect(screen.getByText(/^Intake lead promoted to /)).toBeVisible({ timeout: 10_000 })

        await app.open("/surrogates")
        await screen.getByRole("textbox", "Search surrogates").fill(APPLICANT.name)
        await expect(screen.getByRole("row").filter({ hasText: APPLICANT.name })).toHaveCount(1, { timeout: 10_000 })

        // The submissions page shows the same submission under the form, now processed.
        await app.open("/automation/form-submissions")
        await screen.getByRole("combobox", "Form").tap()
        await screen.getByRole("option", "E2E routing form").tap()
        await expect(screen.getByRole("heading", "Lead Promotion Queue 0")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("article", APPLICANT.name)).toBeVisible({ timeout: 10_000 })
    },
)

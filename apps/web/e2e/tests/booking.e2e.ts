import { test } from "@e2e-dev/web"
import { expect } from "e2e"
import type { Screen } from "e2e"

import { queryDatabase } from "../database"

// The tests run in order on one worker: the first publishes what the others book.
// The type is a phone call because Zoom and Google Meet need provider connections that
// the local stack does not have.
const TYPE_NAME = "E2E Phone Consultation"
const CLIENT = { name: "Bea Booker", email: "bea.booker@example.com", phone: "(555) 010-4477" }
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

/** Picks the nth open day on the calendar, moving to the next month when this one has none left. */
async function pickOpenDay(screen: Screen, nth = 0): Promise<void> {
    const openDays = screen.getByRole("button", { name: /^\d{1,2}$/, disabled: false })
    await expect(screen.getByText("Loading available times…")).toBeHidden({ timeout: 10_000 })
    if ((await openDays.count()) <= nth) await screen.getByRole("button", "Next month").tap()
    await openDays.nth(nth).tap()
}

async function pickFirstTime(screen: Screen): Promise<void> {
    const times = screen.getByRole("group", "Available times").getByRole("button")
    await expect(times.first()).toBeVisible({ timeout: 10_000 })
    await times.first().tap()
}

function selfServiceLinks(): { orgId: string; rescheduleToken: string; cancelToken: string } {
    const [row] = queryDatabase(
        "SELECT organization_id, reschedule_token, cancel_token FROM appointments WHERE client_email = %s",
        [CLIENT.email],
    )
    if (!row?.[0] || !row[1] || !row[2]) throw new Error(`No appointment with tokens for ${CLIENT.email}.`)
    return { orgId: row[0], rescheduleToken: row[1], cancelToken: row[2] }
}

test(
    "an admin publishes weekly availability and a phone appointment type",
    { session: "admin", tags: ["booking"] },
    async ({ app, screen }) => {
        // Opening the page creates the default Monday to Friday hours; the weekend is added so
        // that a run on any day finds open days. `check` leaves a day that is already on as is.
        await app.open("/settings/appointments?tab=availability")
        for (const day of DAYS) await screen.getByRole("switch", `Available on ${day}`).check()
        for (const day of DAYS) await expect(screen.getByRole("switch", `Available on ${day}`)).toBeChecked()
        await screen.getByRole("button", "Save availability").tap()
        await expect(screen.getByRole("button", "Save availability")).toBeDisabled({ timeout: 10_000 })

        await app.open("/settings/appointments?tab=availability")
        await expect(screen.getByRole("switch", "Available on Sunday")).toBeChecked({ timeout: 10_000 })

        await app.open("/settings/appointments?tab=types")
        await screen.getByRole("button", "Add type").first().tap()
        const dialog = screen.getByRole("dialog", "New Appointment Type")
        await dialog.getByRole("textbox", "Name").fill(TYPE_NAME)
        // At least one format stays selected, so Phone goes on before Zoom comes off.
        await dialog.getByRole("checkbox", "Phone").check()
        await dialog.getByRole("checkbox", "Zoom").uncheck()
        await dialog.getByRole("textbox", "Dial-in Number").fill("+1 (555) 010-2030")
        await dialog.getByRole("button", "Create type").tap()
        await expect(dialog).toBeHidden({ timeout: 10_000 })
        await expect(screen.getByText(TYPE_NAME)).toBeVisible()

        // Asking for the link creates it; the public page answers only once it exists.
        await app.open("/appointments")
        await screen.getByRole("button", "Share booking link").tap()
        await expect(screen.getByRole("textbox", "Booking link")).toHaveValue(/\/book\/test-admin$/)
    },
)

test("a visitor requests an appointment on the public booking page", { tags: ["booking"] }, async ({ app, screen }) => {
    await app.open("/book/test-admin")
    await expect(screen.getByRole("heading", "Test Admin")).toBeVisible({ timeout: 15_000 })
    await screen.getByRole("button", TYPE_NAME).tap()
    await pickOpenDay(screen)
    await pickFirstTime(screen)
    await screen.getByRole("button", "Enter contact details").tap()

    await expect(screen.getByRole("heading", "Your details")).toBeVisible()
    await screen.getByRole("textbox", "Full name *").fill(CLIENT.name)
    await screen.getByRole("textbox", "Email *").fill(CLIENT.email)
    await screen.getByRole("textbox", "Phone number *").fill(CLIENT.phone)
    await screen.getByRole("button", "Request Appointment").tap()

    await expect(screen.getByRole("heading", "Request Submitted!")).toBeVisible({ timeout: 15_000 })
    await expect(screen.getByText(TYPE_NAME)).toBeVisible()
})

test(
    "an unknown booking link shows the not found state",
    { tags: ["booking"] },
    async ({ app, screen }) => {
        await app.open("/book/no-such-staff")
        await expect(screen.getByRole("heading", "Booking Page Not Found")).toBeVisible({ timeout: 15_000 })
    },
)

test(
    "an admin approves the pending request",
    { session: "admin", tags: ["booking"] },
    async ({ app, screen }) => {
        await app.open("/appointments")
        await screen.getByRole("tab", /^Pending/).tap()
        const request = screen.getByRole("button").filter({ hasText: CLIENT.name }).first()
        await expect(request).toContainText("Pending", { timeout: 10_000 })
        await screen.getByRole("button", "Approve").tap()

        await screen.getByRole("tab", /^Upcoming/).tap()
        await expect(screen.getByRole("button").filter({ hasText: CLIENT.name }).first()).toContainText("Confirmed", {
            timeout: 10_000,
        })

        // The request created its default client email template, which the library lists by name.
        await app.open("/automation/email-templates")
        await screen.getByRole("tab", /^Organization/).tap()
        await expect(screen.getByRole("heading", /Booking Request Received$/)).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("heading", /appointment_request_received/)).toHaveCount(0)
    },
)

test(
    "the visitor reschedules and then cancels through the self-service links",
    { tags: ["booking"] },
    async ({ app, screen }) => {
        // Approval rotates the tokens, so they are read after it.
        const before = selfServiceLinks()
        await app.open(`/book/self-service/${before.orgId}/manage/${before.rescheduleToken}`)
        await expect(screen.getByText("Manage Appointment")).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByText(TYPE_NAME)).toBeVisible()
        // Today may have no time left, so the visitor moves to a later day.
        await pickOpenDay(screen, 2)
        await pickFirstTime(screen)
        await screen.getByRole("button", "Confirm Reschedule").tap()
        await expect(screen.getByRole("heading", "Appointment Rescheduled")).toBeVisible({ timeout: 15_000 })

        const after = selfServiceLinks()
        await app.open(`/book/self-service/${after.orgId}/manage/${after.cancelToken}?action=cancel`)
        await screen.getByRole("textbox", "Reason for cancellation (optional)").fill("Plans changed")
        await screen.getByRole("button", "Cancel Appointment").tap()
        await expect(screen.getByRole("heading", "Appointment Cancelled")).toBeVisible({ timeout: 15_000 })

        // A used link no longer opens the appointment.
        await app.open(`/book/self-service/${after.orgId}/manage/${after.cancelToken}?action=cancel`)
        await expect(screen.getByRole("heading", "Unable to Manage Appointment")).toBeVisible({ timeout: 15_000 })
    },
)

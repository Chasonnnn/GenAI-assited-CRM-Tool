import { test } from "@e2e-dev/web"
import { expect } from "e2e"

import { createInvite, grantGoogleSession } from "../admin-session"

// Invitees use example.com addresses, so the team test's count of seeded @test.com members holds.
const INVITEE = { email: "ivy.invitee@example.com", displayName: "Ivy Invitee" }

test(
    "an invitee accepts a pending invitation through Google sign-in",
    { session: "admin", tags: ["invites"] },
    async ({ app, screen, browser }) => {
        // The admin session only creates the invite; the invitee then replaces it.
        const invite = await createInvite(browser, { email: INVITEE.email, role: "intake_specialist" })

        // The Google button leaves for the API's OAuth start; the request is held here instead.
        const signInStarts: string[] = []
        await browser.route("**/auth/google/login**", (route) => {
            signInStarts.push(route.request.url)
            return route.fulfill({ status: 204 })
        })

        await app.open(`/invite/${invite.id}`)
        await expect(screen.getByText("You're Invited")).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByText("Test Admin")).toBeVisible()
        await expect(screen.getByText("Test Organization")).toBeVisible()
        await screen.getByRole("button", "Continue with Google").tap()
        await expect.poll(() => signInStarts.length).toBe(1)
        expect(signInStarts[0]).toContain(`invite_id=${invite.id}`)

        // Google returns the invitee's verified email; the API accepts the invite and signs them in.
        expect(await grantGoogleSession(browser, { ...INVITEE, inviteId: invite.id })).toEqual({})
        await app.open("/welcome")
        await screen.getByRole("textbox", "Job Title *").fill("Intake Coordinator")
        await screen.getByRole("button", "Complete Profile").tap()
        await expect(browser).toHaveURL("/dashboard", { timeout: 15_000 })

        await app.open(`/invite/${invite.id}`)
        await expect(screen.getByText("Welcome!")).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByText("This invite is accepted.")).toBeVisible()
        await expect(screen.getByText(/^You already have access to this organization\./)).toBeVisible()
    },
)

test(
    "another Google account cannot use someone else's invitation",
    { session: "admin", tags: ["invites"] },
    async ({ app, screen, browser }) => {
        const invite = await createInvite(browser, { email: "rhea.reserved@example.com", role: "case_manager" })

        const signIn = await grantGoogleSession(browser, {
            email: "mallory.other@example.com",
            displayName: "Mallory Other",
            inviteId: invite.id,
        })
        expect(signIn).toEqual({ error: "not_invited" })

        // The OAuth callback sends a refused sign-in to the login page with that code.
        await app.open(`/login?error=${signIn.error}`)
        await expect(screen.getByText("Invite required")).toBeVisible({ timeout: 15_000 })

        // The invitation stays open for the right person.
        await app.open(`/invite/${invite.id}`)
        await expect(screen.getByRole("button", "Continue with Google")).toBeVisible({ timeout: 15_000 })
    },
)

test(
    "expired, revoked, and unknown invitations explain why they cannot be used",
    { session: "admin", tags: ["invites"] },
    async ({ app, screen, browser }) => {
        const expired = await createInvite(browser, {
            email: "eli.expired@example.com",
            role: "case_manager",
            expiresAt: new Date(Date.now() - 24 * 60 * 60 * 1000),
        })
        await app.open(`/invite/${expired.id}`)
        await expect(screen.getByText("This invite is expired.")).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByText("Ask the inviter to send a new invitation.")).toBeVisible()
        await expect(screen.getByRole("button", "Continue with Google")).toHaveCount(0)

        // The admin revokes a pending invitation from the team page.
        const revokedEmail = "rory.revoked@example.com"
        const revoked = await createInvite(browser, { email: revokedEmail, role: "case_manager" })
        await app.open("/settings/team")
        await screen.getByRole("tab", /^Invitations \(\d+\)$/).tap()
        await browser.onDialog("accept")
        await screen.getByRole("button", `Revoke invitation for ${revokedEmail}`).tap()
        await expect(screen.getByText("Invitation revoked")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("button", `Revoke invitation for ${revokedEmail}`)).toHaveCount(0)

        await app.open(`/invite/${revoked.id}`)
        await expect(screen.getByText("This invite is revoked.")).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByRole("button", "Continue with Google")).toHaveCount(0)

        await app.open("/invite/00000000-0000-4000-8000-000000000000")
        await expect(screen.getByText("Invitation not found")).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByText("This invitation is invalid or has expired.")).toBeVisible()
    },
)

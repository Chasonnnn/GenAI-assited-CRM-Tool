import type { ReactNode } from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AgencyInvitesTab } from "@/components/ops/agencies/AgencyInvitesTab"
import { AgencyOverviewTab } from "@/components/ops/agencies/AgencyOverviewTab"
import type { OrganizationDetail } from "@/lib/api/platform"

vi.mock("@/components/app-link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

const org: OrganizationDetail = {
    id: "org-1",
    name: "Test Agency",
    slug: "test-agency",
    portal_base_url: "https://test-agency.example.com",
    timezone: "America/New_York",
    member_count: 2,
    surrogate_count: 3,
    subscription_plan: "starter",
    subscription_status: "active",
    created_at: "2026-01-01T00:00:00Z",
    deleted_at: null,
    purge_at: null,
    active_match_count: 0,
    pending_task_count: 0,
    ai_enabled: false,
}

function expectDestructiveFill(element: HTMLElement) {
    expect(element).toHaveClass("bg-destructive")
    expect(element.className).not.toMatch(/linear-gradient/)
}

describe("ops agency destructive actions", () => {
    it("separates soft delete from the irreversible purge and uses destructive confirms", async () => {
        const onPurgeOrganization = vi.fn()
        render(
            <AgencyOverviewTab
                org={org}
                isDeleted={false}
                purgeDate={null}
                restoreSubmitting={false}
                deleteSubmitting={false}
                purgeSubmitting={false}
                onRestoreOrganization={vi.fn()}
                onDeleteOrganization={vi.fn()}
                onPurgeOrganization={onPurgeOrganization}
            />
        )

        const softDelete = screen.getByRole("button", { name: "Delete Organization" })
        const purge = screen.getByRole("button", { name: "Permanently delete now" })
        // The irreversible purge is the solid destructive button; soft delete is the outline one.
        expectDestructiveFill(purge)
        expect(softDelete).not.toHaveClass("bg-destructive")
        expect(softDelete).toHaveClass("text-destructive")
        expect(softDelete.parentElement).not.toBe(purge.parentElement)
        expect(softDelete.parentElement).toHaveClass("flex-wrap", "gap-2")
        expect(purge.parentElement).toHaveClass("flex-wrap", "gap-2")

        fireEvent.click(softDelete)
        expectDestructiveFill(await screen.findByRole("button", { name: "Confirm Delete" }))
        fireEvent.click(screen.getByRole("button", { name: "Cancel" }))

        fireEvent.click(purge)
        const deleteNow = await screen.findByRole("button", { name: "Delete now" })
        expectDestructiveFill(deleteNow)
        fireEvent.click(deleteNow)
        expect(onPurgeOrganization).toHaveBeenCalledOnce()
    })

    it("names the revoke icon button and confirms with a destructive action", async () => {
        const onRevokeInvite = vi.fn()
        render(
            <AgencyInvitesTab
                orgName="Test Agency"
                invites={[
                    {
                        id: "invite-1",
                        email: "new.user@example.com",
                        role: "admin",
                        status: "pending",
                        created_at: "2026-01-01T00:00:00Z",
                        can_resend: true,
                    },
                ]}
                inviteOpen={false}
                inviteSubmitting={false}
                inviteResending={null}
                inviteForm={{ email: "", role: "admin" }}
                inviteError={null}
                platformEmailStatus={{ configured: true, from_email: null, provider: "resend" }}
                platformEmailStatusLoading={false}
                platformEmailReadiness={null}
                platformEmailReadinessLoading={false}
                platformEmailReadinessError={false}
                platformEmailCheckPending={false}
                platformEmailCheckError={false}
                onCheckPlatformEmailReadiness={vi.fn()}
                onInviteOpenChange={vi.fn()}
                onInviteEmailChange={vi.fn()}
                onInviteRoleChange={vi.fn()}
                onCreateInvite={vi.fn()}
                onResendInvite={vi.fn()}
                onRevokeInvite={onRevokeInvite}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Revoke invite for new.user@example.com" }))
        const revoke = await screen.findByRole("button", { name: "Revoke" })
        expectDestructiveFill(revoke)
        fireEvent.click(revoke)
        expect(onRevokeInvite).toHaveBeenCalledWith("invite-1")
    })
})

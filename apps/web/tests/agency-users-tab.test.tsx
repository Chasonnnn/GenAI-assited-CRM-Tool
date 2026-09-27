import "@testing-library/jest-dom"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AgencyUsersTab } from "@/components/ops/agencies/AgencyUsersTab"

describe("AgencyUsersTab", () => {
    it("warns that reset also clears Duo enrollment", async () => {
        render(
            <AgencyUsersTab
                members={[
                    {
                        id: "member_1",
                        user_id: "user_1",
                        email: "cathyf@ewifamilyglobal.com",
                        display_name: "Cathy F",
                        role: "admin",
                        is_active: true,
                        last_login_at: "2026-03-09T18:25:34Z",
                        created_at: "2026-02-18T23:34:00Z",
                    },
                ]}
                orgName="EWI"
                mfaResetting={null}
                onResetMfa={vi.fn()}
                onDeactivateMember={vi.fn()}
                onReactivateMember={vi.fn()}
                reactivating={null}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /reset mfa for cathyf@ewifamilyglobal\.com/i }))

        expect(await screen.findByText("Reset MFA and Duo?")).toBeInTheDocument()
        expect(
            screen.getByText(/clear CRM MFA state and Duo enrollment/i)
        ).toBeInTheDocument()
        expect(screen.getByText(/may fail if Duo is unavailable/i)).toBeInTheDocument()
    })

    const activeMember = {
        id: "member_active",
        user_id: "user_active",
        email: "active@example.com",
        display_name: "Active Person",
        role: "intake_specialist",
        is_active: true,
        last_login_at: null,
        created_at: "2026-02-18T23:34:00Z",
    }
    const inactiveMember = {
        ...activeMember,
        id: "member_inactive",
        user_id: "user_inactive",
        email: "inactive@example.com",
        display_name: "Inactive Person",
        is_active: false,
    }

    it("confirms deactivation with a destructive action and a reversible consequence", async () => {
        const onDeactivateMember = vi.fn()
        render(
            <AgencyUsersTab
                members={[activeMember]}
                orgName="EWI"
                mfaResetting={null}
                onResetMfa={vi.fn()}
                onDeactivateMember={onDeactivateMember}
                onReactivateMember={vi.fn()}
                reactivating={null}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Deactivate active@example.com" }))

        expect(await screen.findByText("Deactivate Active Person?")).toBeInTheDocument()
        expect(screen.getByText(/loses access to EWI/)).toBeInTheDocument()
        expect(screen.getByText(/reactivate them from the Members list/)).toBeInTheDocument()
        const confirm = screen.getByRole("button", { name: "Deactivate" })
        expect(confirm).toHaveClass("bg-destructive")
        expect(confirm.className).not.toMatch(/linear-gradient/)

        fireEvent.click(confirm)
        expect(onDeactivateMember).toHaveBeenCalledWith("member_active")
    })

    it("offers Reactivate only for inactive members", () => {
        const onReactivateMember = vi.fn()
        const { rerender } = render(
            <AgencyUsersTab
                members={[activeMember, inactiveMember]}
                orgName="EWI"
                mfaResetting={null}
                onResetMfa={vi.fn()}
                onDeactivateMember={vi.fn()}
                onReactivateMember={onReactivateMember}
                reactivating={null}
            />
        )

        expect(screen.queryByRole("button", { name: "Reactivate active@example.com" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Deactivate inactive@example.com" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Reactivate inactive@example.com" }))
        expect(onReactivateMember).toHaveBeenCalledWith("member_inactive")

        rerender(
            <AgencyUsersTab
                members={[activeMember, inactiveMember]}
                orgName="EWI"
                mfaResetting={null}
                onResetMfa={vi.fn()}
                onDeactivateMember={vi.fn()}
                onReactivateMember={onReactivateMember}
                reactivating="member_inactive"
            />
        )
        expect(screen.getByRole("button", { name: "Reactivate inactive@example.com" })).toBeDisabled()
    })
})

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
            />
        )

        fireEvent.click(screen.getByRole("button", { name: /reset mfa for cathyf@ewifamilyglobal\.com/i }))

        expect(await screen.findByText("Reset MFA and Duo?")).toBeInTheDocument()
        expect(
            screen.getByText(/clear CRM MFA state and Duo enrollment/i)
        ).toBeInTheDocument()
        expect(screen.getByText(/may fail if Duo is unavailable/i)).toBeInTheDocument()
    })
})

import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"

import { AppointmentLinkSection } from "@/components/appointments/AppointmentLinkSection"
import type { Appointment } from "@/lib/api/appointments"

const mocks = vi.hoisted(() => ({
    mutate: vi.fn(),
    permissions: ["view_intended_parents"],
    isPending: false,
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { user_id: "staff" } }),
}))
vi.mock("@/lib/hooks/use-appointments", () => ({
    useUpdateAppointmentLink: () => ({ mutate: mocks.mutate, isPending: mocks.isPending }),
}))
vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({
        data: { permissions: mocks.permissions },
        isLoading: false,
    }),
}))
vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogates: () => ({ data: { items: [] } }),
}))
vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: () => ({ data: { items: [] } }),
}))

function appointment(overrides: Partial<Appointment> = {}) {
    return {
        id: "appointment",
        surrogate_id: null,
        surrogate_number: null,
        intended_parent_id: null,
        intended_parent_name: null,
        ...overrides,
    }
}

describe("Appointment links", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.permissions = ["view_intended_parents"]
        mocks.isPending = false
    })

    it("shows the donor linked to a donor-only appointment", () => {
        render(<AppointmentLinkSection appointment={appointment({ donor_id: "donor", donor_name: "QA Donor" })} />)

        expect(screen.getByText("QA Donor")).toBeInTheDocument()
        expect(screen.getByText("Donor")).toBeInTheDocument()
        expect(screen.queryByText("Not linked")).not.toBeInTheDocument()
    })

    it("shows a donor fallback when the linked record has no display name", () => {
        render(<AppointmentLinkSection appointment={appointment({ donor_id: "hidden-donor-id" })} />)

        expect(screen.getByText("Linked donor")).toBeInTheDocument()
        expect(screen.queryByText("hidden-donor-id")).not.toBeInTheDocument()
        expect(screen.queryByText("Not linked")).not.toBeInTheDocument()
    })

    it.each([
        [{ match_id: "hidden-match-id" }, "Match case"],
        [{ attempt_id: "hidden-attempt-id" }, "Match attempt"],
    ] as const)("shows existing case context without exposing its id", (links, label) => {
        render(<AppointmentLinkSection appointment={appointment(links)} />)

        expect(screen.getByText(label)).toBeInTheDocument()
        expect(screen.queryByText("Not linked")).not.toBeInTheDocument()
        expect(screen.queryByText(Object.values(links)[0])).not.toBeInTheDocument()
    })

    it("shows fallback labels for linked surrogate and intended parent records", () => {
        render(<AppointmentLinkSection appointment={appointment({ surrogate_id: "surrogate", intended_parent_id: "ip" })} />)

        expect(screen.getByText("Linked surrogate")).toBeInTheDocument()
        expect(screen.getByText("Linked intended parent")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Unlink surrogate" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Unlink intended parent" })).toBeInTheDocument()
    })

    it("keeps existing surrogate and intended parent labels and unlink actions", () => {
        render(<AppointmentLinkSection appointment={appointment({
            surrogate_id: "surrogate", surrogate_number: "S1001",
            intended_parent_id: "ip", intended_parent_name: "QA Parent",
        })} />)

        expect(screen.getByText("#S1001")).toBeInTheDocument()
        expect(screen.getByText("QA Parent")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Unlink surrogate S1001" }))
        expect(mocks.mutate).toHaveBeenLastCalledWith({ appointmentId: "appointment", data: { surrogate_id: null } })
        fireEvent.click(screen.getByRole("button", { name: "Unlink intended parent QA Parent" }))
        expect(mocks.mutate).toHaveBeenLastCalledWith({ appointmentId: "appointment", data: { intended_parent_id: null } })
    })

    it("keeps donor and case fields out of participant edits", () => {
        render(<AppointmentLinkSection appointment={appointment({
            donor_id: "donor", donor_name: "QA Donor", match_id: "match", attempt_id: "attempt",
        })} />)

        fireEvent.click(screen.getByRole("button", { name: "Edit" }))
        fireEvent.click(screen.getByRole("button", { name: "Save links" }))

        expect(mocks.mutate).toHaveBeenCalledWith({
            appointmentId: "appointment",
            data: { surrogate_id: null, intended_parent_id: null },
        }, { onSuccess: expect.any(Function) })
    })

    it("preserves the intended parent permission restriction in the editor", () => {
        mocks.permissions = []
        render(<AppointmentLinkSection appointment={appointment({ donor_id: "donor" })} />)
        fireEvent.click(screen.getByRole("button", { name: "Edit" }))

        expect(screen.getByText("Your role cannot view intended parents. Ask an admin to change your permissions.")).toBeInTheDocument()
    })

    it("shows the empty state only when no record or case is linked", () => {
        render(<AppointmentLinkSection appointment={appointment()} />)

        expect(screen.getByText("Not linked")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Link" })).toBeInTheDocument()
    })

    it("disables existing unlink actions while the update is pending", () => {
        mocks.isPending = true
        render(<AppointmentLinkSection appointment={appointment({ surrogate_id: "surrogate" })} />)

        expect(screen.getByRole("button", { name: "Unlink surrogate" })).toBeDisabled()
    })
})

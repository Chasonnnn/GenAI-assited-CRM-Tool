import { describe, it, expect, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"

import { LogInterviewOutcomeDialog } from "@/components/surrogates/LogInterviewOutcomeDialog"

const mockMutateAsync = vi.fn()

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
    DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
    DialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({
        value,
        onValueChange,
        children,
    }: {
        value?: string
        onValueChange?: (value: string) => void
        children: React.ReactNode
    }) => (
        <div>
            <select
                data-testid="outcome-select"
                value={value ?? ""}
                onChange={(event) => onValueChange?.(event.target.value)}
            >
                <option value="">Select</option>
                <option value="completed">Completed</option>
                <option value="no_show">No Show</option>
                <option value="rescheduled">Rescheduled</option>
                <option value="cancelled">Cancelled</option>
            </select>
            {children}
        </div>
    ),
    SelectTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    SelectValue: () => null,
    SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    SelectItem: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useLogInterviewOutcome: () => ({
        mutateAsync: mockMutateAsync,
        isPending: false,
    }),
}))

vi.mock("sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

describe("LogInterviewOutcomeDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("requires an outcome before submit", () => {
        render(
            <LogInterviewOutcomeDialog
                open
                onOpenChange={vi.fn()}
                surrogateId="surrogate-1"
            />
        )

        const submit = screen.getByRole("button", { name: /log outcome/i })
        expect(submit).toBeDisabled()
    })

    it("supports backdate input and submits payload", async () => {
        mockMutateAsync.mockResolvedValueOnce({
            id: "activity-1",
            activity_type: "interview_outcome_logged",
        })

        render(
            <LogInterviewOutcomeDialog
                open
                onOpenChange={vi.fn()}
                surrogateId="surrogate-1"
                appointmentId="appointment-1"
            />
        )

        fireEvent.change(screen.getByTestId("outcome-select"), {
            target: { value: "no_show" },
        })
        fireEvent.click(screen.getByLabelText(/log for a different date\/time/i))
        fireEvent.change(screen.getByLabelText(/occurred at/i), {
            target: { value: "2026-02-20T10:30" },
        })

        fireEvent.click(screen.getByRole("button", { name: /log outcome/i }))

        await waitFor(() => {
            expect(mockMutateAsync).toHaveBeenCalledTimes(1)
        })
        const call = mockMutateAsync.mock.calls[0]?.[0]
        expect(call.surrogateId).toBe("surrogate-1")
        expect(call.data.outcome).toBe("no_show")
        expect(call.data.appointment_id).toBe("appointment-1")
        expect(typeof call.data.occurred_at).toBe("string")
    })

    it("disables appointment-surface submit when appointment is unlinked", () => {
        render(
            <LogInterviewOutcomeDialog
                open
                onOpenChange={vi.fn()}
                surrogateId={null}
                appointmentId="appointment-unlinked"
            />
        )

        expect(screen.getByText(/link surrogate first/i)).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /log outcome/i })).toBeDisabled()
    })
})

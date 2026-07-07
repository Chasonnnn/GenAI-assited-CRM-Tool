import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { toast } from "sonner"

import { trackFirstContactLogged } from "@/lib/workflow-metrics"
import { LogContactAttemptDialog } from "@/components/surrogates/LogContactAttemptDialog"

const mockMutateAsync = vi.fn()

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
    DialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({
        value,
        onValueChange,
        children,
    }: {
        value?: string
        onValueChange?: (value: string) => void
        children: ReactNode
    }) => (
        <select
            data-testid="contact-outcome-select"
            value={value ?? ""}
            onChange={(event) => onValueChange?.(event.target.value)}
        >
            <option value="">Select outcome</option>
            <option value="reached">Reached</option>
            <option value="no_answer">No Answer</option>
            <option value="voicemail">Voicemail</option>
            <option value="wrong_number">Wrong Number</option>
            <option value="email_bounced">Email Bounced</option>
            {children}
        </select>
    ),
    SelectTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectValue: () => null,
    SelectContent: () => null,
    SelectItem: () => null,
}))

vi.mock("@/components/ui/checkbox", () => ({
    Checkbox: ({
        id,
        checked,
        onCheckedChange,
    }: {
        id?: string
        checked?: boolean
        onCheckedChange?: (checked: boolean) => void
    }) => (
        <input
            id={id}
            type="checkbox"
            checked={checked}
            onChange={(event) => onCheckedChange?.(event.target.checked)}
        />
    ),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useCreateContactAttempt: () => ({
        mutateAsync: mockMutateAsync,
        isPending: false,
    }),
}))

vi.mock("@/lib/workflow-metrics", () => ({
    trackFirstContactLogged: vi.fn(),
}))

vi.mock("sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

function renderDialog(onOpenChange = vi.fn()) {
    const view = render(
        <LogContactAttemptDialog
            open
            onOpenChange={onOpenChange}
            surrogateId="surrogate-1"
            surrogateName="Alex Chen"
        />
    )
    return { ...view, onOpenChange }
}

describe("LogContactAttemptDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("requires at least one method and an outcome before submit", () => {
        renderDialog()

        const submit = screen.getByRole("button", { name: "Log Attempt" })
        expect(submit).toBeDisabled()

        fireEvent.click(screen.getByRole("checkbox", { name: "Phone" }))
        expect(submit).toBeDisabled()

        fireEvent.change(screen.getByTestId("contact-outcome-select"), {
            target: { value: "no_answer" },
        })
        expect(submit).toBeEnabled()
    })

    it("requires a datetime while backdating and submits the ISO attempted time", async () => {
        mockMutateAsync.mockResolvedValueOnce({ id: "attempt-1" })
        const { container } = renderDialog()

        fireEvent.click(screen.getByRole("checkbox", { name: "Phone" }))
        fireEvent.change(screen.getByTestId("contact-outcome-select"), {
            target: { value: "voicemail" },
        })
        fireEvent.click(
            screen.getByRole("checkbox", { name: /log for a different date\/time/i })
        )
        expect(screen.getByRole("button", { name: "Log Attempt" })).toBeDisabled()

        const attemptedAtInput = container.querySelector('input[type="datetime-local"]')
        expect(attemptedAtInput).not.toBeNull()
        fireEvent.change(attemptedAtInput!, { target: { value: "2026-02-20T10:30" } })
        fireEvent.click(screen.getByRole("button", { name: "Log Attempt" }))

        await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1))
        expect(mockMutateAsync).toHaveBeenCalledWith({
            surrogateId: "surrogate-1",
            data: {
                contact_methods: ["phone"],
                outcome: "voicemail",
                notes: null,
                attempted_at: new Date("2026-02-20T10:30").toISOString(),
            },
        })
    })

    it("submits selected methods and trimmed notes, then tracks and closes on success", async () => {
        mockMutateAsync.mockResolvedValueOnce({ id: "attempt-1" })
        const { onOpenChange } = renderDialog()

        fireEvent.click(screen.getByRole("checkbox", { name: "Phone" }))
        fireEvent.click(screen.getByRole("checkbox", { name: "SMS" }))
        fireEvent.change(screen.getByTestId("contact-outcome-select"), {
            target: { value: "reached" },
        })
        fireEvent.change(screen.getByLabelText(/notes/i), {
            target: { value: "  Asked for application follow-up.  " },
        })
        fireEvent.click(screen.getByRole("button", { name: "Log Attempt" }))

        await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1))
        expect(mockMutateAsync).toHaveBeenCalledWith({
            surrogateId: "surrogate-1",
            data: {
                contact_methods: ["phone", "sms"],
                outcome: "reached",
                notes: "Asked for application follow-up.",
                attempted_at: null,
            },
        })
        expect(toast.success).toHaveBeenCalledWith("Surrogate has been marked as contacted.")
        expect(trackFirstContactLogged).toHaveBeenCalledWith("surrogate-1", {
            outcome: "reached",
            contact_methods: ["phone", "sms"],
            is_backdated: false,
        })
        expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it("does not submit stale attempted time after backdating is disabled", async () => {
        mockMutateAsync.mockResolvedValueOnce({ id: "attempt-1" })
        const { container } = renderDialog()

        fireEvent.click(screen.getByRole("checkbox", { name: "Email" }))
        fireEvent.change(screen.getByTestId("contact-outcome-select"), {
            target: { value: "email_bounced" },
        })
        const backdateToggle = screen.getByRole("checkbox", {
            name: /log for a different date\/time/i,
        })
        fireEvent.click(backdateToggle)
        const attemptedAtInput = container.querySelector('input[type="datetime-local"]')
        expect(attemptedAtInput).not.toBeNull()
        fireEvent.change(attemptedAtInput!, { target: { value: "2026-02-20T10:30" } })
        fireEvent.click(backdateToggle)
        fireEvent.click(screen.getByRole("button", { name: "Log Attempt" }))

        await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1))
        expect(mockMutateAsync.mock.calls[0]?.[0].data.attempted_at).toBeNull()
    })

    it("preserves entered data and shows an error toast when submit fails", async () => {
        mockMutateAsync.mockRejectedValueOnce(new Error("API unavailable"))
        const onOpenChange = vi.fn()
        renderDialog(onOpenChange)

        fireEvent.click(screen.getByRole("checkbox", { name: "Phone" }))
        fireEvent.change(screen.getByTestId("contact-outcome-select"), {
            target: { value: "no_answer" },
        })
        fireEvent.change(screen.getByLabelText(/notes/i), {
            target: { value: "  Still trying.  " },
        })
        fireEvent.click(screen.getByRole("button", { name: "Log Attempt" }))

        await waitFor(() => expect(toast.error).toHaveBeenCalledWith("API unavailable"))
        expect(onOpenChange).not.toHaveBeenCalled()
        expect(screen.getByRole("checkbox", { name: "Phone" })).toBeChecked()
        expect(screen.getByLabelText(/notes/i)).toHaveValue("  Still trying.  ")
        expect(trackFirstContactLogged).not.toHaveBeenCalled()
    })
})

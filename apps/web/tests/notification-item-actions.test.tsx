import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { NotificationItemActions } from "@/components/notifications/NotificationItemActions"
import type { Notification } from "@/lib/api/notifications"
import { ApiError } from "@/lib/api"

const mocks = vi.hoisted(() => ({
    resolveApproval: vi.fn(),
    approveRequest: vi.fn(),
    rejectRequest: vi.fn(),
    claimSurrogate: vi.fn(),
    approveAppointment: vi.fn(),
    cancelAppointment: vi.fn(),
    completeTask: vi.fn(),
    toastSuccess: vi.fn(),
    toastError: vi.fn(),
    permissions: new Set<string>(),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: mocks.toastSuccess, error: mocks.toastError },
}))
vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({ can: (key: string) => mocks.permissions.has(key) }),
}))
vi.mock("@/lib/hooks/use-tasks", () => ({
    useResolveWorkflowApproval: () => ({ mutateAsync: mocks.resolveApproval }),
    useCompleteTask: () => ({ mutateAsync: mocks.completeTask }),
}))
vi.mock("@/lib/hooks/use-status-change-requests", () => ({
    useApproveStatusChangeRequest: () => ({ mutateAsync: mocks.approveRequest }),
    useRejectStatusChangeRequest: () => ({ mutateAsync: mocks.rejectRequest }),
}))
vi.mock("@/lib/hooks/use-queues", () => ({
    useClaimSurrogate: () => ({ mutateAsync: mocks.claimSurrogate }),
}))
vi.mock("@/lib/hooks/use-appointments", () => ({
    useApproveAppointment: () => ({ mutateAsync: mocks.approveAppointment }),
    useCancelAppointment: () => ({ mutateAsync: mocks.cancelAppointment }),
}))

function makeNotification(overrides: Partial<Notification>): Notification {
    return {
        id: "n1",
        type: "workflow_approval_requested",
        tier: "action",
        title: "Approval needed",
        body: null,
        entity_type: "task",
        entity_id: "task-1",
        read_at: null,
        created_at: new Date().toISOString(),
        ...overrides,
    }
}

function renderActions(notification: Notification) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const utils = render(<NotificationItemActions notification={notification} />, { wrapper })
    return { ...utils, invalidate }
}

describe("NotificationItemActions", () => {
    beforeEach(() => {
        Object.values(mocks).forEach((value) => {
            if (typeof value === "function" && "mockReset" in value) value.mockReset()
        })
        mocks.permissions = new Set(["assign_surrogates", "edit_tasks"])
    })

    it("approves a workflow approval and refreshes the panel", async () => {
        mocks.resolveApproval.mockResolvedValue({})
        const { invalidate } = renderActions(makeNotification({}))

        fireEvent.click(screen.getByRole("button", { name: "Approve" }))

        await waitFor(() => expect(mocks.toastSuccess).toHaveBeenCalledWith("Approved"))
        expect(mocks.resolveApproval).toHaveBeenCalledWith({ taskId: "task-1", decision: "approve" })
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ["notifications", "list"] })
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ["notifications", "count"] })
    })

    it("asks before denying and can be cancelled", async () => {
        mocks.resolveApproval.mockResolvedValue({})
        renderActions(makeNotification({}))

        fireEvent.click(screen.getByRole("button", { name: "Deny" }))
        expect(screen.getByText("Deny this action?")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
        expect(mocks.resolveApproval).not.toHaveBeenCalled()

        fireEvent.click(screen.getByRole("button", { name: "Deny" }))
        fireEvent.click(screen.getByRole("button", { name: "Deny" }))
        await waitFor(() => expect(mocks.toastSuccess).toHaveBeenCalledWith("Denied"))
        expect(mocks.resolveApproval).toHaveBeenCalledWith({ taskId: "task-1", decision: "deny" })
    })

    it("acts on the pending status change request, not the record", async () => {
        mocks.rejectRequest.mockResolvedValue({})
        renderActions(
            makeNotification({
                type: "status_change_requested",
                entity_type: "surrogate",
                entity_id: "s-1",
                request_id: "req-1",
            })
        )

        fireEvent.click(screen.getByRole("button", { name: "Reject" }))
        fireEvent.click(screen.getByRole("button", { name: "Reject" }))

        await waitFor(() => expect(mocks.rejectRequest).toHaveBeenCalledWith({ requestId: "req-1" }))
    })

    it("offers no status change buttons without a pending request", () => {
        const { container } = renderActions(
            makeNotification({ type: "status_change_requested", entity_type: "surrogate", request_id: null })
        )
        expect(container).toBeEmptyDOMElement()
    })

    it("claims, approves appointments, and completes tasks", async () => {
        mocks.claimSurrogate.mockResolvedValue({})
        const claim = renderActions(
            makeNotification({ type: "surrogate_claim_available", entity_type: "surrogate", entity_id: "s-2" })
        )
        fireEvent.click(screen.getByRole("button", { name: "Claim" }))
        await waitFor(() => expect(mocks.claimSurrogate).toHaveBeenCalledWith("s-2"))
        claim.unmount()

        mocks.approveAppointment.mockResolvedValue({})
        const appointment = renderActions(
            makeNotification({ type: "appointment_requested", entity_type: "appointment", entity_id: "a-1" })
        )
        fireEvent.click(screen.getByRole("button", { name: "Approve" }))
        await waitFor(() =>
            expect(mocks.approveAppointment).toHaveBeenCalledWith({ appointmentId: "a-1" })
        )
        expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument()
        appointment.unmount()

        mocks.completeTask.mockResolvedValue({})
        renderActions(makeNotification({ type: "task_overdue", entity_id: "task-3" }))
        fireEvent.click(screen.getByRole("button", { name: "Complete" }))
        await waitFor(() => expect(mocks.completeTask).toHaveBeenCalledWith("task-3"))
    })

    it("hides actions the viewer lacks permission for", () => {
        mocks.permissions = new Set()
        const claim = renderActions(
            makeNotification({ type: "surrogate_claim_available", entity_type: "surrogate", entity_id: "s-2" })
        )
        expect(claim.container).toBeEmptyDOMElement()
        claim.unmount()

        const task = renderActions(makeNotification({ type: "task_assigned", entity_id: "task-4" }))
        expect(task.container).toBeEmptyDOMElement()
    })

    it("shows the API message when the action fails and re-enables the buttons", async () => {
        mocks.claimSurrogate.mockRejectedValue(
            new ApiError(409, "Conflict", "Surrogate already claimed")
        )
        renderActions(
            makeNotification({ type: "surrogate_claim_available", entity_type: "surrogate", entity_id: "s-2" })
        )

        fireEvent.click(screen.getByRole("button", { name: "Claim" }))

        await waitFor(() => expect(mocks.toastError).toHaveBeenCalledWith("Surrogate already claimed"))
        expect(mocks.toastSuccess).not.toHaveBeenCalled()
        expect(screen.getByRole("button", { name: "Claim" })).not.toBeDisabled()
    })

    it("renders nothing for types without an inline action", () => {
        const { container } = renderActions(
            makeNotification({ type: "match_conflict", entity_type: "match", entity_id: "m-1" })
        )
        expect(container).toBeEmptyDOMElement()
    })
})

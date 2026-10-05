"use client"

import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
import type { Notification } from "@/lib/api/notifications"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { useApproveAppointment, useCancelAppointment } from "@/lib/hooks/use-appointments"
import { notificationKeys } from "@/lib/hooks/use-notifications"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import {
    useApproveStatusChangeRequest,
    useRejectStatusChangeRequest,
} from "@/lib/hooks/use-status-change-requests"
import { useCompleteTask, useResolveWorkflowApproval } from "@/lib/hooks/use-tasks"

type ItemAction = {
    label: string
    run: () => Promise<unknown>
    success: string
    failure: string
    /** Declines and rejections ask once before running. */
    confirm?: string
}

type ItemActions = { primary: ItemAction; secondary?: ItemAction }

function useItemActions(notification: Notification): ItemActions | null {
    const { can } = usePermissionCheck()
    const resolveApproval = useResolveWorkflowApproval()
    const approveRequest = useApproveStatusChangeRequest()
    const rejectRequest = useRejectStatusChangeRequest()
    const approveAppointment = useApproveAppointment()
    const cancelAppointment = useCancelAppointment()
    const completeTask = useCompleteTask()

    const entityId = notification.entity_id
    switch (notification.type) {
        case "workflow_approval_requested":
            if (!entityId) return null
            return {
                primary: {
                    label: "Approve",
                    run: () => resolveApproval.mutateAsync({ taskId: entityId, decision: "approve" }),
                    success: "Approved",
                    failure: "Couldn't approve",
                },
                secondary: {
                    label: "Deny",
                    run: () => resolveApproval.mutateAsync({ taskId: entityId, decision: "deny" }),
                    success: "Denied",
                    failure: "Couldn't deny",
                    confirm: "Deny this action?",
                },
            }
        case "status_change_requested": {
            const requestId = notification.request_id
            if (!requestId) return null
            return {
                primary: {
                    label: "Approve",
                    run: () => approveRequest.mutateAsync(requestId),
                    success: "Request approved",
                    failure: "Couldn't approve the request",
                },
                secondary: {
                    label: "Reject",
                    run: () => rejectRequest.mutateAsync({ requestId }),
                    success: "Request rejected",
                    failure: "Couldn't reject the request",
                    confirm: "Reject this request?",
                },
            }
        }
        case "appointment_requested":
            if (!entityId) return null
            return {
                primary: {
                    label: "Approve",
                    run: () => approveAppointment.mutateAsync({ appointmentId: entityId }),
                    success: "Appointment approved",
                    failure: "Couldn't approve the appointment",
                },
                secondary: {
                    label: "Decline",
                    run: () => cancelAppointment.mutateAsync({ appointmentId: entityId }),
                    success: "Appointment declined",
                    failure: "Couldn't decline the appointment",
                    confirm: "Decline this appointment?",
                },
            }
        case "task_assigned":
        case "task_overdue":
            if (!entityId || !can("edit_tasks")) return null
            return {
                primary: {
                    label: "Complete",
                    run: () => completeTask.mutateAsync(entityId),
                    success: "Task completed",
                    failure: "Couldn't complete the task",
                },
            }
        default:
            return null
    }
}

export function NotificationItemActions({ notification }: { notification: Notification }) {
    const queryClient = useQueryClient()
    const actions = useItemActions(notification)
    const [running, setRunning] = useState<string | null>(null)
    const [confirming, setConfirming] = useState<ItemAction | null>(null)

    if (!actions) return null

    const run = async (action: ItemAction) => {
        setConfirming(null)
        setRunning(action.label)
        try {
            await action.run()
            toast.success(action.success)
            // The item leaves the Action needed list once its work is done; keep the row
            // busy until the refetch removes it.
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: [...notificationKeys.all, "list"] }),
                queryClient.invalidateQueries({ queryKey: notificationKeys.count() }),
            ])
        } catch (error) {
            const message = getActionErrorMessage(error, action.failure)
            if (message) toast.error(message)
            // A conflict usually means someone else already handled it.
            void queryClient.invalidateQueries({ queryKey: [...notificationKeys.all, "list"] })
        } finally {
            setRunning(null)
        }
    }

    const handleClick = (action: ItemAction) => {
        if (action.confirm) {
            setConfirming(action)
            return
        }
        void run(action)
    }

    if (confirming) {
        return (
            <div className="flex items-center gap-2 px-4 pb-3" role="group" aria-label={confirming.confirm}>
                <span className="mr-auto text-xs text-muted-foreground">{confirming.confirm}</span>
                <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                    Cancel
                </Button>
                <Button variant="destructive" size="sm" onClick={() => void run(confirming)}>
                    {confirming.label}
                </Button>
            </div>
        )
    }

    const busy = running !== null
    return (
        <div className="flex items-center gap-2 px-4 pb-3">
            {[actions.primary, actions.secondary].map((action, index) =>
                action ? (
                    <Button
                        key={action.label}
                        variant={index === 0 ? "default" : "outline"}
                        size="sm"
                        disabled={busy}
                        aria-busy={running === action.label}
                        onClick={() => handleClick(action)}
                    >
                        {running === action.label && <Spinner className="size-3" aria-hidden="true" />}
                        {action.label}
                    </Button>
                ) : null
            )}
        </div>
    )
}

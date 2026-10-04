"use client"

import { useEffect, useRef } from "react"

export type TaskFocusTarget =
    | "approvals"
    | "tasks"
    | "overdue"
    | "today"
    | "tomorrow"
    | "this-week"
    | "later"
    | "no-date"

type TaskFocusNavigationOptions = {
    focusTarget: TaskFocusTarget | null
    // Approval row to scroll to inside the approvals section.
    highlightedApprovalId?: string | null
    activeView: "list" | "calendar"
    isLoading: boolean
    loadingApprovals: boolean
    loadingStatusRequests: boolean
    loadingImportApprovals: boolean
}

export function useTaskFocusNavigation({
    focusTarget,
    highlightedApprovalId = null,
    activeView,
    isLoading,
    loadingApprovals,
    loadingStatusRequests,
    loadingImportApprovals,
}: TaskFocusNavigationOptions) {
    const handledFocusRef = useRef<string | null>(null)

    useEffect(() => {
        if (!focusTarget) {
            handledFocusRef.current = null
            return
        }
        const focusKey = `${focusTarget}:${highlightedApprovalId ?? ""}`
        if (handledFocusRef.current === focusKey) return
        if (focusTarget !== "approvals" && activeView !== "list") return
        if (isLoading) return
        if (
            focusTarget === "approvals" &&
            (loadingApprovals || loadingStatusRequests || loadingImportApprovals)
        ) {
            return
        }

        const targetId =
            focusTarget === "approvals"
                ? "tasks-approvals"
                : focusTarget === "tasks"
                    ? "tasks-list"
                    : `tasks-${focusTarget}`
        const highlighted =
            focusTarget === "approvals" && highlightedApprovalId
                ? document.getElementById(`approval-${highlightedApprovalId}`)
                : null
        const target =
            highlighted ||
            document.getElementById(targetId) ||
            document.getElementById("tasks-list")
        if (!target) return

        target.scrollIntoView({ behavior: "smooth", block: highlighted ? "center" : "start" })
        if (focusTarget !== "approvals") {
            localStorage.setItem("tasks-view", "list")
        }
        handledFocusRef.current = focusKey
    }, [
        focusTarget,
        highlightedApprovalId,
        activeView,
        isLoading,
        loadingApprovals,
        loadingStatusRequests,
        loadingImportApprovals,
    ])
}

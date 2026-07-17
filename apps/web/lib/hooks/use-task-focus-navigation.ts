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
    activeView: "list" | "calendar"
    isLoading: boolean
    loadingApprovals: boolean
    loadingStatusRequests: boolean
    loadingImportApprovals: boolean
}

export function useTaskFocusNavigation({
    focusTarget,
    activeView,
    isLoading,
    loadingApprovals,
    loadingStatusRequests,
    loadingImportApprovals,
}: TaskFocusNavigationOptions) {
    const handledFocusRef = useRef<TaskFocusTarget | null>(null)

    useEffect(() => {
        if (!focusTarget) {
            handledFocusRef.current = null
            return
        }
        if (handledFocusRef.current === focusTarget) return
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
        const target =
            document.getElementById(targetId) || document.getElementById("tasks-list")
        if (!target) return

        target.scrollIntoView({ behavior: "smooth", block: "start" })
        if (focusTarget !== "approvals") {
            localStorage.setItem("tasks-view", "list")
        }
        handledFocusRef.current = focusTarget
    }, [
        focusTarget,
        activeView,
        isLoading,
        loadingApprovals,
        loadingStatusRequests,
        loadingImportApprovals,
    ])
}

import { useSyncExternalStore } from "react"

export type SurrogateTasksViewMode = "list" | "calendar"

const DEFAULT_VIEW_MODE: SurrogateTasksViewMode = "list"
const VIEW_MODE_CHANGE_EVENT = "surrogate-tasks-view-mode-change"

function getStorageKey(surrogateId: string): string {
    return `surrogate-tasks-view-${surrogateId}`
}

function toViewMode(value: string | null): SurrogateTasksViewMode {
    return value === "calendar" || value === "list" ? value : DEFAULT_VIEW_MODE
}

function readStoredViewMode(surrogateId: string): SurrogateTasksViewMode {
    if (typeof window === "undefined") return DEFAULT_VIEW_MODE
    return toViewMode(window.localStorage.getItem(getStorageKey(surrogateId)))
}

function subscribeToViewModeChanges(onStoreChange: () => void) {
    if (typeof window === "undefined") return () => undefined

    window.addEventListener("storage", onStoreChange)
    window.addEventListener(VIEW_MODE_CHANGE_EVENT, onStoreChange)

    return () => {
        window.removeEventListener("storage", onStoreChange)
        window.removeEventListener(VIEW_MODE_CHANGE_EVENT, onStoreChange)
    }
}

export function useSurrogateTaskViewMode(
    surrogateId: string,
): readonly [SurrogateTasksViewMode, (mode: SurrogateTasksViewMode) => void] {
    const viewMode = useSyncExternalStore(
        subscribeToViewModeChanges,
        () => readStoredViewMode(surrogateId),
        () => DEFAULT_VIEW_MODE,
    )

    const setViewMode = (mode: SurrogateTasksViewMode) => {
        if (typeof window === "undefined") return
        window.localStorage.setItem(getStorageKey(surrogateId), mode)
        window.dispatchEvent(new Event(VIEW_MODE_CHANGE_EVENT))
    }

    return [viewMode, setViewMode] as const
}

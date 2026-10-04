// No "use client": the server page parses the `tab` query parameter with this too.
export const WORKSPACE_TABS = ["edit", "preview", "settings", "routing", "submissions"] as const
export type WorkspaceTab = (typeof WORKSPACE_TABS)[number]

export function parseWorkspaceTab(value: string | null | undefined): WorkspaceTab | undefined {
    return WORKSPACE_TABS.find((tab) => tab === value)
}

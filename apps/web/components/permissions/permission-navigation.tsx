"use client"

import Link from "@/components/app-link"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type PermissionTab = "roles" | "people" | "check" | "upgrade"

export function PermissionNavigation({ current, capabilities, showUpgrade = false, disabled = false, onSelect }: {
    current: PermissionTab
    capabilities?: Record<string, boolean> | undefined
    showUpgrade?: boolean
    disabled?: boolean
    onSelect?: (tab: PermissionTab) => void
}) {
    const tabs = [
        { key: "roles" as const, label: "Roles", href: "/settings/team/roles" as const },
        ...(capabilities?.can_manage_members ? [{ key: "people" as const, label: "People", href: "/settings/team" as const }] : []),
        ...(capabilities?.can_manage_roles ? [{ key: "check" as const, label: "Check access", href: "/settings/team/roles?tab=check" as const }] : []),
        ...(showUpgrade && capabilities?.can_activate_policy ? [{ key: "upgrade" as const, label: "Review upgrade", href: "/settings/team/roles?tab=upgrade" as const }] : []),
    ]
    return <nav aria-label="Permission settings" className="flex max-w-full gap-6 overflow-x-auto text-sm">
        {tabs.map((tab) => {
            const className = cn("h-auto shrink-0 rounded-none border-b-2 px-0 py-3 font-medium hover:bg-transparent hover:text-primary disabled:opacity-40 dark:hover:bg-transparent", current === tab.key ? "border-primary text-primary" : "border-transparent text-muted-foreground")
            return onSelect && tab.key !== "people" ? <Button key={tab.key} variant="ghost" disabled={disabled && current !== tab.key} onClick={() => onSelect(tab.key)} aria-current={current === tab.key ? "page" : undefined} className={className}>{tab.label}</Button> : <Link key={tab.key} href={tab.href} className={className} aria-current={current === tab.key ? "page" : undefined} aria-disabled={disabled} onClick={(event) => { if (disabled) event.preventDefault() }}>{tab.label}</Link>
        })}
    </nav>
}

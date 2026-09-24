import type { PermissionPresentation, PermissionTopic, RoleDetail, RolePermission } from "@/lib/api/permissions"

export const PERMISSION_TOPICS: PermissionTopic[] = ["Surrogates", "Donors", "Intended Parents", "Operations", "Administration"]

const SECTION_ORDER = ["Records", "Progress & ownership", "Notes", "Matches", "Workflows", "Templates", "Campaigns", "Tasks", "Communications", "Inbox", "Appointments", "Forms", "Reports", "Team", "Organization", "Integrations", "AI", "Compliance", "System"]
const ACTION_ORDER: Record<string, string[]> = {
    Records: ["View", "Create", "Edit", "Archive", "Delete", "Import"],
    "Progress & ownership": ["Change status", "Approve", "Assign", "Approve status corrections"],
}

export function isIncludedPermission(permission: PermissionPresentation | undefined, activePolicy: boolean) {
    return activePolicy && permission?.is_default === true
}

export function groupRolePermissions(detail: RoleDetail | undefined) {
    const topics = Object.fromEntries(PERMISSION_TOPICS.map((topic) => [topic, {}])) as Record<PermissionTopic, Record<string, RolePermission[]>>
    for (const [category, permissions] of Object.entries(detail?.permissions_by_category ?? {})) {
        for (const permission of permissions) {
            if (isIncludedPermission(permission, detail?.policy_version === 2)) continue
            const topic = permission.topic ?? (PERMISSION_TOPICS.includes(category as PermissionTopic) ? category as PermissionTopic : "Administration")
            const section = permission.section ?? (category === topic ? "Actions" : category)
            ;(topics[topic][section] ??= []).push(permission)
        }
    }
    for (const topic of PERMISSION_TOPICS) {
        for (const [section, rows] of Object.entries(topics[topic])) {
            const order = ACTION_ORDER[section]
            if (!order) continue
            const rank = (row: RolePermission) => {
                const index = order.indexOf(row.short_label || row.label)
                return index < 0 ? order.length : index
            }
            rows.sort((left, right) => rank(left) - rank(right))
        }
        topics[topic] = Object.fromEntries(Object.entries(topics[topic]).sort(([left], [right]) => {
            const leftIndex = SECTION_ORDER.indexOf(left)
            const rightIndex = SECTION_ORDER.indexOf(right)
            return (leftIndex < 0 ? SECTION_ORDER.length : leftIndex) - (rightIndex < 0 ? SECTION_ORDER.length : rightIndex) || left.localeCompare(right)
        }))
    }
    return topics
}

export function permissionPreviewLabel(permission: RolePermission, rows: RolePermission[]) {
    const label = permission.short_label || permission.label
    const section = permission.section
    const ambiguous = rows.some((other) => other.section !== section && (other.short_label || other.label) === label)
    if (!section || section === "Records" || !ambiguous) return label
    return `${label} ${section === section.toUpperCase() ? section : section.toLowerCase()}`
}

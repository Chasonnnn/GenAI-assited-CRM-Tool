// Display names for organization roles. Kept outside the permission components so public pages,
// such as the invitation page, can label a role without loading those components.
export const ROLE_LABELS: Record<string, string> = {
    intake_specialist: "Intake Specialist",
    case_manager: "Case Manager",
    operations: "Operations",
    admin: "Admin",
    developer: "Dev",
}

export function getRoleLabel(role: string | null | undefined): string {
    return (role && ROLE_LABELS[role]) || "Unknown role"
}

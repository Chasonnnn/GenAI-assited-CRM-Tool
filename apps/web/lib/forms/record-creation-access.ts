import type { FormLeadKind } from "@/lib/api/forms"

export function canCreateIntakeRecord(
    access: { policy_version?: number; permissions: string[] } | undefined,
    kind: FormLeadKind,
): boolean {
    const module = kind === "egg_donor" || kind === "sperm_donor" ? "donors" : "surrogates"
    const action = access?.policy_version === 2 ? "create" : "edit"
    return access?.permissions.includes(`${action}_${module}`) === true
}

import type { Route } from "next"

export type TaskRelatedRecordSelection =
    | "none"
    | `surrogate:${string}`
    | `intended_parent:${string}`
    | `donor:${string}`

export type TaskRelatedRecordFields = {
    surrogate_id?: string | null
    surrogate_number?: string | null
    intended_parent_id?: string | null
    donor_id?: string | null
    donor_number?: string | null
    donor_type?: "egg" | "sperm" | null
    donor_name?: string | null
}

export type TaskRelatedRecordPresentation = {
    kind: "surrogate" | "intended_parent" | "donor"
    id: string
    href: Route | null
    label: string
}

export type TaskRelatedRecordPayload = {
    surrogate_id: string | null
    intended_parent_id: string | null
    donor_id: string | null
}

export function getTaskRelatedRecords(
    task: TaskRelatedRecordFields,
): TaskRelatedRecordPresentation[] {
    const records: TaskRelatedRecordPresentation[] = []

    if (task.surrogate_id) {
        const available = Boolean(task.surrogate_number)
        records.push({
            kind: "surrogate",
            id: task.surrogate_id,
            href: available ? `/surrogates/${task.surrogate_id}` as Route : null,
            label: available ? `Surrogate #${task.surrogate_number}` : "Surrogate unavailable",
        })
    }

    if (task.intended_parent_id) {
        records.push({
            kind: "intended_parent",
            id: task.intended_parent_id,
            href: `/intended-parents/${task.intended_parent_id}` as Route,
            label: "Intended Parent",
        })
    }

    if (task.donor_id) {
        const available = Boolean(task.donor_number && task.donor_type)
        const donorTypeLabel = task.donor_type === "egg" ? "Egg Donor" : "Sperm Donor"
        records.push({
            kind: "donor",
            id: task.donor_id,
            href: available ? `/donors/${task.donor_id}` as Route : null,
            label: available ? `${donorTypeLabel} ${task.donor_number}` : "Donor unavailable",
        })
    }

    return records
}

export function getTaskRelatedRecordSelection(
    task: Pick<TaskRelatedRecordFields, "surrogate_id" | "intended_parent_id" | "donor_id">,
): TaskRelatedRecordSelection {
    if (task.donor_id) return `donor:${task.donor_id}`
    if (task.surrogate_id) return `surrogate:${task.surrogate_id}`
    if (task.intended_parent_id) return `intended_parent:${task.intended_parent_id}`
    return "none"
}

export function toTaskRelatedRecordPayload(
    selection: TaskRelatedRecordSelection,
): TaskRelatedRecordPayload {
    const payload: TaskRelatedRecordPayload = {
        surrogate_id: null,
        intended_parent_id: null,
        donor_id: null,
    }
    if (selection === "none") return payload

    const separatorIndex = selection.indexOf(":")
    const kind = selection.slice(0, separatorIndex)
    const id = selection.slice(separatorIndex + 1)
    if (kind === "surrogate") payload.surrogate_id = id
    if (kind === "intended_parent") payload.intended_parent_id = id
    if (kind === "donor") payload.donor_id = id
    return payload
}

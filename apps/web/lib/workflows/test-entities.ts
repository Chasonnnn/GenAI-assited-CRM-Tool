/** Record search for workflow dry runs, shared by the Automation list and the editor. */

import { getAppointments } from "@/lib/api/appointments"
import { listDonors } from "@/lib/api/donors"
import { listMatches, type ListMatchesParams } from "@/lib/api/matches"
import { globalSearch } from "@/lib/api/search"
import { getSurrogates, type SurrogateListParams } from "@/lib/api/surrogates"
import { getTasks, type TaskListParams } from "@/lib/api/tasks"
import type { WorkflowSubjectType } from "@/lib/api/workflows"

export const ENTITY_LABELS: Record<string, string> = {
    surrogate: "Surrogate ID",
    form_submission: "Form Submission ID",
    intake_lead: "Intake Lead ID",
    task: "Task ID",
    match: "Match ID",
    appointment: "Appointment ID",
    note: "Note ID",
    document: "Document ID",
    egg_donor: "Egg Donor ID",
    sperm_donor: "Sperm Donor ID",
}

const DONOR_SUBJECT_TYPES = new Set<string>(["egg_donor", "sperm_donor"])

/** The record type a dry run reads; mirrors workflow_dry_run_service.expected_entity_type. */
export function getTestEntityType(
    subjectType: WorkflowSubjectType,
    triggerType: string,
    triggerEntityTypes: Record<string, string> | undefined,
): string {
    if (DONOR_SUBJECT_TYPES.has(subjectType)) return subjectType
    return triggerEntityTypes?.[triggerType] ?? "surrogate"
}

export type TestEntitySuggestion = { id: string; label: string; meta?: string }

const buildTestEntitySuggestion = (
    id: string,
    label: string,
    meta?: string | null
): TestEntitySuggestion => (meta == null ? { id, label } : { id, label, meta })

export async function fetchTestEntities(
    entityType: string,
    query: string
): Promise<TestEntitySuggestion[]> {
    if (entityType === "egg_donor" || entityType === "sperm_donor") {
        const response = await listDonors({
            donor_type: entityType === "egg_donor" ? "egg" : "sperm",
            per_page: 5,
            page: 1,
            ...(query.trim() ? { q: query.trim() } : {}),
        })
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                `${item.donor_number} — ${item.full_name}`,
                item.status_label,
            ),
        )
    }
    if (entityType === "surrogate") {
        const params: SurrogateListParams = {
            per_page: 5,
            sort_by: "created_at",
            sort_order: "desc",
        }
        if (query.trim()) params.q = query.trim()
        const response = await getSurrogates(params)
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                `${item.surrogate_number} • ${item.full_name}`,
                item.status_label ?? null
            )
        )
    }
    if (entityType === "task") {
        const params: TaskListParams = {
            per_page: 5,
            exclude_approvals: true,
        }
        if (query.trim()) params.q = query.trim()
        const response = await getTasks(params)
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                item.title,
                item.surrogate_number ?? null
            )
        )
    }
    if (entityType === "match") {
        const params: ListMatchesParams = {
            per_page: 5,
        }
        if (query.trim()) params.q = query.trim()
        const response = await listMatches(params)
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                item.match_number,
                item.surrogate_name ?? item.ip_name ?? null
            )
        )
    }
    if (entityType === "appointment") {
        const now = new Date()
        const end = new Date(now.getTime() + 1000 * 60 * 60 * 24 * 30)
        const response = await getAppointments({
            per_page: 5,
            date_start: now.toISOString(),
            date_end: end.toISOString(),
        })
        return response.items.map((item) =>
            buildTestEntitySuggestion(
                item.id,
                item.appointment_type_name ?? "Appointment",
                item.surrogate_number ?? item.intended_parent_name ?? null
            )
        )
    }
    if (entityType === "note") {
        if (!query.trim()) return []
        const response = await globalSearch({ q: query, types: "note", limit: 5 })
        return response.results.map((result) =>
            buildTestEntitySuggestion(
                result.entity_id,
                result.title,
                result.surrogate_name ?? null
            )
        )
    }
    if (entityType === "document") {
        if (!query.trim()) return []
        const response = await globalSearch({ q: query, types: "attachment", limit: 5 })
        return response.results.map((result) =>
            buildTestEntitySuggestion(
                result.entity_id,
                result.title,
                result.surrogate_name ?? null
            )
        )
    }
    if (entityType === "intake_lead") {
        return []
    }
    if (entityType === "form_submission") {
        return []
    }
    return []
}

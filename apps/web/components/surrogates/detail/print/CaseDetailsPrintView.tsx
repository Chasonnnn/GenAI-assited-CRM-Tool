import { format, isBefore, parseISO, startOfToday } from "date-fns"
import type { ReactNode } from "react"
import { computeBmi, formatDate, formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"
import { EMPTY_VALUE_TEXT } from "@/components/ui/empty-value"
import { formatRace } from "@/lib/formatters"
import { getSurrogateSourceLabel } from "@/lib/surrogate-source-labels"
import type { SurrogateCaseDetailsExportView } from "@/lib/api/surrogates"
import type { TaskListItem } from "@/lib/api/tasks"
import type { MedicalRecord } from "@/lib/types/medical-record"
import {
    MEDICAL_RECORD_SECTIONS,
    formatRecordDate,
    sectionConfig,
} from "@/components/medical-records/medical-record-sections"

interface CaseDetailsPrintViewProps {
    data: SurrogateCaseDetailsExportView
}

function display(value: string | number | null | undefined, fallback: string = EMPTY_VALUE_TEXT): string {
    if (value === null || value === undefined || value === "") return fallback
    return String(value)
}

function formatDateOrDash(value: string | null | undefined): string {
    if (!value) return EMPTY_VALUE_TEXT
    return formatDate(value)
}

function formatAddress(parts: Array<string | null | undefined>): string {
    const tokens = parts.flatMap((part) => {
        const token = (part || "").trim()
        return token ? [token] : []
    })
    return tokens.length > 0 ? tokens.join(", ") : EMPTY_VALUE_TEXT
}

function humanizeActivityType(value: string): string {
    return value
        .replace(/_/g, " ")
        .replace(/\b\w/g, (match) => match.toUpperCase())
}

function taskGroups(tasks: TaskListItem[]) {
    const today = startOfToday()
    const pending: Array<{ task: TaskListItem; dueDate: Date }> = []
    for (const task of tasks) {
        if (task.is_completed || !task.due_date) continue
        const dueDate = parseISO(task.due_date)
        if (!Number.isNaN(dueDate.getTime())) {
            pending.push({ task, dueDate })
        }
    }

    const overdue: TaskListItem[] = []
    const upcoming: TaskListItem[] = []
    for (const entry of pending.toSorted((a, b) => a.dueDate.getTime() - b.dueDate.getTime())) {
        if (isBefore(entry.dueDate, today)) {
            if (overdue.length < 3) overdue.push(entry.task)
        } else if (upcoming.length < 3) {
            upcoming.push(entry.task)
        }
    }

    return { overdue, upcoming }
}

function dueLabel(task: TaskListItem): string {
    if (!task.due_date) return EMPTY_VALUE_TEXT
    return format(parseISO(task.due_date), "MMM d, yyyy")
}

function Section({
    title,
    children,
}: {
    title: string
    children: ReactNode
}) {
    return (
        <section className="rounded-lg border bg-card p-4 print:break-inside-avoid print:page-break-inside-avoid">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {title}
            </h3>
            <div className="space-y-2">{children}</div>
        </section>
    )
}

function Row({ label, value }: { label: string; value: string }) {
    return (
        <div className="grid grid-cols-[160px_1fr] gap-3 border-b border-border/60 pb-2 text-sm last:border-b-0">
            <span className="text-muted-foreground">{label}</span>
            <span>{value}</span>
        </div>
    )
}

function MedicalRecordPrintSection({ record }: { record: MedicalRecord }) {
    const config = sectionConfig(record.section)
    const rows: ReactNode[] = []
    for (const field of config.fields) {
        if (field.key === "address_line2" || field.cityStateZip) continue
        if (field.key === "address_line1") {
            rows.push(
                <Row
                    key="address"
                    label="Address"
                    value={formatAddress([
                        record.address_line1,
                        record.address_line2,
                        record.city,
                        record.state,
                        record.postal,
                    ])}
                />,
            )
            continue
        }
        const value = field.type === "date" ? formatRecordDate(record[field.key]) : record[field.key]
        rows.push(<Row key={field.key} label={field.label} value={display(value)} />)
    }
    return <Section title={config.title}>{rows}</Section>
}

export function CaseDetailsPrintView({ data }: CaseDetailsPrintViewProps) {
    const surrogate = data.surrogate
    const medicalRecords = MEDICAL_RECORD_SECTIONS.flatMap((config) =>
        data.medical_records.filter((record) => record.section === config.key),
    )
    const bmi = computeBmi(surrogate.height_ft, surrogate.weight_lb ?? null)
    const { overdue, upcoming } = taskGroups(data.tasks)

    return (
        <div data-case-details-print="ready" className="min-h-screen bg-background text-foreground">
            <div className="mx-auto max-w-[900px] space-y-4 px-4 py-6 print:px-0 print:py-0">
                <header className="rounded-lg border bg-card p-4">
                    <h1 className="text-2xl font-semibold tracking-tight">Case Details</h1>
                    <p className="mt-1 text-base">{display(surrogate.full_name)}</p>
                </header>

                <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
                    <div className="space-y-4">
                        <Section title="Contact Information">
                            <Row label="Name" value={display(surrogate.full_name)} />
                            <Row label="Email" value={display(surrogate.email)} />
                            <Row label="Phone" value={display(surrogate.phone)} />
                            <Row label="State" value={display(surrogate.state)} />
                            <Row label="Source" value={getSurrogateSourceLabel(surrogate.source)} />
                            <Row label="Created" value={formatDateOrDash(surrogate.created_at)} />
                        </Section>

                        <Section title="Demographics">
                            <Row label="Date of Birth" value={formatDateOrDash(surrogate.date_of_birth)} />
                            <Row label="Race" value={display(formatRace(surrogate.race))} />
                            <Row label="Height" value={formatHeight(surrogate.height_ft)} />
                            <Row
                                label="Weight"
                                value={surrogate.weight_lb ? `${surrogate.weight_lb} lb` : EMPTY_VALUE_TEXT}
                            />
                            <Row label="BMI" value={bmi !== null ? String(bmi) : EMPTY_VALUE_TEXT} />
                        </Section>

                        {medicalRecords.map((record) => (
                            <MedicalRecordPrintSection key={record.id} record={record} />
                        ))}
                    </div>

                    <div className="space-y-4">
                        {data.show_pregnancy && (
                            <Section title="Pregnancy Tracker">
                                <Row
                                    label="Transferred Date"
                                    value={formatDateOrDash(surrogate.pregnancy_start_date)}
                                />
                                <Row label="Due Date" value={formatDateOrDash(surrogate.pregnancy_due_date)} />
                                <Row
                                    label="Actual Delivery Date"
                                    value={formatDateOrDash(surrogate.actual_delivery_date)}
                                />
                                <Row label="Gender" value={display(surrogate.delivery_baby_gender)} />
                                <Row label="Weight" value={display(surrogate.delivery_baby_weight)} />
                            </Section>
                        )}

                        <Section title="Activity">
                            {data.activities.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No activity yet.</p>
                            ) : (
                                <div className="space-y-2">
                                    {data.activities.map((activity) => (
                                        <div
                                            key={activity.id}
                                            className="rounded border border-border/60 p-2 text-sm"
                                        >
                                            <div className="font-medium">
                                                {humanizeActivityType(activity.activity_type)}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                                {formatDateOrDash(activity.created_at)}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div className="mt-3 space-y-2">
                                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                    Overdue Tasks
                                </h4>
                                {overdue.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">None</p>
                                ) : (
                                    overdue.map((task) => (
                                        <div key={task.id} className="text-sm">
                                            {task.title} ({dueLabel(task)})
                                        </div>
                                    ))
                                )}
                            </div>

                            <div className="mt-3 space-y-2">
                                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                    Upcoming Tasks
                                </h4>
                                {upcoming.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">None</p>
                                ) : (
                                    upcoming.map((task) => (
                                        <div key={task.id} className="text-sm">
                                            {task.title} ({dueLabel(task)})
                                        </div>
                                    ))
                                )}
                            </div>
                        </Section>

                        <Section title="Eligibility Checklist">
                            {(surrogate.eligibility_checklist ?? []).map((item) => (
                                <Row
                                    key={item.key}
                                    label={item.label}
                                    value={item.display_value}
                                />
                            ))}
                        </Section>
                    </div>
                </div>
            </div>
        </div>
    )
}

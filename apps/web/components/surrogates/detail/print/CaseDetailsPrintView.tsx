import { format, isBefore, parseISO, startOfToday } from "date-fns"
import type { ReactNode } from "react"
import { computeBmi, formatDate, formatHeight } from "@/components/surrogates/detail/surrogate-detail-utils"
import { formatRace } from "@/lib/formatters"
import type { SurrogateCaseDetailsExportView } from "@/lib/api/surrogates"
import type { TaskListItem } from "@/lib/api/tasks"

interface CaseDetailsPrintViewProps {
    data: SurrogateCaseDetailsExportView
}

function display(value: string | number | null | undefined, fallback: string = "-"): string {
    if (value === null || value === undefined || value === "") return fallback
    return String(value)
}

function yesNo(value: boolean | null | undefined): string {
    if (value === true) return "Yes"
    if (value === false) return "No"
    return "-"
}

function formatDateOrDash(value: string | null | undefined): string {
    if (!value) return "-"
    return formatDate(value)
}

function formatAddress(parts: Array<string | null | undefined>): string {
    const tokens = parts.map((part) => (part || "").trim()).filter(Boolean)
    return tokens.length > 0 ? tokens.join(", ") : "-"
}

function humanizeActivityType(value: string): string {
    return value
        .replace(/_/g, " ")
        .replace(/\b\w/g, (match) => match.toUpperCase())
}

function taskGroups(tasks: TaskListItem[]) {
    const today = startOfToday()
    const pending = tasks
        .filter((task) => !task.is_completed && task.due_date)
        .map((task) => ({
            task,
            dueDate: parseISO(task.due_date as string),
        }))
        .filter((entry) => !Number.isNaN(entry.dueDate.getTime()))

    const overdue = pending
        .filter((entry) => isBefore(entry.dueDate, today))
        .sort((a, b) => a.dueDate.getTime() - b.dueDate.getTime())
        .map((entry) => entry.task)
        .slice(0, 3)

    const upcoming = pending
        .filter((entry) => !isBefore(entry.dueDate, today))
        .sort((a, b) => a.dueDate.getTime() - b.dueDate.getTime())
        .map((entry) => entry.task)
        .slice(0, 3)

    return { overdue, upcoming }
}

function dueLabel(task: TaskListItem): string {
    if (!task.due_date) return "-"
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

export function CaseDetailsPrintView({ data }: CaseDetailsPrintViewProps) {
    const surrogate = data.surrogate
    const bmi = computeBmi(
        surrogate.height_ft !== null && surrogate.height_ft !== undefined
            ? Number(surrogate.height_ft)
            : null,
        surrogate.weight_lb ?? null,
    )
    const { overdue, upcoming } = taskGroups(data.tasks)

    return (
        <div data-case-details-print="ready" className="min-h-screen bg-background text-foreground">
            <div className="mx-auto max-w-[900px] space-y-4 px-4 py-6 print:px-0 print:py-0">
                <header className="rounded-lg border bg-card p-4">
                    <h1 className="text-2xl font-semibold tracking-tight">Case Details</h1>
                    <p className="mt-1 text-base">{display(surrogate.full_name)}</p>
                    <p className="mt-2 text-xs text-muted-foreground">
                        Generated {format(new Date(), "MMMM d, yyyy")}
                    </p>
                </header>

                <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
                    <div className="space-y-4">
                        <Section title="Contact Information">
                            <Row label="Name" value={display(surrogate.full_name)} />
                            <Row label="Email" value={display(surrogate.email)} />
                            <Row label="Phone" value={display(surrogate.phone)} />
                            <Row label="State" value={display(surrogate.state)} />
                            <Row label="Source" value={display(surrogate.source)} />
                            <Row label="Created" value={formatDateOrDash(surrogate.created_at)} />
                        </Section>

                        <Section title="Demographics">
                            <Row label="Date of Birth" value={formatDateOrDash(surrogate.date_of_birth)} />
                            <Row label="Race" value={display(formatRace(surrogate.race))} />
                            <Row label="Height" value={formatHeight(surrogate.height_ft)} />
                            <Row
                                label="Weight"
                                value={surrogate.weight_lb ? `${surrogate.weight_lb} lb` : "-"}
                            />
                            <Row label="BMI" value={bmi !== null ? String(bmi) : "-"} />
                        </Section>

                        <Section title="Insurance Information">
                            <Row label="Company" value={display(surrogate.insurance_company)} />
                            <Row label="Plan" value={display(surrogate.insurance_plan_name)} />
                            <Row label="Policy #" value={display(surrogate.insurance_policy_number)} />
                            <Row label="Member ID" value={display(surrogate.insurance_member_id)} />
                            <Row label="Group #" value={display(surrogate.insurance_group_number)} />
                            <Row label="Phone" value={display(surrogate.insurance_phone)} />
                            <Row label="Subscriber Name" value={display(surrogate.insurance_subscriber_name)} />
                            <Row
                                label="Subscriber DOB"
                                value={formatDateOrDash(surrogate.insurance_subscriber_dob)}
                            />
                        </Section>

                        {data.show_medical && (
                            <Section title="Medical Information">
                                <Row label="IVF Clinic" value={display(surrogate.clinic_name)} />
                                <Row
                                    label="IVF Address"
                                    value={formatAddress([
                                        surrogate.clinic_address_line1,
                                        surrogate.clinic_address_line2,
                                        surrogate.clinic_city,
                                        surrogate.clinic_state,
                                        surrogate.clinic_postal,
                                    ])}
                                />
                                <Row label="IVF Phone" value={display(surrogate.clinic_phone)} />
                                <Row label="IVF Email" value={display(surrogate.clinic_email)} />

                                <Row
                                    label="Monitoring Clinic"
                                    value={display(surrogate.monitoring_clinic_name)}
                                />
                                <Row
                                    label="Monitoring Address"
                                    value={formatAddress([
                                        surrogate.monitoring_clinic_address_line1,
                                        surrogate.monitoring_clinic_address_line2,
                                        surrogate.monitoring_clinic_city,
                                        surrogate.monitoring_clinic_state,
                                        surrogate.monitoring_clinic_postal,
                                    ])}
                                />
                                <Row
                                    label="Monitoring Phone"
                                    value={display(surrogate.monitoring_clinic_phone)}
                                />
                                <Row
                                    label="Monitoring Email"
                                    value={display(surrogate.monitoring_clinic_email)}
                                />

                                <Row label="OB Provider" value={display(surrogate.ob_provider_name)} />
                                <Row label="OB Clinic" value={display(surrogate.ob_clinic_name)} />
                                <Row
                                    label="OB Address"
                                    value={formatAddress([
                                        surrogate.ob_address_line1,
                                        surrogate.ob_address_line2,
                                        surrogate.ob_city,
                                        surrogate.ob_state,
                                        surrogate.ob_postal,
                                    ])}
                                />
                                <Row label="OB Phone" value={display(surrogate.ob_phone)} />
                                <Row label="OB Email" value={display(surrogate.ob_email)} />

                                <Row
                                    label="Delivery Hospital"
                                    value={display(surrogate.delivery_hospital_name)}
                                />
                                <Row
                                    label="Delivery Address"
                                    value={formatAddress([
                                        surrogate.delivery_hospital_address_line1,
                                        surrogate.delivery_hospital_address_line2,
                                        surrogate.delivery_hospital_city,
                                        surrogate.delivery_hospital_state,
                                        surrogate.delivery_hospital_postal,
                                    ])}
                                />
                                <Row
                                    label="Delivery Phone"
                                    value={display(surrogate.delivery_hospital_phone)}
                                />
                                <Row
                                    label="Delivery Email"
                                    value={display(surrogate.delivery_hospital_email)}
                                />
                            </Section>
                        )}
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
                            <Row label="Age Eligible (21-36)" value={yesNo(surrogate.is_age_eligible)} />
                            <Row label="US Citizen or PR" value={yesNo(surrogate.is_citizen_or_pr)} />
                            <Row label="Has Child" value={yesNo(surrogate.has_child)} />
                            <Row label="Non-Smoker" value={yesNo(surrogate.is_non_smoker)} />
                            <Row
                                label="Prior Surrogate Experience"
                                value={yesNo(surrogate.has_surrogate_experience)}
                            />
                            <Row
                                label="Deliveries"
                                value={surrogate.num_deliveries !== null ? String(surrogate.num_deliveries) : "-"}
                            />
                            <Row
                                label="C-sections"
                                value={surrogate.num_csections !== null ? String(surrogate.num_csections) : "-"}
                            />
                        </Section>
                    </div>
                </div>
            </div>
        </div>
    )
}

import type { ElementType } from "react"
import {
    ActivityIcon,
    AlertCircleIcon,
    ArrowUpRightIcon,
    BellIcon,
    CalendarIcon,
    CheckCircle2Icon,
    ClockIcon,
    FileTextIcon,
    ListChecksIcon,
    MailIcon,
    MessageSquareIcon,
    PencilLineIcon,
    PlugZapIcon,
    StickyNoteIcon,
    UserIcon,
    UserPlusIcon,
    XIcon,
    ZapIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"

export const TRIGGER_ICONS: Record<string, ElementType> = {
    surrogate_created: FileTextIcon,
    status_changed: ZapIcon,
    surrogate_assigned: UserIcon,
    surrogate_updated: FileTextIcon,
    form_submitted: FileTextIcon,
    form_submission_approved: CheckCircle2Icon,
    form_submission_rejected: XIcon,
    intake_lead_created: FileTextIcon,
    task_due: ClockIcon,
    task_overdue: AlertCircleIcon,
    scheduled: CalendarIcon,
    inactivity: ClockIcon,
    match_proposed: ActivityIcon,
    match_accepted: CheckCircle2Icon,
    match_declined: XIcon,
    match_cancelled: XIcon,
    appointment_scheduled: CalendarIcon,
    appointment_completed: CheckCircle2Icon,
    appointment_cancelled: XIcon,
    appointment_no_show: AlertCircleIcon,
    appointment_requested: CalendarIcon,
    appointment_rescheduled: CalendarIcon,
    appointment_expired: ClockIcon,
    appointment_time: ClockIcon,
    note_added: FileTextIcon,
    document_uploaded: FileTextIcon,
    donor_created: FileTextIcon,
    donor_stage_changed: ZapIcon,
    donor_assigned: UserIcon,
    donor_updated: FileTextIcon,
}

export function getTriggerIcon(triggerType: string): ElementType {
    return TRIGGER_ICONS[triggerType] ?? ZapIcon
}

export type ActionTone = "sky" | "violet" | "emerald" | "amber" | "rose" | "teal" | "slate"

export type ActionGroup = "Communicate" | "Records" | "Tasks" | "Integrations" | "Actions"

export const ACTION_GROUP_ORDER: ActionGroup[] = ["Communicate", "Records", "Tasks", "Integrations", "Actions"]

type ActionMeta = { icon: ElementType; group: ActionGroup; tone: ActionTone }

const ACTION_META: Record<string, ActionMeta> = {
    send_email: { icon: MailIcon, group: "Communicate", tone: "sky" },
    send_message: { icon: MessageSquareIcon, group: "Communicate", tone: "teal" },
    send_notification: { icon: BellIcon, group: "Communicate", tone: "violet" },
    update_field: { icon: PencilLineIcon, group: "Records", tone: "amber" },
    add_note: { icon: StickyNoteIcon, group: "Records", tone: "amber" },
    assign_surrogate: { icon: UserPlusIcon, group: "Records", tone: "emerald" },
    assign_donor: { icon: UserPlusIcon, group: "Records", tone: "emerald" },
    promote_intake_lead: { icon: ArrowUpRightIcon, group: "Records", tone: "emerald" },
    create_task: { icon: ListChecksIcon, group: "Tasks", tone: "violet" },
    send_zapier_conversion_event: { icon: PlugZapIcon, group: "Integrations", tone: "slate" },
}

const FALLBACK_ACTION_META: ActionMeta = { icon: ZapIcon, group: "Actions", tone: "slate" }

export function getActionMeta(actionType: string): ActionMeta {
    return ACTION_META[actionType] ?? FALLBACK_ACTION_META
}

const TONE_CLASSES: Record<ActionTone, string> = {
    sky: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
    violet: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
    emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    rose: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
    teal: "bg-teal-500/10 text-teal-600 dark:text-teal-400",
    slate: "bg-muted text-muted-foreground",
}

/**
 * Canvas node colors per tone: a tinted shell around a card body, with the tone on the label,
 * the connection dots, and the drop slot.
 */
export const NODE_TONE_CLASSES: Record<ActionTone, { shell: string; label: string; dot: string; slot: string }> = {
    sky: {
        shell: "border-sky-500/25 bg-sky-500/[0.07] dark:border-sky-400/25 dark:bg-sky-400/[0.08]",
        label: "text-sky-700 dark:text-sky-300",
        dot: "bg-sky-500 dark:bg-sky-400",
        slot: "border-sky-500/50 bg-sky-500/[0.06]",
    },
    violet: {
        shell: "border-violet-500/25 bg-violet-500/[0.07] dark:border-violet-400/25 dark:bg-violet-400/[0.08]",
        label: "text-violet-700 dark:text-violet-300",
        dot: "bg-violet-500 dark:bg-violet-400",
        slot: "border-violet-500/50 bg-violet-500/[0.06]",
    },
    emerald: {
        shell: "border-emerald-500/25 bg-emerald-500/[0.07] dark:border-emerald-400/25 dark:bg-emerald-400/[0.08]",
        label: "text-emerald-700 dark:text-emerald-300",
        dot: "bg-emerald-500 dark:bg-emerald-400",
        slot: "border-emerald-500/50 bg-emerald-500/[0.06]",
    },
    amber: {
        shell: "border-amber-500/30 bg-amber-500/[0.08] dark:border-amber-400/25 dark:bg-amber-400/[0.08]",
        label: "text-amber-700 dark:text-amber-300",
        dot: "bg-amber-500 dark:bg-amber-400",
        slot: "border-amber-500/50 bg-amber-500/[0.06]",
    },
    rose: {
        shell: "border-rose-500/25 bg-rose-500/[0.07] dark:border-rose-400/25 dark:bg-rose-400/[0.08]",
        label: "text-rose-700 dark:text-rose-300",
        dot: "bg-rose-500 dark:bg-rose-400",
        slot: "border-rose-500/50 bg-rose-500/[0.06]",
    },
    teal: {
        shell: "border-teal-500/25 bg-teal-500/[0.07] dark:border-teal-400/25 dark:bg-teal-400/[0.08]",
        label: "text-teal-700 dark:text-teal-300",
        dot: "bg-teal-500 dark:bg-teal-400",
        slot: "border-teal-500/50 bg-teal-500/[0.06]",
    },
    slate: {
        shell: "border-border bg-muted/60",
        label: "text-muted-foreground",
        dot: "bg-muted-foreground/60",
        slot: "border-muted-foreground/40 bg-muted/60",
    },
}

/** Small tinted icon chip shared by the palette and the canvas nodes. */
export function NodeIcon({
    icon: Icon,
    tone = "slate",
    size = "md",
    className,
}: {
    icon: ElementType
    tone?: ActionTone
    size?: "sm" | "md"
    className?: string
}) {
    return (
        <span
            aria-hidden="true"
            className={cn(
                "flex shrink-0 items-center justify-center rounded-md",
                size === "sm" ? "size-5 [&_svg]:size-3" : "size-8 [&_svg]:size-4",
                TONE_CLASSES[tone],
                className,
            )}
        >
            <Icon />
        </span>
    )
}

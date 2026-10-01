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
    GitMergeIcon,
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
    form_started: FileTextIcon,
    form_submitted: FileTextIcon,
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
    create_intake_lead: { icon: UserPlusIcon, group: "Records", tone: "emerald" },
    auto_match_submission: { icon: GitMergeIcon, group: "Records", tone: "rose" },
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

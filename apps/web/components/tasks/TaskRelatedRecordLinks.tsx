import Link from "@/components/app-link"
import { cn } from "@/lib/utils"
import {
    getTaskFormSubmissionRecord,
    getTaskRelatedRecords,
    type TaskRelatedRecordFields,
} from "@/lib/task-related-record"

export function TaskRelatedRecordLinks({
    task,
    className,
}: {
    task: TaskRelatedRecordFields
    className?: string
}) {
    const records = getTaskRelatedRecords(task)
    if (records.length === 0) return null

    return (
        <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1", className)}>
            {records.map((record) => record.href ? (
                <Link
                    key={`${record.kind}:${record.id}`}
                    href={record.href}
                    className="hover:text-foreground hover:underline"
                >
                    {record.label}
                </Link>
            ) : (
                <span key={`${record.kind}:${record.id}`}>{record.label}</span>
            ))}
        </div>
    )
}

/** Submission row for the task dialogs; renders nothing for tasks without a form submission. */
export function TaskFormSubmissionField({ task }: { task: TaskRelatedRecordFields }) {
    const submission = getTaskFormSubmissionRecord(task)
    if (!submission) return null

    return (
        <div className="space-y-1 text-sm">
            <p className="font-medium">Submission</p>
            {submission.href ? (
                <Link href={submission.href} className="text-primary hover:underline">
                    {submission.label}
                </Link>
            ) : (
                <p className="text-muted-foreground">{submission.label}</p>
            )}
        </div>
    )
}

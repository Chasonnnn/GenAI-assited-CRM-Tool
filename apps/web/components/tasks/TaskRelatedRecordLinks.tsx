import Link from "@/components/app-link"
import { cn } from "@/lib/utils"
import {
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

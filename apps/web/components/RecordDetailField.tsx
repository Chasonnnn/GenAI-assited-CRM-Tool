import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"

export function RecordDetailField({ icon: Icon, label, value }: {
    icon: LucideIcon
    label: string
    value: ReactNode
}) {
    return (
        <div className="flex min-w-0 items-center gap-3">
            <Icon className="size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0">
                <p className="text-sm text-muted-foreground">{label}</p>
                <div className="text-base font-medium [overflow-wrap:anywhere]">
                    {value === "" || value == null ? "Not provided" : value}
                </div>
            </div>
        </div>
    )
}

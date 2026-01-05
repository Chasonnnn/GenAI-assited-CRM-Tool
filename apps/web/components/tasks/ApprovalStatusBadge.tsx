"use client"

/**
 * ApprovalStatusBadge - Visual indicator for workflow approval status.
 *
 * Shows distinct colors and icons for: pending, denied, expired
 */

import { Badge } from "@/components/ui/badge"
import { ClockIcon, XCircleIcon, AlertTriangleIcon, CheckCircleIcon } from "lucide-react"
import type { TaskStatus } from "@/lib/api/tasks"

interface ApprovalStatusBadgeProps {
    status: TaskStatus | string | null
    denialReason?: string | null
    className?: string
}

const statusConfig: Record<string, {
    label: string
    icon: React.ElementType
    className: string
}> = {
    pending: {
        label: "Pending Approval",
        icon: ClockIcon,
        className: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    },
    in_progress: {
        label: "In Review",
        icon: ClockIcon,
        className: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    },
    completed: {
        label: "Approved",
        icon: CheckCircleIcon,
        className: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
    },
    denied: {
        label: "Denied",
        icon: XCircleIcon,
        className: "bg-red-500/10 text-red-600 border-red-500/20",
    },
    expired: {
        label: "Expired",
        icon: AlertTriangleIcon,
        className: "bg-gray-500/10 text-gray-600 border-gray-500/20",
    },
}

export function ApprovalStatusBadge({ status, denialReason, className = "" }: ApprovalStatusBadgeProps) {
    const config = statusConfig[status || "pending"] || statusConfig.pending
    const Icon = config.icon

    return (
        <div className={`flex flex-col gap-1 ${className}`}>
            <Badge variant="outline" className={`${config.className} flex items-center gap-1`}>
                <Icon className="size-3" />
                {config.label}
            </Badge>
            {denialReason && (status === "denied" || status === "expired") && (
                <span className="text-xs text-muted-foreground">
                    {denialReason}
                </span>
            )}
        </div>
    )
}

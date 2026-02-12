"use client"

import { memo } from "react"
import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Checkbox } from "@/components/ui/checkbox"
import { buttonVariants } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { TableCell, TableRow } from "@/components/ui/table"
import { MoreVerticalIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatRace, formatDate } from "@/lib/formatters"
import type { SurrogateListItem } from "@/lib/types/surrogate"
import type { PipelineStage } from "@/lib/api/pipelines"

// Helper for initials
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

interface SurrogateRowProps {
    surrogate: SurrogateListItem
    isSelected: boolean
    stage: PipelineStage | undefined
    onSelect: (id: string, checked: boolean) => void
    onTogglePriority: (id: string, current: boolean) => void
    onArchive: (id: string) => void
    onRestore: (id: string) => void
    isUpdatePending: boolean
    isArchivePending: boolean
    isRestorePending: boolean
}

function SurrogateRowComponent({
    surrogate,
    isSelected,
    stage,
    onSelect,
    onTogglePriority,
    onArchive,
    onRestore,
    isUpdatePending,
    isArchivePending,
    isRestorePending
}: SurrogateRowProps) {
    const statusLabel = surrogate.status_label || stage?.label || "Unknown"
    const statusColor = stage?.color || "#6B7280"
    const rowClass = surrogate.is_priority ? "text-amber-600" : ""
    const mutedCellClass = surrogate.is_priority ? "text-amber-600" : "text-muted-foreground"

    return (
        <TableRow
            className={cn(rowClass, "[content-visibility:auto] [contain-intrinsic-size:auto_53px]")}
        >
            <TableCell>
                <Checkbox
                    checked={isSelected}
                    onCheckedChange={(checked) => onSelect(surrogate.id, !!checked)}
                    aria-label={`Select ${surrogate.full_name}`}
                />
            </TableCell>
            <TableCell>
                <Link href={`/surrogates/${surrogate.id}`} className={cn("font-medium hover:underline", surrogate.is_priority ? "text-amber-600" : "text-primary")}>
                    #{surrogate.surrogate_number}
                </Link>
            </TableCell>
            <TableCell className="font-medium">{surrogate.full_name}</TableCell>
            <TableCell className={cn("text-center", mutedCellClass)}>
                {surrogate.age ?? "—"}
            </TableCell>
            <TableCell className={cn("text-center", mutedCellClass)}>
                {surrogate.bmi ?? "—"}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {formatRace(surrogate.race) || "—"}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {surrogate.state || "—"}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {surrogate.phone || "—"}
            </TableCell>
            <TableCell className={cn("max-w-[200px] truncate", mutedCellClass)} title={surrogate.email}>
                {surrogate.email}
            </TableCell>
            <TableCell>
                <Badge style={{ backgroundColor: statusColor, color: "white" }}>
                    {statusLabel}
                </Badge>
            </TableCell>
            <TableCell>
                <Badge variant="secondary" className="capitalize">
                    {(() => {
                        const labels: Record<string, string> = {
                            manual: "Manual",
                            meta: "Meta",
                            tiktok: "TikTok",
                            google: "Google",
                            website: "Website",
                            referral: "Referral",
                            other: "Others",
                            agency: "Others",
                            import: "Others",
                        }
                        return labels[surrogate.source] ?? surrogate.source
                    })()}
                </Badge>
            </TableCell>
            <TableCell>
                {surrogate.owner_name ? (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger>
                                <Avatar className="h-7 w-7">
                                    <AvatarFallback className="text-xs">
                                        {getInitials(surrogate.owner_name)}
                                    </AvatarFallback>
                                </Avatar>
                            </TooltipTrigger>
                            <TooltipContent>
                                {surrogate.owner_name}
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                ) : (
                    <span className="text-muted-foreground">—</span>
                )}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {formatDate(surrogate.created_at, { month: "short", day: "2-digit", year: "numeric" })}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {formatDate(surrogate.last_activity_at || surrogate.created_at, { month: "short", day: "2-digit", year: "numeric" })}
            </TableCell>
            <TableCell>
                <DropdownMenu>
                    <DropdownMenuTrigger
                        className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "size-8")}
                        aria-label={`Actions for ${surrogate.full_name}`}
                    >
                        <MoreVerticalIcon className="size-4" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => window.location.href = `/surrogates/${surrogate.id}`}>
                            View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            onClick={() => onTogglePriority(surrogate.id, surrogate.is_priority)}
                            disabled={isUpdatePending}
                        >
                            {surrogate.is_priority ? "Remove Priority" : "Mark as Priority"}
                        </DropdownMenuItem>
                        {!surrogate.is_archived ? (
                            <DropdownMenuItem
                                onClick={() => onArchive(surrogate.id)}
                                disabled={isArchivePending}
                                className="text-destructive"
                            >
                                Archive
                            </DropdownMenuItem>
                        ) : (
                            <DropdownMenuItem
                                onClick={() => onRestore(surrogate.id)}
                                disabled={isRestorePending}
                            >
                                Restore
                            </DropdownMenuItem>
                        )}
                    </DropdownMenuContent>
                </DropdownMenu>
            </TableCell>
        </TableRow>
    )
}

export const SurrogateRow = memo(SurrogateRowComponent)

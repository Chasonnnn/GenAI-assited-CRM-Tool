"use client"

import { memo } from "react"
import Link from "@/components/app-link"
import { TableCell, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Checkbox } from "@/components/ui/checkbox"
import { buttonVariants } from "@/components/ui/button"
import { MoreVerticalIcon } from "lucide-react"
import { useArchiveSurrogate, useRestoreSurrogate, useUpdateSurrogate } from "@/lib/hooks/use-surrogates"
import type { SurrogateListItem } from "@/lib/types/surrogate"
import { cn } from "@/lib/utils"
import { formatRace } from "@/lib/formatters"
import { parseDateInput } from "@/lib/utils/date"

// Format date for display
function formatDate(dateString: string | null | undefined): string {
    if (!dateString) return "—"
    const date = parseDateInput(dateString)
    return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "2-digit",
        year: "numeric",
    }).format(date)
}

// Get initials from name
function getInitials(name: string | null): string {
    if (!name) return "?"
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

interface SurrogateRowProps {
    item: SurrogateListItem
    isSelected: boolean
    onToggleSelection: (id: string, checked: boolean) => void
    stageById: Map<string, { label: string; color?: string }>
}

const SurrogateRow = memo(({ item, isSelected, onToggleSelection, stageById }: SurrogateRowProps) => {
    const archiveMutation = useArchiveSurrogate()
    const restoreMutation = useRestoreSurrogate()
    const updateMutation = useUpdateSurrogate()

    const handleArchive = async () => {
        await archiveMutation.mutateAsync(item.id)
    }

    const handleRestore = async () => {
        await restoreMutation.mutateAsync(item.id)
    }

    const handleTogglePriority = async () => {
        await updateMutation.mutateAsync({ surrogateId: item.id, data: { is_priority: !item.is_priority } })
    }

    const stage = stageById.get(item.stage_id)
    const statusLabel = item.status_label || stage?.label || "Unknown"
    const statusColor = stage?.color || "#6B7280"
    // Apply gold styling for entire row on priority surrogates
    const rowClass = item.is_priority ? "text-amber-600" : ""
    const mutedCellClass = item.is_priority ? "text-amber-600" : "text-muted-foreground"

    return (
        <TableRow
            className={cn(rowClass, "[content-visibility:auto] [contain-intrinsic-size:auto_53px]")}
        >
            <TableCell>
                <Checkbox
                    checked={isSelected}
                    onCheckedChange={(checked) => onToggleSelection(item.id, !!checked)}
                    aria-label={`Select ${item.full_name}`}
                />
            </TableCell>
            <TableCell>
                <Link href={`/surrogates/${item.id}`} className={`font-medium hover:underline ${item.is_priority ? "text-amber-600" : "text-primary"}`}>
                    #{item.surrogate_number}
                </Link>
            </TableCell>
            <TableCell className="font-medium">{item.full_name}</TableCell>
            <TableCell className={cn("text-center", mutedCellClass)}>
                {item.age ?? "—"}
            </TableCell>
            <TableCell className={cn("text-center", mutedCellClass)}>
                {item.bmi ?? "—"}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {formatRace(item.race) || "—"}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {item.state || "—"}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {item.phone || "—"}
            </TableCell>
            <TableCell className={cn("max-w-[200px] truncate", mutedCellClass)} title={item.email}>
                {item.email}
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
                        return labels[item.source] ?? item.source
                    })()}
                </Badge>
            </TableCell>
            <TableCell>
                {item.owner_name ? (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger>
                                <Avatar className="h-7 w-7">
                                    <AvatarFallback className="text-xs">
                                        {getInitials(item.owner_name)}
                                    </AvatarFallback>
                                </Avatar>
                            </TooltipTrigger>
                            <TooltipContent>
                                {item.owner_name}
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                ) : (
                    <span className="text-muted-foreground">—</span>
                )}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {formatDate(item.created_at)}
            </TableCell>
            <TableCell className={mutedCellClass}>
                {formatDate(item.last_activity_at || item.created_at)}
            </TableCell>
            <TableCell>
                <DropdownMenu>
                    <DropdownMenuTrigger
                        className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "size-8")}
                        aria-label={`Actions for ${item.full_name}`}
                    >
                        <MoreVerticalIcon className="size-4" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => window.location.href = `/surrogates/${item.id}`}>
                            View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem
                            onClick={handleTogglePriority}
                            disabled={updateMutation.isPending}
                        >
                            {item.is_priority ? "Remove Priority" : "Mark as Priority"}
                        </DropdownMenuItem>
                        {!item.is_archived ? (
                            <DropdownMenuItem
                                onClick={handleArchive}
                                disabled={archiveMutation.isPending}
                                className="text-destructive"
                            >
                                Archive
                            </DropdownMenuItem>
                        ) : (
                            <DropdownMenuItem
                                onClick={handleRestore}
                                disabled={restoreMutation.isPending}
                            >
                                Restore
                            </DropdownMenuItem>
                        )}
                    </DropdownMenuContent>
                </DropdownMenu>
            </TableCell>
        </TableRow>
    )
})

SurrogateRow.displayName = "SurrogateRow"

export default SurrogateRow

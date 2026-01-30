"use client"

import { buttonVariants } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MoreVerticalIcon, EditIcon, HistoryIcon, TrashIcon } from "lucide-react"
import { useInterviewTab } from "./context"

export function MobileHeaderActions() {
    const {
        selectedInterview,
        openEditor,
        openDeleteDialog,
        openVersionHistory,
        canEdit,
        canDelete,
    } = useInterviewTab()

    if (!selectedInterview) return null

    return (
        <DropdownMenu>
            <DropdownMenuTrigger
                className={buttonVariants({ variant: "ghost", size: "icon", className: "h-8 w-8" })}
            >
                <MoreVerticalIcon className="h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                {canEdit && (
                    <DropdownMenuItem onClick={() => openEditor(selectedInterview)}>
                        <EditIcon className="h-4 w-4 mr-2" />
                        Edit
                    </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={() => openVersionHistory(selectedInterview)}>
                    <HistoryIcon className="h-4 w-4 mr-2" />
                    Version History
                </DropdownMenuItem>
                {canDelete && (
                    <DropdownMenuItem onClick={() => openDeleteDialog(selectedInterview)} className="text-destructive">
                        <TrashIcon className="h-4 w-4 mr-2" />
                        Delete
                    </DropdownMenuItem>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

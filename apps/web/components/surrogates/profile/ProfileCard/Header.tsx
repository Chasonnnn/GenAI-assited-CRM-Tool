"use client"

import { Button } from "@/components/ui/button"
import { CardHeader, CardTitle } from "@/components/ui/card"
import {
    RefreshCwIcon,
    Loader2Icon,
    DownloadIcon,
    EditIcon,
} from "lucide-react"
import { useProfileCardActions, useProfileCardMode } from "./context"

export function Header() {
    const { mode, enterEditMode } = useProfileCardMode()
    const {
        cancelAllChanges,
        syncProfile,
        exportProfile,
        isSyncing,
        isExporting,
    } = useProfileCardActions()

    const isEditMode = mode.type === "edit"

    return (
        <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg">Profile Card</CardTitle>
            <div className="flex items-center gap-2">
                <Button
                    size="sm"
                    variant="outline"
                    className="h-7"
                    onClick={exportProfile}
                    disabled={isExporting}
                >
                    {isExporting ? (
                        <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                        <DownloadIcon className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1.5">Export</span>
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    className="h-7"
                    onClick={syncProfile}
                    disabled={isSyncing}
                >
                    {isSyncing ? (
                        <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                        <RefreshCwIcon className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1.5">Sync</span>
                </Button>
                {isEditMode ? (
                    <Button
                        size="sm"
                        variant="ghost"
                        className="h-7"
                        onClick={cancelAllChanges}
                    >
                        Cancel
                    </Button>
                ) : (
                    <Button
                        size="sm"
                        className="h-7"
                        onClick={enterEditMode}
                    >
                        <EditIcon className="h-3.5 w-3.5 mr-1.5" />
                        Edit
                    </Button>
                )}
            </div>
        </CardHeader>
    )
}

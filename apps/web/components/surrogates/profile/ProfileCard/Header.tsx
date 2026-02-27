"use client"

import { Button } from "@/components/ui/button"
import { CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
    RefreshCwIcon,
    Loader2Icon,
    DownloadIcon,
    EditIcon,
} from "lucide-react"
import { useProfileCardActions, useProfileCardData, useProfileCardEdits, useProfileCardMode, PROFILE_HEADER_NAME_KEY, PROFILE_HEADER_NOTE_KEY, renderProfileTemplate } from "./context"

export function Header() {
    const { profile } = useProfileCardData()
    const { mode, enterEditMode } = useProfileCardMode()
    const { editedFields, setFieldValue } = useProfileCardEdits()
    const {
        cancelAllChanges,
        syncProfile,
        exportProfile,
        isSyncing,
        isExporting,
    } = useProfileCardActions()

    const isEditMode = mode.type === "edit"
    const profileName = String(
        editedFields[PROFILE_HEADER_NAME_KEY] ||
        profile?.header_name_override ||
        profile?.merged_view?.full_name ||
        "Profile Card"
    )
    const profileNote = String(
        editedFields[PROFILE_HEADER_NOTE_KEY] ||
        profile?.header_note ||
        ""
    )
    const renderedNote = renderProfileTemplate(profileNote, profile?.merged_view ?? {})

    return (
        <CardHeader className="pb-2 space-y-3">
            <div>
                {isEditMode ? (
                    <Input
                        value={profileName}
                        onChange={(e) => setFieldValue(PROFILE_HEADER_NAME_KEY, e.target.value)}
                        placeholder="Profile header name"
                        className="h-8 text-base font-semibold"
                    />
                ) : (
                    <CardTitle className="text-lg">{profileName}</CardTitle>
                )}
                {isEditMode ? (
                    <Input
                        value={profileNote}
                        onChange={(e) => setFieldValue(PROFILE_HEADER_NOTE_KEY, e.target.value)}
                        placeholder="Add a custom header note (supports tokens like {{first_name}})"
                        className="mt-2 h-8 text-sm"
                    />
                ) : (
                    renderedNote ? <p className="mt-2 text-sm text-muted-foreground">{renderedNote}</p> : null
                )}
            </div>
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

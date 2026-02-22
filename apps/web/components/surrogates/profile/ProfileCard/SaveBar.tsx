"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Loader2Icon, SaveIcon } from "lucide-react"
import { useProfileCardActions, useProfileCardEdits, useProfileCardMode } from "./context"

export function SaveBar() {
    const { mode } = useProfileCardMode()
    const { hasChanges, stagedChanges } = useProfileCardEdits()
    const {
        saveChanges,
        isSaving,
    } = useProfileCardActions()

    const isEditMode = mode.type === "edit"

    if (!isEditMode || !hasChanges) {
        return null
    }

    return (
        <div className="sticky bottom-0 pt-4 bg-gradient-to-t from-card to-transparent">
            <Button
                className="w-full bg-primary hover:bg-primary/90"
                onClick={saveChanges}
                disabled={isSaving}
            >
                {isSaving ? (
                    <Loader2Icon className="h-4 w-4 animate-spin mr-2" />
                ) : (
                    <SaveIcon className="h-4 w-4 mr-2" />
                )}
                Save Changes
                {stagedChanges.length > 0 && (
                    <Badge variant="secondary" className="ml-2">
                        {stagedChanges.length} synced
                    </Badge>
                )}
            </Button>
        </div>
    )
}

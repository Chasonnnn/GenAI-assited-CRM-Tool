"use client"

import { InterviewVersionHistory } from "../InterviewVersionHistory"
import { useInterviewTab } from "./context"

export function VersionHistoryDialog() {
    const { dialog, closeDialog, canEdit } = useInterviewTab()

    if (dialog.type !== "version_history") {
        return null
    }

    return (
        <InterviewVersionHistory
            interviewId={dialog.interview.id}
            currentVersion={dialog.interview.transcript_version}
            open={true}
            onOpenChange={(open) => !open && closeDialog()}
            canRestore={canEdit}
        />
    )
}

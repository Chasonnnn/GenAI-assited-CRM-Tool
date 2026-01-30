"use client"

/**
 * SurrogateInterviewTab - Interview management for surrogates.
 *
 * Refactored as compound components with context for state management.
 *
 * Features:
 * - Interview list with type icons and metadata
 * - Detail view with transcript and comments
 * - Create/Edit/Delete dialogs
 * - Version history
 * - Attachments with AI transcription
 * - AI summary generation
 * - Responsive desktop/mobile layouts
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Loader2Icon, FileTextIcon, PlusIcon, ChevronLeftIcon } from "lucide-react"
import { InterviewWithComments } from "../InterviewWithComments"
import { InterviewTabProvider, useInterviewTab } from "./context"
import { List } from "./List"
import { ListItem } from "./ListItem"
import { DetailView } from "./DetailView"
import { EditorDialog } from "./EditorDialog"
import { DeleteDialog } from "./DeleteDialog"
import { VersionHistoryDialog } from "./VersionHistoryDialog"
import { MobileHeaderActions } from "./MobileHeaderActions"

// Re-export context hook
export { useInterviewTab } from "./context"
export type { DialogState, UploadState, FormState } from "./context"

// ============================================================================
// Main Component Props
// ============================================================================

interface SurrogateInterviewTabProps {
    surrogateId: string
}

// ============================================================================
// Main Component
// ============================================================================

export function SurrogateInterviewTab({ surrogateId }: SurrogateInterviewTabProps) {
    return (
        <InterviewTabProvider surrogateId={surrogateId}>
            <InterviewTabContent />
        </InterviewTabProvider>
    )
}

// ============================================================================
// Content Component (uses context)
// ============================================================================

function InterviewTabContent() {
    const {
        interviews,
        isLoading,
        canEdit,
        openEditor,
    } = useInterviewTab()

    // Loading state
    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-16">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading interviews...</span>
                </CardContent>
            </Card>
        )
    }

    // Empty state
    if (interviews.length === 0) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                    <FileTextIcon className="h-16 w-16 text-muted-foreground mb-4" />
                    <h3 className="text-lg font-semibold mb-2">No Interviews</h3>
                    <p className="text-sm text-muted-foreground mb-6 max-w-md">
                        Document phone calls, video interviews, and in-person meetings with this candidate.
                    </p>
                    {canEdit && (
                        <Button onClick={() => openEditor()}>
                            <PlusIcon className="h-4 w-4 mr-2" />
                            Add Interview
                        </Button>
                    )}

                    {/* Dialogs */}
                    <EditorDialog />
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="space-y-4">
            {/* Desktop Layout */}
            <DesktopLayout />

            {/* Mobile Layout */}
            <MobileLayout />

            {/* Dialogs */}
            <EditorDialog />
            <DeleteDialog />
            <VersionHistoryDialog />
        </div>
    )
}

// ============================================================================
// Desktop Layout
// ============================================================================

function DesktopLayout() {
    const { selectedId, selectedInterview } = useInterviewTab()

    return (
        <div className="hidden lg:grid lg:grid-cols-[320px_1fr] gap-4 h-[calc(100vh-280px)]">
            {/* Interview List */}
            <List className="overflow-hidden flex flex-col" />

            {/* Detail View */}
            <Card className="overflow-hidden flex flex-col">
                {selectedId && selectedInterview ? (
                    <DetailView />
                ) : (
                    <div className="flex-1 flex items-center justify-center text-muted-foreground">
                        <div className="text-center">
                            <FileTextIcon className="h-12 w-12 mx-auto mb-3 opacity-50" />
                            <p>Select an interview to view details</p>
                        </div>
                    </div>
                )}
            </Card>
        </div>
    )
}

// ============================================================================
// Mobile Layout
// ============================================================================

function MobileLayout() {
    const {
        interviews,
        selectedId,
        selectedInterview,
        notes,
        selectInterview,
        openEditor,
        addNote,
        updateNote,
        deleteNote,
        canEdit,
        canEditNotes,
    } = useInterviewTab()

    return (
        <div className="lg:hidden">
            {selectedId ? (
                <Card className="overflow-hidden">
                    <div className="p-2 border-b flex items-center justify-between">
                        <Button variant="ghost" size="sm" onClick={() => selectInterview(null)}>
                            <ChevronLeftIcon className="h-4 w-4 mr-1" />
                            Back to list
                        </Button>
                        <MobileHeaderActions />
                    </div>
                    {selectedInterview && (
                        <div className="h-[calc(100vh-200px)]">
                            <InterviewWithComments
                                interview={selectedInterview}
                                notes={notes}
                                onAddNote={addNote}
                                onUpdateNote={updateNote}
                                onDeleteNote={deleteNote}
                                canEdit={canEditNotes}
                            />
                        </div>
                    )}
                </Card>
            ) : (
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between py-3 px-4 border-b">
                        <CardTitle className="text-base">Interviews ({interviews.length})</CardTitle>
                        {canEdit && (
                            <Button size="sm" onClick={() => openEditor()}>
                                <PlusIcon className="h-4 w-4 mr-1" />
                                Add
                            </Button>
                        )}
                    </CardHeader>
                    <CardContent className="p-0">
                        {interviews.map((interview) => (
                            <ListItem
                                key={interview.id}
                                interview={interview}
                                isSelected={false}
                                onClick={() => selectInterview(interview.id)}
                            />
                        ))}
                    </CardContent>
                </Card>
            )}
        </div>
    )
}

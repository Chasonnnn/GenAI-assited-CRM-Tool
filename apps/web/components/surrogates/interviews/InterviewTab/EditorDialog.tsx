"use client"

import dynamic from "next/dynamic"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Loader2Icon } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { useInterviewTab } from "./context"

const TranscriptEditor = dynamic(
    () => import("../TranscriptEditor").then((mod) => mod.TranscriptEditor),
    { ssr: false, loading: () => <Skeleton className="h-96 w-full rounded-lg" /> }
)

export function EditorDialog() {
    const {
        dialog,
        closeDialog,
        form,
        setFormType,
        setFormDate,
        setFormDuration,
        setFormTranscript,
        setFormStatus,
        createOrUpdateInterview,
        isCreatePending,
        isUpdatePending,
    } = useInterviewTab()

    const isOpen = dialog.type === "editor"
    const isEditing = isOpen && dialog.interview !== null
    const isPending = isCreatePending || isUpdatePending

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{isEditing ? "Edit Interview" : "Add Interview"}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="interview-type">Interview Type</Label>
                            <NativeSelect
                                id="interview-type"
                                value={form.type}
                                onChange={(e) => setFormType(e.target.value as typeof form.type)}
                            >
                                <NativeSelectOption value="phone">Phone Call</NativeSelectOption>
                                <NativeSelectOption value="video">Video Call</NativeSelectOption>
                                <NativeSelectOption value="in_person">In-Person</NativeSelectOption>
                            </NativeSelect>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="interview-status">Status</Label>
                            <NativeSelect
                                id="interview-status"
                                value={form.status}
                                onChange={(e) => setFormStatus(e.target.value as typeof form.status)}
                            >
                                <NativeSelectOption value="completed">Completed</NativeSelectOption>
                                <NativeSelectOption value="draft">Draft</NativeSelectOption>
                            </NativeSelect>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="interview-date">Date & Time</Label>
                            <Input
                                id="interview-date"
                                type="datetime-local"
                                value={form.date}
                                onChange={(e) => setFormDate(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="interview-duration">Duration (minutes)</Label>
                            <Input
                                id="interview-duration"
                                type="number"
                                min="1"
                                max="480"
                                placeholder="30"
                                value={form.duration}
                                onChange={(e) => setFormDuration(e.target.value)}
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label>Transcript</Label>
                        <TranscriptEditor
                            content={form.transcript}
                            onChange={setFormTranscript}
                            placeholder="Start typing or paste content from Word, Google Docs..."
                            minHeight="200px"
                            maxHeight="400px"
                        />
                        <p className="text-xs text-muted-foreground">
                            Paste formatted text from Word or Google Docs to preserve formatting.
                            You can also upload audio/video files for AI transcription after creating the interview.
                        </p>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={closeDialog}>
                        Cancel
                    </Button>
                    <Button onClick={createOrUpdateInterview} disabled={isPending || !form.date}>
                        {isPending ? (
                            <>
                                <Loader2Icon className="h-4 w-4 mr-2 animate-spin" />
                                {isEditing ? "Saving..." : "Creating..."}
                            </>
                        ) : (
                            isEditing ? "Save Changes" : "Create Interview"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

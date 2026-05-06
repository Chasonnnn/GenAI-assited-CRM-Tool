"use client"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { DateTimePicker } from "@/components/ui/date-time-picker"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { VideoIcon } from "lucide-react"
import {
    useSurrogateDetailData,
    useSurrogateDetailDialogs,
    useSurrogateDetailZoom,
} from "../context"

const DURATION_OPTIONS = [
    { value: "15", label: "15 minutes" },
    { value: "30", label: "30 minutes" },
    { value: "45", label: "45 minutes" },
    { value: "60", label: "1 hour" },
    { value: "90", label: "1.5 hours" },
] as const

function formatDurationLabel(value: string | null) {
    if (!value) return "Select duration"
    return DURATION_OPTIONS.find((option) => option.value === value)?.label ?? `${value} minutes`
}

export function ZoomMeetingDialog() {
    const {
        surrogate,
        timezoneName,
    } = useSurrogateDetailData()
    const { activeDialog, closeDialog } = useSurrogateDetailDialogs()
    const {
        zoomForm,
        setZoomTopic,
        setZoomDuration,
        setZoomStartAt,
        createZoomMeeting,
        sendZoomInvite,
        isCreateZoomPending,
        isSendZoomInvitePending,
    } = useSurrogateDetailZoom()

    const isOpen = activeDialog.type === "zoom_meeting"

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <VideoIcon className="size-5" />
                        Schedule Zoom Appointment
                    </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div>
                        <Label htmlFor="zoom-topic">Topic</Label>
                        <Input
                            id="zoom-topic"
                            value={zoomForm.topic}
                            onChange={(event) => setZoomTopic(event.target.value)}
                            placeholder="Appointment topic"
                            className="mt-2"
                            disabled={!!zoomForm.lastMeetingResult}
                        />
                    </div>
                    <div>
                        <Label htmlFor="zoom-when">When</Label>
                        <div className="mt-2">
                            <DateTimePicker
                                value={zoomForm.startAt}
                                onChange={setZoomStartAt}
                                disabled={!!zoomForm.lastMeetingResult}
                                triggerId="zoom-when"
                                timeInputId="zoom-when-time"
                            />
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                            Timezone: {timezoneName}
                        </div>
                    </div>
                    <div>
                        <Label htmlFor="zoom-duration">Duration (minutes)</Label>
                        <Select
                            value={String(zoomForm.duration)}
                            onValueChange={(value) => setZoomDuration(Number(value))}
                            disabled={!!zoomForm.lastMeetingResult}
                        >
                            <SelectTrigger id="zoom-duration" className="mt-2">
                                <SelectValue>
                                    {(value: string | null) => formatDurationLabel(value)}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectGroup>
                                    {DURATION_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectGroup>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="text-xs text-muted-foreground">
                        An appointment task is created automatically.
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={closeDialog}>Cancel</Button>
                    {zoomForm.lastMeetingResult ? (
                        <>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    if (zoomForm.lastMeetingResult) {
                                        navigator.clipboard.writeText(zoomForm.lastMeetingResult.join_url)
                                    }
                                }}
                            >
                                Copy Link
                            </Button>
                            <Button
                                onClick={sendZoomInvite}
                                disabled={isSendZoomInvitePending || !surrogate?.email}
                            >
                                {isSendZoomInvitePending ? "Sending..." : "Send Invite"}
                            </Button>
                        </>
                    ) : (
                        <Button
                            onClick={createZoomMeeting}
                            disabled={!zoomForm.topic || !zoomForm.startAt || isCreateZoomPending}
                        >
                            {isCreateZoomPending ? "Creating..." : "Create Appointment"}
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

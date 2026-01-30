"use client"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { DateTimePicker } from "@/components/ui/date-time-picker"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { VideoIcon } from "lucide-react"
import { useSurrogateDetailLayout } from "../context"

export function ZoomMeetingDialog() {
    const {
        surrogate,
        activeDialog,
        closeDialog,
        zoomForm,
        setZoomTopic,
        setZoomDuration,
        setZoomStartAt,
        createZoomMeeting,
        sendZoomInvite,
        timezoneName,
        isCreateZoomPending,
        isSendZoomInvitePending,
    } = useSurrogateDetailLayout()

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
                        <Label>When</Label>
                        <div className="mt-2">
                            <DateTimePicker
                                value={zoomForm.startAt}
                                onChange={setZoomStartAt}
                                disabled={!!zoomForm.lastMeetingResult}
                            />
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                            Timezone: {timezoneName}
                        </div>
                    </div>
                    <div>
                        <Label htmlFor="zoom-duration">Duration (minutes)</Label>
                        <select
                            id="zoom-duration"
                            value={zoomForm.duration}
                            onChange={(event) => setZoomDuration(Number(event.target.value))}
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 mt-2"
                            disabled={!!zoomForm.lastMeetingResult}
                        >
                            <option value={15}>15 minutes</option>
                            <option value={30}>30 minutes</option>
                            <option value={45}>45 minutes</option>
                            <option value={60}>1 hour</option>
                            <option value={90}>1.5 hours</option>
                        </select>
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

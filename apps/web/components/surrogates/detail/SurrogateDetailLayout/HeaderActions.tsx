"use client"

import { Button, buttonVariants } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    MoreVerticalIcon,
    CheckIcon,
    XIcon,
    Loader2Icon,
    MailIcon,
    HeartHandshakeIcon,
    PhoneIcon,
    VideoIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { useSurrogateDetailLayout } from "./context"

export function HeaderActions() {
    const { user } = useAuth()
    const {
        surrogate,
        stageById,
        stageOptions,
        queues,
        assignees,
        openDialog,
        canManageQueue,
        canChangeStage,
        isInQueue,
        isOwnedByUser,
        zoomConnected,
        claimSurrogate,
        assignSurrogate,
        archiveSurrogate,
        restoreSurrogate,
        isClaimPending,
        isAssignPending,
        isReleasePending,
    } = useSurrogateDetailLayout()

    if (!surrogate) return null

    // Determine if log contact button should be shown
    const currentStage = stageById.get(surrogate.stage_id)
    const contactedStage = stageOptions.find((stage) => stage.slug === "contacted")
    const isIntakeStage = currentStage?.stage_type === "intake"
    const isBeforeContacted = !!(
        currentStage &&
        contactedStage &&
        currentStage.order < contactedStage.order
    )
    const isAssignee = !!(user?.user_id && surrogate.owner_id === user.user_id)
    const canLogContact =
        surrogate.owner_type === "user" &&
        (isAssignee || canManageQueue) &&
        isIntakeStage &&
        isBeforeContacted &&
        !surrogate.is_archived

    // Determine if propose match button should be shown
    const isReadyToMatchStage = currentStage?.slug === "ready_to_match"
    const isManagerRole = user?.role && ["case_manager", "admin", "developer"].includes(user.role)
    const canProposeMatch = isManagerRole && isReadyToMatchStage && !surrogate.is_archived

    return (
        <>
            <Button
                variant="outline"
                size="sm"
                onClick={() => openDialog({ type: "change_stage" })}
                disabled={surrogate.is_archived || !canChangeStage}
            >
                Change Stage
            </Button>

            <Button
                variant="outline"
                size="sm"
                onClick={() => openDialog({ type: "email" })}
                disabled={surrogate.is_archived || !surrogate.email}
                className="gap-2"
            >
                <MailIcon className="size-4" />
                Send Email
            </Button>

            {canLogContact && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openDialog({ type: "log_contact" })}
                    className="gap-2"
                >
                    <PhoneIcon className="size-4" />
                    Log Contact
                </Button>
            )}

            {canManageQueue && isInQueue && (
                <Button
                    variant="default"
                    size="sm"
                    onClick={claimSurrogate}
                    disabled={isClaimPending || surrogate.is_archived}
                >
                    {isClaimPending ? "Claiming..." : "Claim Surrogate"}
                </Button>
            )}

            {canManageQueue && isOwnedByUser && queues.length > 0 && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openDialog({ type: "release_queue" })}
                    disabled={surrogate.is_archived}
                >
                    Release to Queue
                </Button>
            )}

            {zoomConnected && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                        const nextHour = new Date()
                        nextHour.setSeconds(0, 0)
                        nextHour.setMinutes(0)
                        nextHour.setHours(nextHour.getHours() + 1)
                        openDialog({ type: "zoom_meeting" })
                    }}
                    disabled={surrogate.is_archived}
                >
                    <VideoIcon className="mr-2 size-4" />
                    Schedule Zoom
                </Button>
            )}

            {canProposeMatch && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openDialog({ type: "propose_match" })}
                >
                    <HeartHandshakeIcon className="size-4 mr-2" />
                    Propose Match
                </Button>
            )}

            {user?.role &&
                ["case_manager", "admin", "developer"].includes(user.role) &&
                !surrogate.is_archived && (
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                            disabled={isAssignPending}
                        >
                            {isAssignPending && <Loader2Icon className="size-4 mr-2 animate-spin" />}
                            Assign
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            {surrogate.owner_type === "user" && surrogate.owner_id && (() => {
                                const defaultQueue = queues.find((queue) => queue.name === "Unassigned")
                                if (!defaultQueue) return null
                                return (
                                    <>
                                        <DropdownMenuItem
                                            onClick={() => assignSurrogate(null)}
                                            disabled={isReleasePending}
                                        >
                                            <XIcon className="size-4 mr-2" />
                                            Unassign
                                        </DropdownMenuItem>
                                        <DropdownMenuSeparator />
                                    </>
                                )
                            })()}
                            {assignees.map((assignee) => (
                                <DropdownMenuItem
                                    key={assignee.id}
                                    onClick={() => assignSurrogate(assignee.id)}
                                    disabled={surrogate.owner_id === assignee.id}
                                >
                                    {assignee.name}
                                    {surrogate.owner_id === assignee.id && (
                                        <CheckIcon className="size-4 ml-auto" />
                                    )}
                                </DropdownMenuItem>
                            ))}
                            {assignees.length === 0 && (
                                <DropdownMenuItem disabled>No users available</DropdownMenuItem>
                            )}
                        </DropdownMenuContent>
                    </DropdownMenu>
                )}

            <DropdownMenu>
                <DropdownMenuTrigger
                    className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }))}
                    aria-label="More actions"
                >
                    <MoreVerticalIcon className="h-4 w-4" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => openDialog({ type: "edit_surrogate" })}>
                        Edit
                    </DropdownMenuItem>
                    {surrogate.is_archived ? (
                        <DropdownMenuItem onClick={restoreSurrogate}>Restore</DropdownMenuItem>
                    ) : (
                        <DropdownMenuItem onClick={archiveSurrogate}>Archive</DropdownMenuItem>
                    )}
                </DropdownMenuContent>
            </DropdownMenu>
        </>
    )
}

"use client"

import { useState } from "react"
import { AlertCircleIcon, InboxIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet"
import { toast } from "@/components/ui/toast"
import { ApiError } from "@/lib/api"
import type {
    EmailOperationMessage,
    EmailReconciliationAction,
    EmailReconciliationCase,
    EmailReconciliationDismissResolution,
} from "@/lib/api/email-operations"
import { formatDateTime } from "@/lib/formatters"
import {
    useConfirmEmailReconciliationNotSent,
    useConfirmEmailReconciliationSent,
    useDismissEmailReconciliationCase,
    useLinkEmailReconciliationEvent,
    useRetryEmailReconciliationCorrelation,
} from "@/lib/hooks/use-email-operations"
import { getMessageStatusLabel } from "./email-operation-labels"

export interface EmailReconciliationActionSelection {
    action: EmailReconciliationAction
    reconciliationCase: EmailReconciliationCase
}

function getControlledActionError(error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
        return "This case is no longer available. Refresh the queue."
    }
    if (error instanceof ApiError && error.status === 409) {
        return "This case changed. Refresh and try again."
    }
    if (error) {
        return "This action couldn’t be completed. Try again."
    }
    return null
}

function ActionError({ error }: { error: unknown }) {
    const message = getControlledActionError(error)
    if (!message) return null

    return (
        <Alert variant="destructive">
            <AlertCircleIcon aria-hidden="true" />
            <AlertTitle>Action unavailable</AlertTitle>
            <AlertDescription>{message}</AlertDescription>
        </Alert>
    )
}

export function EmailReconciliationActionDialogs({
    selection,
    messages,
    onClose,
}: {
    selection: EmailReconciliationActionSelection
    messages: EmailOperationMessage[]
    onClose: () => void
}) {
    const [dismissReason, setDismissReason] =
        useState<EmailReconciliationDismissResolution | null>(null)
    const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
    const [providerMessageId, setProviderMessageId] = useState("")
    const retryMutation = useRetryEmailReconciliationCorrelation()
    const dismissMutation = useDismissEmailReconciliationCase()
    const linkMutation = useLinkEmailReconciliationEvent()
    const confirmSentMutation = useConfirmEmailReconciliationSent()
    const confirmNotSentMutation = useConfirmEmailReconciliationNotSent()

    const { action, reconciliationCase } = selection
    const recentResendMessages = messages.filter(
        (message) => message.provider === "resend",
    )
    const trimmedProviderMessageId = providerMessageId.trim()

    if (action === "retry_correlation") {
        return (
            <AlertDialog
                open
                onOpenChange={(open) => {
                    if (!open && !retryMutation.isPending) onClose()
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Retry local correlation?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This retries local matching only. It does not send or
                            resend email.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <ActionError error={retryMutation.error} />
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={retryMutation.isPending}>
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            disabled={retryMutation.isPending}
                            onClick={() =>
                                retryMutation.mutate(
                                    {
                                        caseId: reconciliationCase.id,
                                        expectedVersion: reconciliationCase.version,
                                    },
                                    {
                                        onSuccess: () => {
                                            toast.success(
                                                "Local correlation retry started",
                                            )
                                            onClose()
                                        },
                                    },
                                )
                            }
                        >
                            {retryMutation.isPending
                                ? "Retrying..."
                                : "Retry local matching"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        )
    }

    if (action === "dismiss") {
        return (
            <Dialog
                open
                onOpenChange={(open) => {
                    if (!open && !dismissMutation.isPending) onClose()
                }}
            >
                <DialogContent showCloseButton={!dismissMutation.isPending}>
                    <DialogHeader>
                        <DialogTitle>Dismiss reconciliation case</DialogTitle>
                        <DialogDescription>
                            Dismissal removes this case from the operator queue. It
                            does not change message status or send email.
                        </DialogDescription>
                    </DialogHeader>
                    <ActionError error={dismissMutation.error} />
                    <RadioGroup
                        value={dismissReason ?? ""}
                        onValueChange={(value) =>
                            setDismissReason(
                                value as EmailReconciliationDismissResolution,
                            )
                        }
                    >
                        <div className="flex items-start gap-3 rounded-lg border p-3">
                            <RadioGroupItem
                                id="dismiss-unsupported-event"
                                value="unsupported_event"
                            />
                            <Label
                                htmlFor="dismiss-unsupported-event"
                                className="grid cursor-pointer gap-1"
                            >
                                <span>Unsupported event type</span>
                                <span className="font-normal text-muted-foreground">
                                    The signed event is valid but not part of the
                                    supported email lifecycle.
                                </span>
                            </Label>
                        </div>
                        <div className="flex items-start gap-3 rounded-lg border p-3">
                            <RadioGroupItem
                                id="dismiss-test-event"
                                value="test_event"
                            />
                            <Label
                                htmlFor="dismiss-test-event"
                                className="grid cursor-pointer gap-1"
                            >
                                <span>Test provider event</span>
                                <span className="font-normal text-muted-foreground">
                                    The event came from an intentional provider test.
                                </span>
                            </Label>
                        </div>
                        <div className="flex items-start gap-3 rounded-lg border p-3">
                            <RadioGroupItem
                                id="dismiss-not-actionable"
                                value="not_actionable"
                            />
                            <Label
                                htmlFor="dismiss-not-actionable"
                                className="grid cursor-pointer gap-1"
                            >
                                <span>Not actionable</span>
                                <span className="font-normal text-muted-foreground">
                                    Review confirmed no local message update is needed.
                                </span>
                            </Label>
                        </div>
                    </RadioGroup>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onClose}
                            disabled={dismissMutation.isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            variant="destructive"
                            disabled={
                                dismissReason === null ||
                                dismissMutation.isPending
                            }
                            onClick={() => {
                                if (dismissReason === null) return
                                dismissMutation.mutate(
                                    {
                                        caseId: reconciliationCase.id,
                                        expectedVersion: reconciliationCase.version,
                                        resolutionCode: dismissReason,
                                    },
                                    {
                                        onSuccess: () => {
                                            toast.success(
                                                "Reconciliation case dismissed",
                                            )
                                            onClose()
                                        },
                                    },
                                )
                            }}
                        >
                            {dismissMutation.isPending
                                ? "Dismissing..."
                                : "Dismiss case"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        )
    }

    if (action === "link_event") {
        return (
            <Sheet
                open
                onOpenChange={(open) => {
                    if (!open && !linkMutation.isPending) onClose()
                }}
            >
                <SheetContent
                    className="sm:max-w-lg"
                    showCloseButton={!linkMutation.isPending}
                >
                    <SheetHeader className="border-b">
                        <SheetTitle>Link provider event</SheetTitle>
                        <SheetDescription>
                            Linking updates local delivery history only. It does not
                            send or resend email.
                        </SheetDescription>
                    </SheetHeader>
                    <div className="flex min-h-0 flex-1 flex-col gap-4 px-6">
                        <ActionError error={linkMutation.error} />
                        <div>
                            <p className="font-medium">Choose a recent message</p>
                            <p className="mt-1 text-sm text-muted-foreground">
                                Match the signed provider event to an existing Resend
                                message in this organization.
                            </p>
                        </div>
                        {recentResendMessages.length === 0 ? (
                            <Empty className="border">
                                <EmptyHeader>
                                    <EmptyMedia variant="icon">
                                        <InboxIcon aria-hidden="true" />
                                    </EmptyMedia>
                                    <EmptyTitle>No recent Resend messages</EmptyTitle>
                                    <EmptyDescription>
                                        Refresh Email Operations after the matching
                                        message is available.
                                    </EmptyDescription>
                                </EmptyHeader>
                            </Empty>
                        ) : (
                            <ScrollArea className="min-h-0 flex-1 pr-3">
                                <div className="space-y-2 pb-4">
                                    {recentResendMessages.map((message) => {
                                        const isSelected =
                                            selectedMessageId === message.id
                                        return (
                                            <Button
                                                key={message.id}
                                                type="button"
                                                variant={
                                                    isSelected
                                                        ? "secondary"
                                                        : "outline"
                                                }
                                                className="h-auto w-full justify-between gap-4 px-4 py-3 text-left"
                                                aria-label={`Select ${message.subject} to ${message.recipient_email}`}
                                                aria-pressed={isSelected}
                                                onClick={() =>
                                                    setSelectedMessageId(message.id)
                                                }
                                            >
                                                <span className="min-w-0">
                                                    <span className="block truncate font-medium">
                                                        {message.subject}
                                                    </span>
                                                    <span className="mt-1 block truncate text-xs font-normal text-muted-foreground">
                                                        {message.recipient_email}
                                                    </span>
                                                    <span className="mt-1 block text-xs font-normal text-muted-foreground">
                                                        {formatDateTime(
                                                            message.created_at,
                                                            "Unknown",
                                                        )}
                                                    </span>
                                                </span>
                                                <Badge
                                                    variant={
                                                        isSelected
                                                            ? "default"
                                                            : "secondary"
                                                    }
                                                >
                                                    {isSelected
                                                        ? "Selected"
                                                        : getMessageStatusLabel(
                                                              message.status,
                                                          )}
                                                </Badge>
                                            </Button>
                                        )
                                    })}
                                </div>
                            </ScrollArea>
                        )}
                    </div>
                    <div className="flex flex-col-reverse gap-2 border-t p-6 sm:flex-row sm:justify-end">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onClose}
                            disabled={linkMutation.isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            disabled={
                                selectedMessageId === null ||
                                linkMutation.isPending
                            }
                            onClick={() => {
                                if (selectedMessageId === null) return
                                linkMutation.mutate(
                                    {
                                        caseId: reconciliationCase.id,
                                        expectedVersion: reconciliationCase.version,
                                        emailLogId: selectedMessageId,
                                    },
                                    {
                                        onSuccess: () => {
                                            toast.success("Provider event linked")
                                            onClose()
                                        },
                                    },
                                )
                            }}
                        >
                            {linkMutation.isPending
                                ? "Linking..."
                                : "Link event"}
                        </Button>
                    </div>
                </SheetContent>
            </Sheet>
        )
    }

    if (action === "confirm_sent") {
        return (
            <Dialog
                open
                onOpenChange={(open) => {
                    if (!open && !confirmSentMutation.isPending) onClose()
                }}
            >
                <DialogContent showCloseButton={!confirmSentMutation.isPending}>
                    <DialogHeader>
                        <DialogTitle>Confirm sent delivery</DialogTitle>
                        <DialogDescription>
                            Use only after verifying the Resend dashboard. This updates
                            local delivery history and does not send email.
                        </DialogDescription>
                    </DialogHeader>
                    <ActionError error={confirmSentMutation.error} />
                    <div className="space-y-2">
                        <Label htmlFor="confirmed-provider-message-id">
                            Resend message ID
                        </Label>
                        <Input
                            id="confirmed-provider-message-id"
                            value={providerMessageId}
                            onChange={(event) =>
                                setProviderMessageId(event.target.value)
                            }
                            maxLength={255}
                            autoComplete="off"
                            placeholder="Enter the verified Resend message ID"
                        />
                        <p className="text-xs text-muted-foreground">
                            Copy this value from the matching message in Resend.
                        </p>
                    </div>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={onClose}
                            disabled={confirmSentMutation.isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            disabled={
                                trimmedProviderMessageId.length === 0 ||
                                confirmSentMutation.isPending
                            }
                            onClick={() =>
                                confirmSentMutation.mutate(
                                    {
                                        caseId: reconciliationCase.id,
                                        expectedVersion: reconciliationCase.version,
                                        providerMessageId:
                                            trimmedProviderMessageId,
                                    },
                                    {
                                        onSuccess: () => {
                                            toast.success(
                                                "Delivery marked as sent",
                                            )
                                            onClose()
                                        },
                                    },
                                )
                            }
                        >
                            {confirmSentMutation.isPending
                                ? "Confirming..."
                                : "Confirm sent"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        )
    }

    if (action === "confirm_not_sent") {
        return (
            <AlertDialog
                open
                onOpenChange={(open) => {
                    if (!open && !confirmNotSentMutation.isPending) onClose()
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Confirm this delivery was not sent?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            Use only after verifying the Resend dashboard. This marks
                            the local delivery as not sent. It does not send or resend
                            email.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <ActionError error={confirmNotSentMutation.error} />
                    <AlertDialogFooter>
                        <AlertDialogCancel
                            disabled={confirmNotSentMutation.isPending}
                        >
                            Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            disabled={confirmNotSentMutation.isPending}
                            onClick={() =>
                                confirmNotSentMutation.mutate(
                                    {
                                        caseId: reconciliationCase.id,
                                        expectedVersion: reconciliationCase.version,
                                    },
                                    {
                                        onSuccess: () => {
                                            toast.success(
                                                "Delivery marked as not sent",
                                            )
                                            onClose()
                                        },
                                    },
                                )
                            }
                        >
                            {confirmNotSentMutation.isPending
                                ? "Confirming..."
                                : "Confirm not sent"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        )
    }

    return null
}

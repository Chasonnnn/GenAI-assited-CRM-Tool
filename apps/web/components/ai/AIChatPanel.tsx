"use client"

import * as React from "react"
import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
    SparklesIcon,
    SendIcon,
    XIcon,
    CheckIcon,
    XCircleIcon,
    Loader2Icon,
    MailIcon,
    ListTodoIcon,
    StickyNoteIcon,
    ArrowRightIcon,
} from "lucide-react"
import { useConversation, useSendMessage, useApproveAction, useRejectAction } from "@/lib/hooks/use-ai"
import type { ProposedAction } from "@/lib/api/ai"

interface AIChatPanelProps {
    entityType?: "case" | null  // null/undefined = global mode
    entityId?: string | null
    entityName?: string | null
    canApproveActions?: boolean
    onClose?: () => void
}

// Action type icons
const ACTION_ICONS: Record<string, React.ReactNode> = {
    send_email: <MailIcon className="h-4 w-4" />,
    create_task: <ListTodoIcon className="h-4 w-4" />,
    add_note: <StickyNoteIcon className="h-4 w-4" />,
    update_status: <ArrowRightIcon className="h-4 w-4" />,
}

// Action type labels
const ACTION_LABELS: Record<string, string> = {
    send_email: "Send Email",
    create_task: "Create Task",
    add_note: "Add Note",
    update_status: "Update Status",
}

export function AIChatPanel({
    entityType,
    entityId,
    entityName,
    canApproveActions = true,
    onClose,
}: AIChatPanelProps) {
    const [message, setMessage] = useState("")
    const scrollContainerRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    // Hooks
    const { data: conversation, isLoading: loadingConversation } = useConversation(entityType, entityId)
    const sendMessage = useSendMessage()
    const approveAction = useApproveAction()
    const rejectAction = useRejectAction()

    // Scroll to bottom on new messages
    useEffect(() => {
        if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
        }
    }, [conversation?.messages])

    // Focus input on mount
    useEffect(() => {
        inputRef.current?.focus()
    }, [])

    const handleSend = () => {
        if (!message.trim() || sendMessage.isPending) return

        sendMessage.mutate({
            entity_type: entityType,
            entity_id: entityId,
            message: message.trim(),
        })
        setMessage("")
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    const handleApprove = (approvalId: string) => {
        approveAction.mutate(approvalId)
    }

    const handleReject = (approvalId: string) => {
        rejectAction.mutate(approvalId)
    }

    const messages = conversation?.messages || []

    return (
        <div className="flex h-full flex-col bg-background">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
                <div className="flex items-center gap-2">
                    <SparklesIcon className="h-5 w-5 text-primary" />
                    <span className="font-semibold">AI Assistant</span>
                </div>
                {onClose && (
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <XIcon className="h-4 w-4" />
                    </Button>
                )}
            </div>

            {/* Context indicator */}
            <div className="border-b bg-muted/30 px-4 py-2">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>Context:</span>
                    <Badge variant="secondary" className="font-normal">
                        {entityType === "case" && entityName
                            ? `Case • ${entityName}`
                            : "Global Mode"}
                    </Badge>
                </div>
            </div>

            {/* Messages */}
            <ScrollArea className="flex-1">
                <div ref={scrollContainerRef} className="p-4">
                    {loadingConversation ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2Icon className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-8 text-center">
                            <SparklesIcon className="mb-4 h-10 w-10 text-muted-foreground/50" />
                            <p className="text-sm text-muted-foreground">
                                {entityType === "case"
                                    ? `Ask me anything about this case.`
                                    : "Ask me anything! I can help with drafts, answer questions, or parse emails."}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground/70">
                                {entityType === "case"
                                    ? "I can help summarize, draft emails, suggest next steps, and more."
                                    : "Open a case for context-aware assistance with actions."}
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {messages.map((msg) => (
                                <div key={msg.id}>
                                    {/* Message bubble */}
                                    <div
                                        className={cn(
                                            "rounded-lg px-4 py-2",
                                            msg.role === "user"
                                                ? "ml-8 bg-primary text-primary-foreground"
                                                : "mr-8 bg-muted"
                                        )}
                                    >
                                        <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                                    </div>

                                    {/* Action cards */}
                                    {msg.role === "assistant" && msg.proposed_actions && msg.proposed_actions.length > 0 && (
                                        <div className="mt-2 mr-8 space-y-2">
                                            {msg.proposed_actions.map((action: ProposedAction, idx: number) => {
                                                const approval = msg.action_approvals?.find(
                                                    (a) => a.action_index === idx
                                                )
                                                const status = approval?.status || "pending"

                                                return (
                                                    <ActionCard
                                                        key={action.approval_id || idx}
                                                        action={action}
                                                        status={status}
                                                        canApprove={canApproveActions && status === "pending"}
                                                        onApprove={() => handleApprove(action.approval_id)}
                                                        onReject={() => handleReject(action.approval_id)}
                                                        isApproving={approveAction.isPending}
                                                        isRejecting={rejectAction.isPending}
                                                    />
                                                )
                                            })}
                                        </div>
                                    )}
                                </div>
                            ))}

                            {/* Typing indicator */}
                            {sendMessage.isPending && (
                                <div className="mr-8 flex items-center gap-2 rounded-lg bg-muted px-4 py-2">
                                    <Loader2Icon className="h-4 w-4 animate-spin" />
                                    <span className="text-sm text-muted-foreground">Thinking...</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </ScrollArea>

            {/* Quick actions */}
            <div className="border-t px-4 py-2">
                <div className="flex flex-wrap gap-2">
                    <QuickActionButton
                        onClick={() => setMessage("Summarize this case")}
                        disabled={sendMessage.isPending}
                    >
                        Summarize
                    </QuickActionButton>
                    <QuickActionButton
                        onClick={() => setMessage("What should I do next?")}
                        disabled={sendMessage.isPending}
                    >
                        Next Steps
                    </QuickActionButton>
                    <QuickActionButton
                        onClick={() => setMessage("Draft a follow-up email")}
                        disabled={sendMessage.isPending}
                    >
                        Draft Email
                    </QuickActionButton>
                </div>
            </div>

            {/* Input */}
            <div className="border-t p-4">
                <div className="flex gap-2">
                    <Input
                        ref={inputRef}
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask anything..."
                        disabled={sendMessage.isPending}
                        className="flex-1"
                    />
                    <Button
                        onClick={handleSend}
                        disabled={!message.trim() || sendMessage.isPending}
                        size="icon"
                    >
                        {sendMessage.isPending ? (
                            <Loader2Icon className="h-4 w-4 animate-spin" />
                        ) : (
                            <SendIcon className="h-4 w-4" />
                        )}
                    </Button>
                </div>
            </div>
        </div>
    )
}

// Action card component
interface ActionCardProps {
    action: ProposedAction
    status: string
    canApprove: boolean
    onApprove: () => void
    onReject: () => void
    isApproving: boolean
    isRejecting: boolean
}

function ActionCard({
    action,
    status,
    canApprove,
    onApprove,
    onReject,
    isApproving,
    isRejecting,
}: ActionCardProps) {
    const icon = ACTION_ICONS[action.action_type] || <SparklesIcon className="h-4 w-4" />
    const label = ACTION_LABELS[action.action_type] || action.action_type

    return (
        <div className="rounded-lg border bg-card p-3">
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                    <div className="rounded-md bg-primary/10 p-1.5 text-primary">{icon}</div>
                    <div>
                        <p className="text-sm font-medium">{label}</p>
                        {action.action_data && (
                            <ActionPreview type={action.action_type} data={action.action_data} />
                        )}
                    </div>
                </div>

                {status === "pending" && canApprove ? (
                    <div className="flex gap-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-destructive hover:bg-destructive/10"
                            onClick={onReject}
                            disabled={isRejecting}
                        >
                            <XCircleIcon className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-green-600 hover:bg-green-600/10"
                            onClick={onApprove}
                            disabled={isApproving}
                        >
                            {isApproving ? (
                                <Loader2Icon className="h-4 w-4 animate-spin" />
                            ) : (
                                <CheckIcon className="h-4 w-4" />
                            )}
                        </Button>
                    </div>
                ) : (
                    <Badge
                        variant={
                            status === "executed"
                                ? "default"
                                : status === "rejected"
                                    ? "secondary"
                                    : "outline"
                        }
                        className="text-xs"
                    >
                        {status === "executed" ? "Done" : status === "rejected" ? "Rejected" : status}
                    </Badge>
                )}
            </div>
        </div>
    )
}

// Action preview component
function ActionPreview({ type, data }: { type: string; data: Record<string, unknown> }) {
    switch (type) {
        case "send_email":
            return (
                <p className="text-xs text-muted-foreground">
                    To: {String(data.to || "")}, Subject: {String(data.subject || "").slice(0, 30)}...
                </p>
            )
        case "create_task": {
            const dueText = data.due_date ? ` (due: ${String(data.due_date)})` : ""
            return (
                <p className="text-xs text-muted-foreground">
                    {String(data.title || "")}{dueText}
                </p>
            )
        }
        case "add_note":
            return (
                <p className="text-xs text-muted-foreground">
                    {String(data.content || data.body || data.text || "").slice(0, 50)}...
                </p>
            )
        case "update_status":
            return (
                <p className="text-xs text-muted-foreground">
                    Change to: {String(data.status || data.stage_id || "")}
                </p>
            )
        default:
            return null
    }
}

// Quick action button
function QuickActionButton({
    children,
    onClick,
    disabled,
}: {
    children: React.ReactNode
    onClick: () => void
    disabled?: boolean
}) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
        >
            {children}
        </button>
    )
}

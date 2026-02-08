"use client"

import * as React from "react"
import { useState, useRef, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
    CalendarPlusIcon,
    StopCircleIcon,
} from "lucide-react"
import { useConversation, useStreamChatMessage, useApproveAction, useRejectAction } from "@/lib/hooks/use-ai"
import type { ProposedAction } from "@/lib/api/ai"
import { ScheduleParserDialog } from "@/components/ai/ScheduleParserDialog"

interface AIChatPanelProps {
    entityType?: "surrogate" | "task" | null  // null/undefined = global mode
    entityId?: string | null
    entityName?: string | null
    canApproveActions?: boolean
    onClose?: () => void
}

interface PanelMessage {
    id: string
    role: "user" | "assistant"
    content: string
    proposed_actions?: ProposedAction[]
    action_approvals?: Array<{ action_index: number; status: string }>
    status?: "thinking" | "streaming" | "done" | "error"
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
    update_status: "Update Stage",
}

export function AIChatPanel({
    entityType,
    entityId,
    entityName,
    canApproveActions = true,
    onClose,
}: AIChatPanelProps) {
    const [message, setMessage] = useState("")
    const [messages, setMessages] = useState<PanelMessage[]>([])
    const [isStreaming, setIsStreaming] = useState(false)
    const [scheduleParserOpen, setScheduleParserOpen] = useState(false)
    const scrollRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLInputElement>(null)
    const streamAbortRef = useRef<AbortController | null>(null)
    const streamingMessageIdRef = useRef<string | null>(null)
    const stopRequestedRef = useRef(false)
    const prevContextRef = useRef<{ entityId: string | null; entityType: "surrogate" | "task" | null }>({
        entityId: entityId ?? null,
        entityType: entityType ?? null,
    })

    // Hooks
    const { data: conversation, isLoading: loadingConversation } = useConversation(entityType, entityId)
    const streamMessage = useStreamChatMessage()
    const approveAction = useApproveAction()
    const rejectAction = useRejectAction()

    useEffect(() => {
        if (isStreaming) return
        if (!conversation?.messages) {
            setMessages([])
            return
        }
        setMessages(
            conversation.messages.map((msg) => ({
                ...msg,
                status: "done" as const,
            }))
        )
    }, [conversation?.messages, isStreaming])

    // Scroll to bottom on new messages
    useEffect(() => {
        const container = scrollRef.current
        if (!container) return
        container.scrollTop = container.scrollHeight
    }, [messages])

    // Focus input on mount
    useEffect(() => {
        inputRef.current?.focus()
    }, [])

    useEffect(() => {
        return () => {
            streamAbortRef.current?.abort()
        }
    }, [])

    useEffect(() => {
        const prev = prevContextRef.current
        const currentEntityId = entityId ?? null
        const currentEntityType = entityType ?? null
        const contextChanged = prev.entityId !== currentEntityId || prev.entityType !== currentEntityType
        prevContextRef.current = { entityId: currentEntityId, entityType: currentEntityType }
        if (!contextChanged || !isStreaming) return
        streamAbortRef.current?.abort()
        setIsStreaming(false)
        streamingMessageIdRef.current = null
        stopRequestedRef.current = false
    }, [entityId, entityType, isStreaming])

    const updateMessageById = useCallback((id: string, updater: (msg: PanelMessage) => PanelMessage) => {
        setMessages((prev) => prev.map((msg) => (msg.id === id ? updater(msg) : msg)))
    }, [])

    const setAssistantError = useCallback((assistantId: string, errorText: string) => {
        updateMessageById(assistantId, (msg) => ({
            ...msg,
            content: errorText,
            status: "error",
        }))
    }, [updateMessageById])

    const handleSend = async () => {
        const trimmedMessage = message.trim()
        if (!trimmedMessage || isStreaming) return

        const userMessage: PanelMessage = {
            id: `user-${Date.now()}`,
            role: "user",
            content: trimmedMessage,
            status: "done",
        }
        const assistantId = `assistant-${Date.now()}`
        const assistantMessage: PanelMessage = {
            id: assistantId,
            role: "assistant",
            content: "",
            status: "thinking",
        }

        setMessages((prev) => [...prev, userMessage, assistantMessage])
        setMessage("")

        streamAbortRef.current?.abort()
        stopRequestedRef.current = false
        const controller = new AbortController()
        streamAbortRef.current = controller
        streamingMessageIdRef.current = assistantId
        setIsStreaming(true)

        try {
            await streamMessage(
                {
                    message: trimmedMessage,
                    ...(entityType ? { entity_type: entityType } : {}),
                    ...(entityId ? { entity_id: entityId } : {}),
                },
                (event) => {
                    if (event.type === 'start') {
                        updateMessageById(assistantId, (msg) => ({ ...msg, status: "thinking" }))
                        return
                    }
                    if (event.type === 'delta') {
                        const delta = event.data.text || ''
                        if (!delta) return
                        updateMessageById(assistantId, (msg) => ({
                            ...msg,
                            content: msg.content + delta,
                            status: "streaming",
                        }))
                        return
                    }
                    if (event.type === 'done') {
                        updateMessageById(assistantId, (msg) => ({
                            ...msg,
                            content: event.data.content,
                            proposed_actions: event.data.proposed_actions,
                            status: "done",
                        }))
                        return
                    }
                    if (event.type === 'error') {
                        setAssistantError(
                            assistantId,
                            `Sorry, I encountered an error: ${event.data.message || 'Unknown error'}. Please try again.`
                        )
                    }
                },
                controller.signal
            )
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') {
                if (stopRequestedRef.current) {
                    updateMessageById(assistantId, (msg) => ({
                        ...msg,
                        content: msg.content || "Stopped.",
                        status: "done",
                    }))
                }
                stopRequestedRef.current = false
                return
            }
            setAssistantError(
                assistantId,
                `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`
            )
        } finally {
            setIsStreaming(false)
            streamingMessageIdRef.current = null
        }
    }

    const handleStop = useCallback(() => {
        if (!isStreaming) return
        stopRequestedRef.current = true
        streamAbortRef.current?.abort()
        setIsStreaming(false)
    }, [isStreaming])

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    const handleApprove = (approvalId: string | null | undefined) => {
        if (!approvalId) return
        approveAction.mutate(approvalId)
    }

    const handleReject = (approvalId: string | null | undefined) => {
        if (!approvalId) return
        rejectAction.mutate(approvalId)
    }

    return (
        <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
                <div className="flex items-center gap-2">
                    <SparklesIcon className="h-5 w-5 text-primary" />
                    <span className="font-semibold">AI Assistant</span>
                </div>
                {onClose && (
                    <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close AI Assistant">
                        <XIcon className="h-4 w-4" />
                    </Button>
                )}
            </div>

            {/* Context indicator */}
            <div className="border-b bg-muted/30 px-4 py-2">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>Context:</span>
                    <Badge variant="secondary" className="font-normal">
                        {entityType === "surrogate" && entityName
                            ? `Surrogate • ${entityName}`
                            : "Global Mode"}
                    </Badge>
                </div>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto">
                <div className="p-4">
                    {loadingConversation ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2Icon className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-8 text-center">
                            <SparklesIcon className="mb-4 h-10 w-10 text-muted-foreground/50" />
                            <p className="text-sm text-muted-foreground">
                                {entityType === "surrogate"
                                    ? `Ask me anything about this surrogate.`
                                    : "Ask me anything! I can help with drafts, answer questions, or parse emails."}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground/70">
                                {entityType === "surrogate"
                                    ? "I can help summarize, draft emails, suggest next steps, and more."
                                    : "Open a surrogate for context-aware assistance with actions."}
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
                                        {msg.role === "assistant" && msg.status === "thinking" && !msg.content ? (
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                                                Thinking...
                                            </div>
                                        ) : (
                                            <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                                        )}
                                    </div>

                                    {/* Action cards */}
                                    {msg.role === "assistant" && msg.proposed_actions && msg.proposed_actions.length > 0 && (
                                        <div className="mt-2 mr-8 space-y-2">
                                            {msg.proposed_actions.map((action: ProposedAction, idx: number) => {
                                                const approval = msg.action_approvals?.find(
                                                    (a) => a.action_index === idx
                                                )
                                                const approvalId = action.approval_id
                                                const status = approval?.status || (approvalId ? "pending" : "unavailable")

                                                return (
                                                    <ActionCard
                                                        key={action.approval_id || idx}
                                                        action={action}
                                                        status={status}
                                                        canApprove={!!approvalId && canApproveActions && status === "pending"}
                                                        onApprove={() => handleApprove(approvalId)}
                                                        onReject={() => handleReject(approvalId)}
                                                        isApproving={approveAction.isPending}
                                                        isRejecting={rejectAction.isPending}
                                                    />
                                                )
                                            })}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Quick actions */}
            <div className="border-t px-4 py-2">
                <div className="flex flex-wrap gap-2">
                    <QuickActionButton
                        onClick={() => setMessage("Summarize this surrogate")}
                        disabled={isStreaming}
                    >
                        Summarize
                    </QuickActionButton>
                    <QuickActionButton
                        onClick={() => setMessage("What should I do next?")}
                        disabled={isStreaming}
                    >
                        Next Steps
                    </QuickActionButton>
                    <QuickActionButton
                        onClick={() => setMessage("Draft a follow-up email")}
                        disabled={isStreaming}
                    >
                        Draft Email
                    </QuickActionButton>
                    {entityType === "surrogate" && entityId && (
                        <QuickActionButton
                            onClick={() => setScheduleParserOpen(true)}
                            disabled={isStreaming}
                        >
                            <CalendarPlusIcon className="mr-1 h-3 w-3" />
                            Parse Schedule
                        </QuickActionButton>
                    )}
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
                        disabled={isStreaming}
                        className="flex-1"
                    />
                    {isStreaming ? (
                        <Button
                            onClick={handleStop}
                            size="icon"
                            variant="outline"
                            aria-label="Stop generating"
                        >
                            <StopCircleIcon className="h-4 w-4" />
                        </Button>
                    ) : (
                        <Button
                            onClick={handleSend}
                            disabled={!message.trim()}
                            size="icon"
                            aria-label="Send message"
                        >
                            <SendIcon className="h-4 w-4" />
                        </Button>
                    )}
                </div>
            </div>

            {/* Schedule Parser Dialog (mount only when open to avoid unnecessary hooks) */}
            {scheduleParserOpen && entityType === "surrogate" && entityId && (
                <ScheduleParserDialog
                    open={scheduleParserOpen}
                    onOpenChange={setScheduleParserOpen}
                    entityType="surrogate"
                    entityId={entityId}
                    {...(entityName ? { entityName } : {})}
                />
            )}
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
                            aria-label="Reject action"
                        >
                            <XCircleIcon className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-green-600 hover:bg-green-600/10"
                            onClick={onApprove}
                            disabled={isApproving}
                            aria-label="Approve action"
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
                        {status === "executed"
                            ? "Done"
                            : status === "rejected"
                                ? "Rejected"
                                : status === "unavailable"
                                    ? "Unavailable"
                                    : status}
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
        <Button
            variant="outline"
            size="sm"
            onClick={onClick}
            disabled={disabled}
            className="rounded-full h-auto px-3 py-1 text-xs"
        >
            {children}
        </Button>
    )
}

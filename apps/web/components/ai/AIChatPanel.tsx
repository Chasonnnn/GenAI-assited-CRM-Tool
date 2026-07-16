"use client"

import * as React from "react"
import dynamic from "next/dynamic"
import { useState, useRef, useEffect } from "react"
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
import type { ScheduleParserDialogProps } from "@/components/ai/ScheduleParserDialog"
import { AssistantRichText } from "@/components/ai/AssistantRichText"
import { useAIChatScrollToLatest } from "@/lib/hooks/use-ai-chat-scroll-to-latest"
import { useMountEffect } from "@/lib/hooks/use-mount-effect"

const ScheduleParserDialog = dynamic<ScheduleParserDialogProps>(
    () => import("@/components/ai/ScheduleParserDialog").then((mod) => mod.ScheduleParserDialog),
    {
        loading: () => null,
    }
)

const SCROLL_BOTTOM_THRESHOLD = 48

function isNearBottom(container: HTMLDivElement) {
    return container.scrollHeight - container.clientHeight - container.scrollTop <= SCROLL_BOTTOM_THRESHOLD
}

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

type PanelContext = {
    entityId: string | null
    entityType: "surrogate" | "task" | null
}

type ConversationMessage = Omit<PanelMessage, "status"> & {
    status?: PanelMessage["status"]
}

type PanelMessageState = {
    conversationKey: string
    conversationMessages: readonly ConversationMessage[] | undefined
    messages: PanelMessage[]
}

type MutableRef<T> = {
    current: T
}

function createConversationKey(
    context: PanelContext,
    conversationId: string | undefined,
    conversationMessages: readonly ConversationMessage[] | undefined
) {
    const scope = `${context.entityType ?? "global"}:${context.entityId ?? "global"}`
    const messagesFingerprint = conversationMessages?.map((msg) => {
        const approvals = msg.action_approvals?.map((approval) => `${approval.action_index}:${approval.status}`).join(",") ?? ""
        return `${msg.id}:${msg.role}:${msg.content.length}:${msg.proposed_actions?.length ?? 0}:${approvals}`
    }).join("|") ?? "empty"

    return `${scope}:${conversationId ?? "pending"}:${messagesFingerprint}`
}

function createPanelMessageState(
    conversationKey: string,
    conversationMessages: readonly ConversationMessage[] | undefined
): PanelMessageState {
    return {
        conversationKey,
        conversationMessages,
        messages: conversationMessages?.map((msg) => ({
            ...msg,
            status: "done" as const,
        })) ?? [],
    }
}

function abortActiveStream(streamAbortRef: MutableRef<AbortController | null>) {
    streamAbortRef.current?.abort()
}

// Action type icons
const ACTION_ICONS: Record<string, React.ReactNode> = {
    send_email: <MailIcon className="size-4" />,
    create_task: <ListTodoIcon className="size-4" />,
    add_note: <StickyNoteIcon className="size-4" />,
    update_status: <ArrowRightIcon className="size-4" />,
}

// Action type labels
const ACTION_LABELS: Record<string, string> = {
    send_email: "Send Email",
    create_task: "Create Task",
    add_note: "Add Note",
    update_status: "Update Stage",
}

type AIChatActionControls = {
    canApproveActions: boolean
    approvePending: boolean
    rejectPending: boolean
    onApprove: (approvalId: string | null | undefined) => void
    onReject: (approvalId: string | null | undefined) => void
}

function AIChatHeader({ onClose }: { onClose?: () => void }) {
    return (
        <div className="flex items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-2">
                <SparklesIcon className="size-5 text-primary" />
                <span className="font-semibold">AI Assistant</span>
            </div>
            {onClose ? (
                <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close AI Assistant">
                    <XIcon className="size-4" aria-hidden="true" />
                </Button>
            ) : null}
        </div>
    )
}

function AIChatContextBar({
    entityType,
    entityName,
}: {
    entityType: AIChatPanelProps["entityType"]
    entityName: AIChatPanelProps["entityName"]
}) {
    return (
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
    )
}

function AIChatEmptyState({ entityType }: { entityType: AIChatPanelProps["entityType"] }) {
    return (
        <div className="flex flex-col items-center justify-center py-8 text-center">
            <SparklesIcon className="mb-4 size-10 text-muted-foreground/50" />
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
    )
}

function AIChatMessageBubble({ message }: { message: PanelMessage }) {
    return (
        <div
            className={cn(
                "rounded-lg px-4 py-2",
                message.role === "user"
                    ? "ml-8 bg-primary text-primary-foreground"
                    : "mr-8 bg-muted"
            )}
        >
            {message.role === "assistant" && message.status === "thinking" && !message.content ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2Icon className="size-3.5 animate-spin" />
                    Thinking
                </div>
            ) : message.role === "assistant" ? (
                <AssistantRichText content={message.content} />
            ) : (
                <p className="whitespace-pre-wrap text-sm">{message.content}</p>
            )}
        </div>
    )
}

function AIChatActionCards({
    message,
    actionControls,
}: {
    message: PanelMessage
    actionControls: AIChatActionControls
}) {
    if (message.role !== "assistant" || !message.proposed_actions?.length) return null

    return (
        <div className="mt-2 mr-8 space-y-2">
            {message.proposed_actions.map((action: ProposedAction, index: number) => {
                const approval = message.action_approvals?.find(
                    (item) => item.action_index === index
                )
                const approvalId = action.approval_id
                const status = approval?.status || (approvalId ? "pending" : "unavailable")

                return (
                    <ActionCard
                        key={action.approval_id || index}
                        action={action}
                        status={status}
                        canApprove={
                            !!approvalId &&
                            actionControls.canApproveActions &&
                            status === "pending"
                        }
                        onApprove={() => actionControls.onApprove(approvalId)}
                        onReject={() => actionControls.onReject(approvalId)}
                        isApproving={actionControls.approvePending}
                        isRejecting={actionControls.rejectPending}
                    />
                )
            })}
        </div>
    )
}

function AIChatMessageList({
    messages,
    actionControls,
}: {
    messages: PanelMessage[]
    actionControls: AIChatActionControls
}) {
    return (
        <div className="space-y-4">
            {messages.map((message) => (
                <div key={message.id}>
                    <AIChatMessageBubble message={message} />
                    <AIChatActionCards message={message} actionControls={actionControls} />
                </div>
            ))}
        </div>
    )
}

function AIChatMessages({
    scrollRef,
    messages,
    loadingConversation,
    entityType,
    actionControls,
    onScroll,
}: {
    scrollRef: React.RefObject<HTMLDivElement | null>
    messages: PanelMessage[]
    loadingConversation: boolean
    entityType: AIChatPanelProps["entityType"]
    actionControls: AIChatActionControls
    onScroll: () => void
}) {
    return (
        <div ref={scrollRef} onScroll={onScroll} className="flex-1 min-h-0 overflow-y-auto">
            <div className="p-4">
                {loadingConversation ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    </div>
                ) : messages.length === 0 ? (
                    <AIChatEmptyState entityType={entityType} />
                ) : (
                    <AIChatMessageList messages={messages} actionControls={actionControls} />
                )}
            </div>
        </div>
    )
}

function AIChatQuickActions({
    entityType,
    entityId,
    streamVisible,
    onSetMessage,
    onOpenScheduleParser,
}: {
    entityType: AIChatPanelProps["entityType"]
    entityId: AIChatPanelProps["entityId"]
    streamVisible: boolean
    onSetMessage: (message: string) => void
    onOpenScheduleParser: () => void
}) {
    return (
        <div className="border-t px-4 py-2">
            <div className="flex flex-wrap gap-2">
                <QuickActionButton
                    onClick={() => onSetMessage("Summarize this surrogate")}
                    disabled={streamVisible}
                >
                    Summarize
                </QuickActionButton>
                <QuickActionButton
                    onClick={() => onSetMessage("What should I do next?")}
                    disabled={streamVisible}
                >
                    Next Steps
                </QuickActionButton>
                <QuickActionButton
                    onClick={() => onSetMessage("Draft a follow-up email")}
                    disabled={streamVisible}
                >
                    Draft Email
                </QuickActionButton>
                {entityType === "surrogate" && entityId ? (
                    <QuickActionButton onClick={onOpenScheduleParser} disabled={streamVisible}>
                        <CalendarPlusIcon className="mr-1 size-3" />
                        Parse Schedule
                    </QuickActionButton>
                ) : null}
            </div>
        </div>
    )
}

function AIChatComposer({
    inputRef,
    message,
    streamVisible,
    onMessageChange,
    onKeyDown,
    onSend,
    onStop,
}: {
    inputRef: React.RefObject<HTMLInputElement | null>
    message: string
    streamVisible: boolean
    onMessageChange: (message: string) => void
    onKeyDown: (event: React.KeyboardEvent) => void
    onSend: () => void
    onStop: () => void
}) {
    return (
        <div className="border-t p-4">
            <div className="flex gap-2">
                <Input
                    ref={inputRef}
                    value={message}
                    onChange={(event) => onMessageChange(event.target.value)}
                    onKeyDown={onKeyDown}
                    placeholder="Ask anything"
                    disabled={streamVisible}
                    className="flex-1"
                />
                {streamVisible ? (
                    <Button
                        onClick={onStop}
                        size="icon"
                        variant="outline"
                        aria-label="Stop generating"
                    >
                        <StopCircleIcon className="size-4" aria-hidden="true" />
                    </Button>
                ) : (
                    <Button
                        onClick={onSend}
                        disabled={!message.trim()}
                        size="icon"
                        aria-label="Send message"
                    >
                        <SendIcon className="size-4" aria-hidden="true" />
                    </Button>
                )}
            </div>
        </div>
    )
}

function AIChatScheduleParser({
    open,
    entityType,
    entityId,
    entityName,
    onOpenChange,
}: {
    open: boolean
    entityType: AIChatPanelProps["entityType"]
    entityId: AIChatPanelProps["entityId"]
    entityName: AIChatPanelProps["entityName"]
    onOpenChange: (open: boolean) => void
}) {
    if (!open || entityType !== "surrogate" || !entityId) return null

    return (
        <ScheduleParserDialog
            open={open}
            onOpenChange={onOpenChange}
            entityType="surrogate"
            entityId={entityId}
            {...(entityName ? { entityName } : {})}
        />
    )
}

export function AIChatPanel({
    entityType,
    entityId,
    entityName,
    canApproveActions = true,
    onClose,
}: AIChatPanelProps) {
    const [message, setMessage] = useState("")
    const [isStreaming, setIsStreaming] = useState(false)
    const [scheduleParserOpen, setScheduleParserOpen] = useState(false)
    const scrollRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLInputElement>(null)
    const streamAbortRef = useRef<AbortController | null>(null)
    const streamingMessageIdRef = useRef<string | null>(null)
    const stopRequestedRef = useRef(false)
    const shouldStickToBottomRef = useRef(true)
    const currentContext = {
        entityId: entityId ?? null,
        entityType: entityType ?? null,
    }
    const [trackedContext, setTrackedContext] = useState<PanelContext>(() => currentContext)

    // Hooks
    const { data: conversation, isLoading: loadingConversation } = useConversation(entityType, entityId)
    const streamMessage = useStreamChatMessage()
    const approveAction = useApproveAction()
    const rejectAction = useRejectAction()
    const conversationMessages = conversation?.messages
    const conversationKey = createConversationKey(currentContext, conversation?.conversation_id, conversationMessages)
    const [messageState, setMessageState] = useState<PanelMessageState>(() =>
        createPanelMessageState(conversationKey, conversationMessages)
    )
    const contextChanged =
        trackedContext.entityId !== currentContext.entityId || trackedContext.entityType !== currentContext.entityType

    if (contextChanged) {
        setTrackedContext(currentContext)
        if (isStreaming) {
            setIsStreaming(false)
        }
    }

    const streamVisible = isStreaming && !contextChanged
    const hasCurrentMessageState =
        messageState.conversationKey === conversationKey && messageState.conversationMessages === conversationMessages
    const derivedMessageState = hasCurrentMessageState
        ? messageState
        : createPanelMessageState(conversationKey, conversationMessages)

    if (!streamVisible && !hasCurrentMessageState) {
        setMessageState(derivedMessageState)
    }

    const messages = streamVisible || hasCurrentMessageState ? messageState.messages : derivedMessageState.messages

    const updateMessages = (updater: (currentMessages: PanelMessage[]) => PanelMessage[]) => {
        setMessageState((currentState) => {
            const baseState = currentState.conversationKey === conversationKey
                ? currentState
                : createPanelMessageState(conversationKey, conversationMessages)

            return {
                ...baseState,
                messages: updater(baseState.messages),
            }
        })
    }

    useAIChatScrollToLatest(scrollRef, messages, { shouldStickToBottomRef })

    useEffect(() => {
        shouldStickToBottomRef.current = true
        abortActiveStream(streamAbortRef)
        streamAbortRef.current = null
        streamingMessageIdRef.current = null
        stopRequestedRef.current = false
    }, [currentContext.entityId, currentContext.entityType])

    // Focus input on mount
    useMountEffect(() => {
        inputRef.current?.focus()
    })

    useMountEffect(() => {
        return () => {
            abortActiveStream(streamAbortRef)
        }
    })

    const updateMessageById = (id: string, updater: (msg: PanelMessage) => PanelMessage) => {
        updateMessages((currentMessages) => currentMessages.map((msg) => (msg.id === id ? updater(msg) : msg)))
    }

    const setAssistantError = (assistantId: string, errorText: string) => {
        updateMessageById(assistantId, (msg) => ({
            ...msg,
            content: errorText,
            status: "error",
        }))
    }

    const handleScroll = () => {
        const container = scrollRef.current
        if (!container) return
        shouldStickToBottomRef.current = isNearBottom(container)
    }

    const handleSend = async () => {
        const trimmedMessage = message.trim()
        if (!trimmedMessage || streamVisible) return

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

        shouldStickToBottomRef.current = true
        updateMessages((currentMessages) => [...currentMessages, userMessage, assistantMessage])
        setMessage("")

        abortActiveStream(streamAbortRef)
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
            } else {
                setAssistantError(
                    assistantId,
                    `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`
                )
            }
        }

        setIsStreaming(false)
        streamingMessageIdRef.current = null
        streamAbortRef.current = null
    }

    const handleStop = () => {
        if (!streamVisible) return
        stopRequestedRef.current = true
        abortActiveStream(streamAbortRef)
        setIsStreaming(false)
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            void handleSend()
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
    const actionControls: AIChatActionControls = {
        canApproveActions,
        approvePending: approveAction.isPending,
        rejectPending: rejectAction.isPending,
        onApprove: handleApprove,
        onReject: handleReject,
    }

    return (
        <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
            <AIChatHeader {...(onClose ? { onClose } : {})} />
            <AIChatContextBar entityType={entityType} entityName={entityName} />
            <AIChatMessages
                scrollRef={scrollRef}
                messages={messages}
                loadingConversation={loadingConversation}
                entityType={entityType}
                actionControls={actionControls}
                onScroll={handleScroll}
            />
            <AIChatQuickActions
                entityType={entityType}
                entityId={entityId}
                streamVisible={streamVisible}
                onSetMessage={setMessage}
                onOpenScheduleParser={() => setScheduleParserOpen(true)}
            />
            <AIChatComposer
                inputRef={inputRef}
                message={message}
                streamVisible={streamVisible}
                onMessageChange={setMessage}
                onKeyDown={handleKeyDown}
                onSend={() => void handleSend()}
                onStop={handleStop}
            />
            <AIChatScheduleParser
                open={scheduleParserOpen}
                entityType={entityType}
                entityId={entityId}
                entityName={entityName}
                onOpenChange={setScheduleParserOpen}
            />
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
    const icon = ACTION_ICONS[action.action_type] || <SparklesIcon className="size-4" />
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
                            className="size-7 text-destructive hover:bg-destructive/10"
                            onClick={onReject}
                            disabled={isRejecting}
                            aria-label="Reject action"
                        >
                            <XCircleIcon className="size-4" aria-hidden="true" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 text-green-600 hover:bg-green-600/10"
                            onClick={onApprove}
                            disabled={isApproving}
                            aria-label="Approve action"
                        >
                            {isApproving ? (
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                            ) : (
                                <CheckIcon className="size-4" aria-hidden="true" />
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
                    To: {String(data.to || "")}, Subject: {String(data.subject || "").slice(0, 30)}&hellip;
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
                    {String(data.content || data.body || data.text || "").slice(0, 50)}&hellip;
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

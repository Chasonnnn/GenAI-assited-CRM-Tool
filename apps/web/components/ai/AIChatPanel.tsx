"use client"

import * as React from "react"
import dynamic from "next/dynamic"
import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "@/components/ui/empty"
import { InputGroup, InputGroupAddon } from "@/components/ui/input-group"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import {
    ArrowUpIcon,
    SparklesIcon,
    XIcon,
    Loader2Icon,
    MailIcon,
    ListChecksIcon,
    ListTodoIcon,
    StickyNoteIcon,
    ArrowRightIcon,
    CalendarPlusIcon,
    LayoutDashboardIcon,
    RefreshCwIcon,
    ScanTextIcon,
    ShieldCheckIcon,
    StopCircleIcon,
    UserRoundIcon,
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
    entityContextLabel?: string | null
    entityStatusLabel?: string | null
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
    send_email: "Draft follow-up email",
    create_task: "Create task",
    add_note: "Add note",
    update_status: "Update stage",
}

type AIChatActionControls = {
    canApproveActions: boolean
    isApproving: (approvalId: string) => boolean
    isRejecting: (approvalId: string) => boolean
    getErrorMessage: (approvalId: string) => string | null
    onApprove: (approvalId: string | null | undefined) => void
    onReject: (approvalId: string | null | undefined) => void
}

function getProposedActionKey(messageId: string, action: ProposedAction) {
    return (
        action.approval_id ??
        `${messageId}:${action.action_type}:${JSON.stringify(action.action_data)}`
    )
}

function AIChatHeader({
    entityType,
    onClose,
}: {
    entityType: AIChatPanelProps["entityType"]
    onClose?: () => void
}) {
    const statusText =
        entityType === "surrogate"
            ? "Ready for this record"
            : entityType === "task"
                ? "Ready for this task"
                : "Ready for your workspace"

    return (
        <div className="flex min-h-14 items-center justify-between border-b px-3 py-2.5">
            <div className="flex min-w-0 items-center gap-2.5">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[linear-gradient(135deg,var(--primary-gradient-from),var(--primary-gradient-to))] text-primary-foreground shadow-sm">
                    <SparklesIcon className="size-5" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold">AI Assistant</h2>
                    <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
                        {statusText}
                    </p>
                </div>
            </div>
            {onClose ? (
                <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={onClose}
                    aria-label="Close AI Assistant"
                >
                    <XIcon className="size-4" aria-hidden="true" />
                </Button>
            ) : null}
        </div>
    )
}

function AIChatContextBar({
    entityType,
    entityName,
    entityContextLabel,
    entityStatusLabel,
}: {
    entityType: AIChatPanelProps["entityType"]
    entityName: AIChatPanelProps["entityName"]
    entityContextLabel: AIChatPanelProps["entityContextLabel"]
    entityStatusLabel: AIChatPanelProps["entityStatusLabel"]
}) {
    const contextLabel =
        entityContextLabel ??
        (entityType === "surrogate" && entityName
            ? `Surrogate • ${entityName}`
            : entityType === "task" && entityName
                ? `Task • ${entityName}`
                : "Workspace overview")
    const ContextIcon =
        entityType === "surrogate"
            ? UserRoundIcon
            : entityType === "task"
                ? ListTodoIcon
                : LayoutDashboardIcon

    return (
        <div className="border-b px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
                <Badge
                    variant="outline"
                    className="h-7 min-w-0 max-w-full gap-1.5 px-2.5 font-medium text-muted-foreground"
                >
                    <ContextIcon className="size-3.5 shrink-0" aria-hidden="true" />
                    <span className="truncate">{contextLabel}</span>
                </Badge>
                {entityStatusLabel ? (
                    <Badge
                        variant="secondary"
                        className="h-6 shrink-0 bg-emerald-500/10 px-2 text-[10px] text-emerald-700 dark:text-emerald-300"
                    >
                        {entityStatusLabel}
                    </Badge>
                ) : null}
            </div>
        </div>
    )
}

function AIChatEmptyState({ entityType }: { entityType: AIChatPanelProps["entityType"] }) {
    const title =
        entityType === "surrogate"
            ? "Ready to work on this surrogate"
            : entityType === "task"
                ? "Ready to help with this task"
                : "How can I help?"
    const description =
        entityType === "surrogate"
            ? "Summarize activity, identify the next step, draft follow-up, or ask about this record."
            : entityType === "task"
                ? "Summarize the task, plan the next step, or draft a clear follow-up."
                : "Ask a question, draft a message, or plan your next move across the workspace."

    return (
        <Empty className="min-h-[50vh] border-0 px-6 py-12">
            <EmptyHeader>
                <EmptyMedia
                    variant="icon"
                    className="size-12 rounded-xl bg-primary/10 text-primary"
                >
                    <SparklesIcon className="size-6" aria-hidden="true" />
                </EmptyMedia>
                <EmptyTitle className="text-base">{title}</EmptyTitle>
                <EmptyDescription className="max-w-xs text-xs">
                    {description}
                </EmptyDescription>
            </EmptyHeader>
        </Empty>
    )
}

function AIChatMessageBubble({ message }: { message: PanelMessage }) {
    const isUser = message.role === "user"

    return (
        <div className={cn("flex items-start gap-2", isUser ? "justify-end" : "justify-start")}>
            {!isUser ? (
                <Avatar
                    size="sm"
                    className="mt-0.5 rounded-lg after:rounded-lg"
                    aria-hidden="true"
                >
                    <AvatarFallback className="rounded-lg bg-primary/10 text-primary">
                        <SparklesIcon className="size-3.5" aria-hidden="true" />
                    </AvatarFallback>
                </Avatar>
            ) : null}
            <div
                className={cn(
                    "max-w-[calc(100%_-_2rem)] px-3 py-2 text-xs shadow-xs",
                    isUser
                        ? "rounded-[12px_5px_12px_12px] bg-[linear-gradient(135deg,var(--primary-gradient-from),var(--primary-gradient-to))] text-primary-foreground"
                        : "rounded-[5px_12px_12px_12px] border bg-card",
                    message.status === "error" && "border-destructive/40 bg-destructive/5"
                )}
            >
                {!isUser && message.status === "thinking" && !message.content ? (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
                        Thinking
                    </div>
                ) : !isUser ? (
                    <AssistantRichText content={message.content} className="text-xs" />
                ) : (
                    <p className="whitespace-pre-wrap text-xs">{message.content}</p>
                )}
            </div>
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
        <div className="mt-2 ml-8 space-y-2">
            {message.proposed_actions.map((action: ProposedAction, index: number) => {
                const approval = message.action_approvals?.find(
                    (item) => item.action_index === index
                )
                const approvalId = action.approval_id
                const status = approval?.status || (approvalId ? "pending" : "unavailable")

                return (
                    <ActionCard
                        key={getProposedActionKey(message.id, action)}
                        action={action}
                        status={status}
                        canApprove={
                            !!approvalId &&
                            actionControls.canApproveActions &&
                            status === "pending"
                        }
                        onApprove={() => actionControls.onApprove(approvalId)}
                        onReject={() => actionControls.onReject(approvalId)}
                        isApproving={approvalId ? actionControls.isApproving(approvalId) : false}
                        isRejecting={approvalId ? actionControls.isRejecting(approvalId) : false}
                        errorMessage={approvalId ? actionControls.getErrorMessage(approvalId) : null}
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
        <div className="space-y-3">
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
    conversationError,
    entityType,
    actionControls,
    onScroll,
    onRetry,
}: {
    scrollRef: React.RefObject<HTMLDivElement | null>
    messages: PanelMessage[]
    loadingConversation: boolean
    conversationError: boolean
    entityType: AIChatPanelProps["entityType"]
    actionControls: AIChatActionControls
    onScroll: () => void
    onRetry: () => void
}) {
    return (
        <div
            ref={scrollRef}
            onScroll={onScroll}
            role="log"
            aria-label="AI Assistant conversation"
            aria-live="polite"
            aria-relevant="additions"
            aria-busy={loadingConversation}
            className="min-h-0 flex-1 overflow-y-auto scroll-smooth"
        >
            <div className="p-3">
                {loadingConversation ? (
                    <div className="space-y-4 py-3" aria-label="Loading conversation">
                        <div className="flex items-start gap-2">
                            <Skeleton className="size-6 shrink-0 rounded-lg" />
                            <Skeleton className="h-16 w-4/5 rounded-xl" />
                        </div>
                        <div className="flex justify-end">
                            <Skeleton className="h-10 w-3/5 rounded-xl" />
                        </div>
                        <div className="flex items-start gap-2">
                            <Skeleton className="size-6 shrink-0 rounded-lg" />
                            <Skeleton className="h-20 w-3/4 rounded-xl" />
                        </div>
                    </div>
                ) : conversationError ? (
                    <Alert className="items-start">
                        <SparklesIcon className="size-4" aria-hidden="true" />
                        <AlertTitle>Couldn’t load this conversation</AlertTitle>
                        <AlertDescription>
                            Your draft is safe. Try loading the conversation history again.
                        </AlertDescription>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="col-start-2 mt-2 w-fit"
                            onClick={onRetry}
                        >
                            <RefreshCwIcon className="size-3.5" aria-hidden="true" />
                            Try again
                        </Button>
                    </Alert>
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
    const summarizePrompt =
        entityType === "task"
            ? "Summarize this task"
            : entityType === "surrogate"
                ? "Summarize recent activity for this surrogate"
                : "Summarize my current workload"
    const summarizeLabel =
        entityType === "task"
            ? "Summarize task"
            : entityType === "surrogate"
                ? "Summarize activity"
                : "Summarize workspace"
    const draftPrompt =
        entityType === "task"
            ? "Draft a progress update for this task"
            : "Draft a follow-up email"

    return (
        <div className="overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <div className="flex w-max min-w-full gap-1.5">
                <QuickActionButton
                    onClick={() => onSetMessage(summarizePrompt)}
                    disabled={streamVisible}
                >
                    <ListChecksIcon className="size-3" aria-hidden="true" />
                    {summarizeLabel}
                </QuickActionButton>
                <QuickActionButton
                    onClick={() => onSetMessage("What should I do next?")}
                    disabled={streamVisible}
                >
                    <ArrowRightIcon className="size-3" aria-hidden="true" />
                    Next step
                </QuickActionButton>
                <QuickActionButton
                    onClick={() => onSetMessage(draftPrompt)}
                    disabled={streamVisible}
                >
                    <MailIcon className="size-3" aria-hidden="true" />
                    {entityType === "task" ? "Draft update" : "Draft email"}
                </QuickActionButton>
                {entityType === "surrogate" && entityId ? (
                    <QuickActionButton onClick={onOpenScheduleParser} disabled={streamVisible}>
                        <CalendarPlusIcon className="size-3" aria-hidden="true" />
                        Parse Schedule
                    </QuickActionButton>
                ) : null}
            </div>
        </div>
    )
}

function AIChatComposer({
    inputRef,
    entityType,
    message,
    streamVisible,
    onMessageChange,
    onKeyDown,
    onSend,
    onStop,
}: {
    inputRef: React.RefObject<HTMLTextAreaElement | null>
    entityType: AIChatPanelProps["entityType"]
    message: string
    streamVisible: boolean
    onMessageChange: (message: string) => void
    onKeyDown: (event: React.KeyboardEvent) => void
    onSend: () => void
    onStop: () => void
}) {
    const placeholder =
        entityType === "surrogate"
            ? "Ask about this surrogate…"
            : entityType === "task"
                ? "Ask about this task…"
                : "Ask AI Assistant…"

    return (
        <div>
            <InputGroup className="h-auto items-end rounded-xl bg-card p-1 shadow-sm">
                <Textarea
                    ref={inputRef}
                    value={message}
                    onChange={(event) => onMessageChange(event.target.value)}
                    onKeyDown={onKeyDown}
                    aria-label="Message AI Assistant"
                    placeholder={placeholder}
                    rows={2}
                    disabled={streamVisible}
                    className="min-h-12 max-h-28 flex-1 border-0 bg-transparent px-2.5 py-2 text-sm shadow-none focus-visible:border-transparent focus-visible:ring-0"
                />
                <InputGroupAddon
                    align="inline-end"
                    className="self-stretch items-end px-1.5 py-1.5"
                >
                    {streamVisible ? (
                        <Button
                            type="button"
                            onClick={onStop}
                            size="icon-sm"
                            variant="outline"
                            className="rounded-lg"
                            aria-label="Stop generating"
                        >
                            <StopCircleIcon className="size-4" aria-hidden="true" />
                        </Button>
                    ) : (
                        <Button
                            type="button"
                            onClick={onSend}
                            disabled={!message.trim()}
                            size="icon-sm"
                            className="rounded-lg"
                            aria-label="Send message"
                        >
                            <ArrowUpIcon className="size-4" aria-hidden="true" />
                        </Button>
                    )}
                </InputGroupAddon>
            </InputGroup>
            <div className="mt-1.5 flex items-center justify-between gap-2 px-0.5 text-[9px] text-muted-foreground/80">
                <span className="flex items-center gap-1">
                    <ShieldCheckIcon className="size-3" aria-hidden="true" />
                    Review AI output before acting
                </span>
                <span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span>
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

function AIChatPanelContent({
    entityType,
    entityId,
    entityName,
    entityContextLabel,
    entityStatusLabel,
    canApproveActions = true,
    onClose,
}: AIChatPanelProps) {
    const [message, setMessage] = useState("")
    const [isStreaming, setIsStreaming] = useState(false)
    const [scheduleParserOpen, setScheduleParserOpen] = useState(false)
    const scrollRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)
    const streamAbortRef = useRef<AbortController | null>(null)
    const streamingMessageIdRef = useRef<string | null>(null)
    const stoppedStreamsRef = useRef(new WeakSet<AbortController>())
    const shouldStickToBottomRef = useRef(true)
    const currentContext = {
        entityId: entityId ?? null,
        entityType: entityType ?? null,
    }

    // Hooks
    const {
        data: conversation,
        isLoading: loadingConversation,
        isError: conversationError,
        refetch: refetchConversation,
    } = useConversation(entityType, entityId)
    const streamMessage = useStreamChatMessage()
    const approveAction = useApproveAction()
    const rejectAction = useRejectAction()
    const conversationMessages = conversation?.messages
    const conversationKey = createConversationKey(currentContext, conversation?.conversation_id, conversationMessages)
    const [messageState, setMessageState] = useState<PanelMessageState>(() =>
        createPanelMessageState(conversationKey, conversationMessages)
    )
    const streamVisible = isStreaming
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
                if (stoppedStreamsRef.current.has(controller)) {
                    updateMessageById(assistantId, (msg) => ({
                        ...msg,
                        content: msg.content || "Stopped.",
                        status: "done",
                    }))
                }
            } else {
                setAssistantError(
                    assistantId,
                    `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`
                )
            }
        }

        if (streamAbortRef.current === controller) {
            setIsStreaming(false)
            streamingMessageIdRef.current = null
            streamAbortRef.current = null
        }
    }

    const handleStop = () => {
        if (!streamVisible) return
        if (streamAbortRef.current) {
            stoppedStreamsRef.current.add(streamAbortRef.current)
        }
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
        isApproving: (approvalId) =>
            approveAction.isPending && approveAction.variables === approvalId,
        isRejecting: (approvalId) =>
            rejectAction.isPending && rejectAction.variables === approvalId,
        getErrorMessage: (approvalId) =>
            (approveAction.error && approveAction.variables === approvalId) ||
            (rejectAction.error && rejectAction.variables === approvalId)
                ? "This action couldn’t be completed. Review it and try again."
                : null,
        onApprove: handleApprove,
        onReject: handleReject,
    }

    return (
        <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
            <AIChatHeader entityType={entityType} {...(onClose ? { onClose } : {})} />
            <AIChatContextBar
                entityType={entityType}
                entityName={entityName}
                entityContextLabel={entityContextLabel}
                entityStatusLabel={entityStatusLabel}
            />
            <AIChatMessages
                scrollRef={scrollRef}
                messages={messages}
                loadingConversation={loadingConversation}
                conversationError={conversationError}
                entityType={entityType}
                actionControls={actionControls}
                onScroll={handleScroll}
                onRetry={() => void refetchConversation()}
            />
            <div className="shrink-0 border-t bg-background/95 px-3 py-2.5 shadow-[0_-12px_24px_rgba(0,0,0,0.08)] backdrop-blur">
                <AIChatQuickActions
                    entityType={entityType}
                    entityId={entityId}
                    streamVisible={streamVisible}
                    onSetMessage={setMessage}
                    onOpenScheduleParser={() => setScheduleParserOpen(true)}
                />
                <AIChatComposer
                    inputRef={inputRef}
                    entityType={entityType}
                    message={message}
                    streamVisible={streamVisible}
                    onMessageChange={setMessage}
                    onKeyDown={handleKeyDown}
                    onSend={() => void handleSend()}
                    onStop={handleStop}
                />
            </div>
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

export function AIChatPanel(props: AIChatPanelProps) {
    const contextKey = `${props.entityType ?? "global"}:${props.entityId ?? "global"}`

    return <AIChatPanelContent key={contextKey} {...props} />
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
    errorMessage: string | null
}

const ACTION_STATUS_LABELS: Record<string, string> = {
    pending: "Needs review",
    approved: "Approved",
    executed: "Done",
    rejected: "Dismissed",
    failed: "Failed",
    unavailable: "Unavailable",
}

function getActionText(
    data: Record<string, unknown>,
    keys: string[]
): string | null {
    for (const key of keys) {
        const value = data[key]
        if (typeof value === "string" && value.trim()) {
            return value.trim()
        }
    }
    return null
}

function humanizeActionValue(value: string) {
    return value
        .replace(/[_-]+/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function getActionReviewLabel(actionType: string, expanded: boolean) {
    if (actionType === "send_email") {
        return expanded ? "Hide draft" : "Review draft"
    }
    return expanded ? "Hide details" : "Review action"
}

function getActionExecuteLabel(actionType: string) {
    if (actionType === "send_email") return "Approve and send"
    if (actionType === "create_task") return "Approve and create"
    if (actionType === "add_note") return "Approve and add"
    if (actionType === "update_status") return "Approve and update"
    return "Approve and run"
}

function ActionCard({
    action,
    status,
    canApprove,
    onApprove,
    onReject,
    isApproving,
    isRejecting,
    errorMessage,
}: ActionCardProps) {
    const [expanded, setExpanded] = useState(false)
    const titleId = React.useId()
    const detailsId = React.useId()
    const icon = ACTION_ICONS[action.action_type] || <SparklesIcon className="size-4" />
    const label = ACTION_LABELS[action.action_type] || humanizeActionValue(action.action_type)
    const statusLabel = ACTION_STATUS_LABELS[status] ?? "Status unavailable"
    const isPending = status === "pending"
    const reviewLabel = getActionReviewLabel(action.action_type, expanded)
    const executeLabel = getActionExecuteLabel(action.action_type)

    return (
        <Card
            role="article"
            aria-labelledby={titleId}
            className="gap-0 overflow-hidden border-primary/25 bg-card py-0 shadow-sm"
        >
            <div className="flex items-start justify-between gap-3 px-3 pt-3">
                <div className="flex min-w-0 items-center gap-2">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        {icon}
                    </div>
                    <div className="min-w-0">
                        <p id={titleId} className="truncate text-sm font-semibold">
                            {label}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                            {isPending ? "Human review required" : "AI action proposal"}
                        </p>
                    </div>
                </div>
                <Badge
                    variant={status === "executed" ? "default" : "outline"}
                    className={cn(
                        "text-[10px]",
                        isPending && "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
                        status === "rejected" && "text-muted-foreground",
                        status === "failed" && "border-destructive/30 bg-destructive/10 text-destructive"
                    )}
                >
                    {statusLabel}
                </Badge>
            </div>

            <div className="mx-3 mt-2 rounded-lg border bg-background/40 px-2.5 py-2">
                <ActionPreview type={action.action_type} data={action.action_data} />
            </div>

            {expanded ? (
                <div
                    id={detailsId}
                    className="mx-3 mt-2 rounded-lg border bg-background/70 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground"
                >
                    <ActionDetails type={action.action_type} data={action.action_data} />
                </div>
            ) : null}

            {errorMessage ? (
                <div
                    role="alert"
                    className="mx-3 mt-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
                >
                    {errorMessage}
                </div>
            ) : null}

            {isPending ? (
                <div className="flex flex-wrap gap-2 px-3 py-3">
                    <Button
                        type="button"
                        variant={expanded ? "outline" : "default"}
                        size="sm"
                        className="h-8"
                        onClick={() => setExpanded((current) => !current)}
                        aria-expanded={expanded}
                        aria-controls={detailsId}
                        disabled={isApproving || isRejecting}
                    >
                        <ScanTextIcon className="size-3.5" aria-hidden="true" />
                        {reviewLabel}
                    </Button>
                    {expanded && canApprove ? (
                        <Button
                            type="button"
                            size="sm"
                            className="h-8"
                            onClick={onApprove}
                            disabled={isApproving || isRejecting}
                        >
                            {isApproving ? (
                                <Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
                            ) : null}
                            {executeLabel}
                        </Button>
                    ) : null}
                    {canApprove ? (
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-8"
                            onClick={onReject}
                            disabled={isApproving || isRejecting}
                        >
                            {isRejecting ? (
                                <Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
                            ) : null}
                            Dismiss
                        </Button>
                    ) : null}
                </div>
            ) : (
                <div className="h-3" aria-hidden="true" />
            )}
        </Card>
    )
}

// Action preview component
function ActionPreview({ type, data }: { type: string; data: Record<string, unknown> }) {
    switch (type) {
        case "send_email": {
            const recipient = getActionText(data, ["to", "recipient_email", "recipient"]) ?? "Recipient not provided"
            const subject = getActionText(data, ["subject"]) ?? "Subject not provided"
            return (
                <div className="grid gap-1 text-[11px] text-muted-foreground">
                    <p className="grid grid-cols-[3rem_minmax(0,1fr)] gap-2">
                        <span>To</span>
                        <strong className="truncate font-medium text-foreground">{recipient}</strong>
                    </p>
                    <p className="grid grid-cols-[3rem_minmax(0,1fr)] gap-2">
                        <span>Subject</span>
                        <strong className="truncate font-medium text-foreground">{subject}</strong>
                    </p>
                </div>
            )
        }
        case "create_task": {
            const title = getActionText(data, ["title"]) ?? "Untitled task"
            const dueDate = getActionText(data, ["due_date"])
            return (
                <p className="text-xs text-muted-foreground">
                    <strong className="font-medium text-foreground">{title}</strong>
                    {dueDate ? ` · Due ${dueDate}` : ""}
                </p>
            )
        }
        case "add_note": {
            const note = getActionText(data, ["content", "body", "text"]) ?? "Note content not provided"
            return (
                <p className="text-xs text-muted-foreground">
                    {note.length > 80 ? `${note.slice(0, 80)}…` : note}
                </p>
            )
        }
        case "update_status": {
            const rawStage = getActionText(data, ["stage_label", "target_stage_label", "status_label", "status"])
            const stageLabel = rawStage
                ? humanizeActionValue(rawStage)
                : "Selected pipeline stage"
            return (
                <p className="text-xs text-muted-foreground">
                    Change to <strong className="font-medium text-foreground">{stageLabel}</strong>
                </p>
            )
        }
        default:
            return <p className="text-xs text-muted-foreground">Review the proposed change before continuing.</p>
    }
}

function ActionDetails({ type, data }: { type: string; data: Record<string, unknown> }) {
    switch (type) {
        case "send_email":
            return (
                <p className="whitespace-pre-wrap text-foreground">
                    {getActionText(data, ["body", "content", "message"]) ?? "No draft body was provided."}
                </p>
            )
        case "create_task":
            return (
                <p className="whitespace-pre-wrap text-foreground">
                    {getActionText(data, ["description", "notes"]) ?? "No additional task details were provided."}
                </p>
            )
        case "add_note":
            return (
                <p className="whitespace-pre-wrap text-foreground">
                    {getActionText(data, ["content", "body", "text"]) ?? "No note content was provided."}
                </p>
            )
        case "update_status":
            return <ActionPreview type={type} data={data} />
        default:
            return <p>Review this action carefully before approving it.</p>
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
            className="h-7 rounded-full px-2.5 text-[10px]"
        >
            {children}
        </Button>
    )
}

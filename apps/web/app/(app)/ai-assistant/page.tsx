"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { SendIcon, SparklesIcon, FileTextIcon, UserIcon, CalendarIcon, ClockIcon, BotIcon, Loader2Icon, AlertCircleIcon, CheckIcon, XIcon, StopCircleIcon, type LucideIcon } from "lucide-react"
import { useEffect, useReducer, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from "react"
import { useMountEffect } from "@/lib/hooks/use-mount-effect"
import { useStreamChatMessage, useAISettings, useApproveAction, useRejectAction } from "@/lib/hooks/use-ai"
import { useAuth } from "@/lib/auth-context"
import { AssistantRichText } from "@/components/ai/AssistantRichText"

interface Message {
    id: string
    role: "user" | "assistant"
    content: string
    timestamp: string
    proposed_actions?: ProposedAction[]
    status?: "thinking" | "streaming" | "done" | "error"
}

interface ProposedAction {
    approval_id: string | null
    action_type: string
    action_data: Record<string, unknown>
    status: string
}

interface ChatSession {
    id: string
    label: string
    preview: string
    updatedAt: string
    entityType: "global"
    entityId: null
    conversationId: string | null
    messages: Message[]
}

const CHAT_HISTORY_KEY = "ai-assistant-chat-history-v1"
const CHAT_HISTORY_USER_KEY = "ai-assistant-chat-history-user-v1"
const MAX_CHAT_HISTORY = 10
const SESSION_MESSAGE_LIMIT = 50
const SESSION_PREVIEW_LIMIT = 80

const QUICK_ACTIONS: QuickAction[] = [
    { icon: FileTextIcon, label: "Summarize top priorities", color: "text-blue-500" },
    { icon: UserIcon, label: "Draft a team follow-up email", color: "text-green-500" },
    { icon: CalendarIcon, label: "What are the next steps?", color: "text-purple-500" },
    { icon: ClockIcon, label: "Create a task list", color: "text-orange-500" },
]

const SUGGESTED_ACTIONS = [
    "What should I focus on today?",
    "Are there any pending tasks?",
    "Summarize recent activity",
    "Draft an internal follow-up email",
]

type QuickAction = {
    icon: LucideIcon
    label: string
    color: string
}

type ChatState = {
    chatHistory: ChatSession[]
    activeSessionId: string | null
    messages: Message[]
}

type ChatAction =
    | { type: "patch"; payload: Partial<ChatState> }
    | { type: "update_history"; updater: (prev: ChatSession[]) => ChatSession[] }

type ChatDispatch = (action: ChatAction) => void
type ChatStateRef = { current: ChatState }

function createWelcomeMessage(): Message {
    return {
        id: "welcome",
        role: "assistant",
        content: "Hello! I'm your AI assistant. Ask me anything about your workflows.",
        timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
        status: "done",
    }
}

function buildInitialChatState(): ChatState {
    return {
        chatHistory: [],
        activeSessionId: null,
        messages: [createWelcomeMessage()],
    }
}

function resolveStateValue<T>(value: T | ((prev: T) => T), previous: T): T {
    return typeof value === "function"
        ? (value as (prev: T) => T)(previous)
        : value
}

function chatReducer(state: ChatState, action: ChatAction): ChatState {
    switch (action.type) {
        case "patch":
            return { ...state, ...action.payload }
        case "update_history":
            return { ...state, chatHistory: action.updater(state.chatHistory) }
        default:
            return state
    }
}

function truncateText(text: string, max: number) {
    if (text.length <= max) return text
    return `${text.slice(0, max)}&hellip;`
}

function formatHistoryTime(value: string) {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ""
    return date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
}

function normalizeMessagesForSession(messages: Message[]) {
    const normalizedMessages: Message[] = []
    for (const msg of messages) {
        if (msg.id === "welcome") continue
        const normalizedStatus =
            msg.status === "thinking" || msg.status === "streaming"
                ? "done"
                : msg.status ?? "done"
        normalizedMessages.push({
            ...msg,
            status: normalizedStatus,
        })
    }
    return normalizedMessages.slice(-SESSION_MESSAGE_LIMIT)
}

function patchChatState(
    dispatchChat: ChatDispatch,
    chatStateRef: ChatStateRef,
    payload: Partial<ChatState>
) {
    chatStateRef.current = { ...chatStateRef.current, ...payload }
    dispatchChat({ type: "patch", payload })
}

function setChatMessages(
    dispatchChat: ChatDispatch,
    chatStateRef: ChatStateRef,
    value: Message[] | ((prev: Message[]) => Message[])
) {
    const next = resolveStateValue(value, chatStateRef.current.messages)
    patchChatState(dispatchChat, chatStateRef, { messages: next })
}

function setActiveChatSessionId(
    dispatchChat: ChatDispatch,
    chatStateRef: ChatStateRef,
    value: string | null
) {
    patchChatState(dispatchChat, chatStateRef, { activeSessionId: value })
}

function persistHistory(next: ChatSession[]) {
    if (typeof window === "undefined") return
    sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(next))
}

function updateHistory(
    dispatchChat: ChatDispatch,
    chatStateRef: ChatStateRef,
    updater: (prev: ChatSession[]) => ChatSession[]
) {
    const next = updater(chatStateRef.current.chatHistory)
    persistHistory(next)
    patchChatState(dispatchChat, chatStateRef, { chatHistory: next })
}

function buildSessionLabel() {
    return "Global Chat"
}

function derivePreview(sessionMessages: Message[]) {
    const lastUserMessage = [...sessionMessages].reverse().find((msg) => msg.role === "user" && msg.content)
    if (!lastUserMessage) return ""
    return truncateText(lastUserMessage.content, SESSION_PREVIEW_LIMIT)
}

function upsertSession(
    dispatchChat: ChatDispatch,
    chatStateRef: ChatStateRef,
    session: ChatSession
) {
    updateHistory(dispatchChat, chatStateRef, (prev) => {
        const filtered = prev.filter((item) => item.id !== session.id)
        const next = [session, ...filtered].slice(0, MAX_CHAT_HISTORY)
        return next
    })
}

function updateSessionMessages(
    dispatchChat: ChatDispatch,
    chatStateRef: ChatStateRef,
    chatHistory: ChatSession[],
    sessionId: string,
    sessionMessages: Message[],
    options?: { conversationId?: string | null }
) {
    const normalized = normalizeMessagesForSession(sessionMessages)
    const existing = chatHistory.find((session) => session.id === sessionId)
    const conversationId = options?.conversationId ?? existing?.conversationId ?? null
    const session: ChatSession = {
        id: sessionId,
        label: buildSessionLabel(),
        preview: derivePreview(sessionMessages),
        updatedAt: new Date().toISOString(),
        entityType: "global",
        entityId: null,
        conversationId,
        messages: normalized,
    }
    upsertSession(dispatchChat, chatStateRef, session)
}

function clearChatHistory(dispatchChat: ChatDispatch, chatStateRef: ChatStateRef) {
    patchChatState(dispatchChat, chatStateRef, {
        chatHistory: [],
        activeSessionId: null,
        messages: [createWelcomeMessage()],
    })
    if (typeof window !== "undefined") {
        sessionStorage.removeItem(CHAT_HISTORY_KEY)
        sessionStorage.removeItem(CHAT_HISTORY_USER_KEY)
    }
}

function createTimestampId(prefix: string) {
    return `${prefix}-${Date.now()}`
}

function safeParseHistory(raw: string | null): ChatSession[] {
    if (!raw) return []
    try {
        const parsed = JSON.parse(raw)
        if (!Array.isArray(parsed)) return []
        const sessions: ChatSession[] = []
        for (const entry of parsed) {
            if (!entry || typeof entry !== "object") continue
            const record = entry as Record<string, unknown>
            const hasSurrogateContext =
                record.entityType === "surrogate" || typeof record.entityId === "string"
            if (hasSurrogateContext) continue

            const id = typeof record.id === "string" ? record.id : createTimestampId("session")
            const label = typeof record.label === "string" ? record.label : "Chat"
            const preview = typeof record.preview === "string" ? record.preview : ""
            const updatedAt =
                typeof record.updatedAt === "string" ? record.updatedAt : new Date().toISOString()
            const conversationId =
                typeof record.conversationId === "string" ? record.conversationId : null
            const rawMessages = Array.isArray(record.messages) ? record.messages : []
            const messages: Message[] = []

            for (const msg of rawMessages) {
                if (!msg || typeof msg !== "object") continue
                const messageRecord = msg as Record<string, unknown>
                const rawStatus = messageRecord.status
                const status =
                    rawStatus === "thinking" ||
                    rawStatus === "streaming" ||
                    rawStatus === "done" ||
                    rawStatus === "error"
                        ? rawStatus
                        : undefined
                const rawRole = messageRecord.role
                const rawTimestamp = messageRecord.timestamp
                const rawContent = messageRecord.content
                const rawActions = messageRecord.proposed_actions
                const proposed_actions = Array.isArray(rawActions) ? rawActions as ProposedAction[] : undefined
                messages.push({
                    id: typeof messageRecord.id === "string" ? messageRecord.id : createTimestampId("msg"),
                    role: rawRole === "assistant" ? "assistant" : "user",
                    content: typeof rawContent === "string" ? rawContent : "",
                    timestamp:
                        typeof rawTimestamp === "string"
                            ? rawTimestamp
                            : new Date().toLocaleTimeString("en-US", {
                                  hour: "numeric",
                                  minute: "2-digit",
                              }),
                    ...(proposed_actions ? { proposed_actions } : {}),
                    ...(status ? { status } : {}),
                })
            }

            sessions.push({
                id,
                label,
                preview,
                updatedAt,
                entityType: "global",
                entityId: null,
                conversationId,
                messages,
            })
            if (sessions.length >= MAX_CHAT_HISTORY) break
        }
        return sessions
    } catch {
        return []
    }
}

function useAIAssistantChat() {
    const { user } = useAuth()
    const [message, setMessage] = useState("")
    const [isStreaming, setIsStreaming] = useState(false)
    const [chatState, dispatchChat] = useReducer(chatReducer, undefined, buildInitialChatState)
    const chatStateRef = useRef(chatState)
    const { chatHistory, activeSessionId, messages } = chatState
    const scrollRef = useRef<HTMLDivElement>(null)
    const streamingMessageIdRef = useRef<string | null>(null)
    const streamAbortRef = useRef<AbortController | null>(null)
    const stopRequestedRef = useRef(false)

    useEffect(() => {
        chatStateRef.current = chatState
    }, [chatState])

    const setMessages = (value: Message[] | ((prev: Message[]) => Message[])) => {
        setChatMessages(dispatchChat, chatStateRef, value)
    }

    const setActiveSessionId = (value: string | null) => {
        setActiveChatSessionId(dispatchChat, chatStateRef, value)
    }

    const aiSettingsQuery = useAISettings()
    const {
        data: aiSettings,
        isError: aiSettingsError,
        error: aiSettingsErrorData,
    } = aiSettingsQuery
    const streamMessage = useStreamChatMessage()
    const approveAction = useApproveAction()
    const rejectAction = useRejectAction()

    const aiSettingsErrorMessage = aiSettingsErrorData instanceof Error ? aiSettingsErrorData.message : ""

    const historyLoadedRef = useRef(false)
    const initialSessionCreatedRef = useRef(false)

    useEffect(() => {
        if (typeof window === "undefined") return
        if (!user?.user_id) {
            historyLoadedRef.current = false
            initialSessionCreatedRef.current = false
            clearChatHistory(dispatchChat, chatStateRef)
            return
        }
        const storedUserId = sessionStorage.getItem(CHAT_HISTORY_USER_KEY)
        if (storedUserId && storedUserId !== user.user_id) {
            clearChatHistory(dispatchChat, chatStateRef)
            historyLoadedRef.current = false
            initialSessionCreatedRef.current = false
        }
        if (!historyLoadedRef.current) {
            const storedHistory = safeParseHistory(sessionStorage.getItem(CHAT_HISTORY_KEY))
            patchChatState(dispatchChat, chatStateRef, {
                chatHistory: storedHistory,
                activeSessionId: null,
                messages: [createWelcomeMessage()],
            })
            historyLoadedRef.current = true
        }
        sessionStorage.setItem(CHAT_HISTORY_USER_KEY, user.user_id)
    }, [user?.user_id])

    useEffect(() => {
        if (!user?.user_id || !historyLoadedRef.current || initialSessionCreatedRef.current) return
        initialSessionCreatedRef.current = true
        const sessionId = createTimestampId("session")
        upsertSession(dispatchChat, chatStateRef, {
            id: sessionId,
            label: buildSessionLabel(),
            preview: "",
            updatedAt: new Date().toISOString(),
            entityType: "global",
            entityId: null,
            conversationId: null,
            messages: [],
        })
        patchChatState(dispatchChat, chatStateRef, {
            activeSessionId: sessionId,
            messages: [createWelcomeMessage()],
        })
    }, [user?.user_id])

    const currentSession = chatHistory.find((session) => session.id === activeSessionId) || null

    useEffect(() => {
        if (isStreaming) return
        if (currentSession) {
            const sessionMessages = currentSession.messages.length
                ? currentSession.messages
                : [createWelcomeMessage()]
            setChatMessages(dispatchChat, chatStateRef, sessionMessages)
            return
        }
        setChatMessages(dispatchChat, chatStateRef, [createWelcomeMessage()])
    }, [currentSession, isStreaming])

    // Scroll to bottom when messages change
    useEffect(() => {
        const container = scrollRef.current
        if (!container) return
        container.scrollTop = container.scrollHeight
    }, [messages])

    // The unmount cleanup intentionally aborts the latest active stream, not the
    // controller that existed when this effect was registered.
    // oxlint-disable-next-line react-doctor/exhaustive-deps
    useMountEffect(() => {
        return () => {
            streamAbortRef.current?.abort()
        }
    })

    const ensureSessionId = () => {
        if (activeSessionId && chatHistory.some((session) => session.id === activeSessionId)) {
            return activeSessionId
        }

        const sessionId = createTimestampId("session")
        upsertSession(dispatchChat, chatStateRef, {
            id: sessionId,
            label: buildSessionLabel(),
            preview: "",
            updatedAt: new Date().toISOString(),
            entityType: "global",
            entityId: null,
            conversationId: null,
            messages: [],
        })
        setActiveSessionId(sessionId)
        return sessionId
    }

    const updateMessageById = (id: string, updater: (msg: Message) => Message) => {
        setMessages((prev) => prev.map((msg) => (msg.id === id ? updater(msg) : msg)))
    }

    const updateMessageAndSession = (
        id: string,
        updater: (msg: Message) => Message,
        sessionId: string,
        options?: { conversationId?: string | null }
    ) => {
        setMessages((prev) => {
            const next = prev.map((msg) => (msg.id === id ? updater(msg) : msg))
            updateSessionMessages(dispatchChat, chatStateRef, chatHistory, sessionId, next, options)
            return next
        })
    }

    const handleSelectSession = (session: ChatSession) => {
        setActiveSessionId(session.id)
        const sessionMessages = session.messages.length ? session.messages : [createWelcomeMessage()]
        setMessages(sessionMessages)
    }

    const handleNewChat = () => {
        const sessionId = createTimestampId("session")
        upsertSession(dispatchChat, chatStateRef, {
            id: sessionId,
            label: buildSessionLabel(),
            preview: "",
            updatedAt: new Date().toISOString(),
            entityType: "global",
            entityId: null,
            conversationId: null,
            messages: [],
        })
        setActiveSessionId(sessionId)
        setMessages([createWelcomeMessage()])
    }

    const setAssistantError = (
        assistantId: string,
        errorText: string,
        sessionId?: string
    ) => {
        if (sessionId) {
            updateMessageAndSession(
                assistantId,
                (msg) => ({
                    ...msg,
                    content: errorText,
                    status: "error",
                }),
                sessionId
            )
            return
        }
        updateMessageById(assistantId, (msg) => ({
            ...msg,
            content: errorText,
            status: "error",
        }))
    }

    const handleSend = async () => {
        const trimmedMessage = message.trim()
        if (!trimmedMessage || !isAIEnabled || isStreaming) return

        const sessionId = ensureSessionId()
        const sessionConversationId =
            chatHistory.find((session) => session.id === sessionId)?.conversationId ?? null

        const timestamp = new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
        const userMessage: Message = {
            id: createTimestampId("user"),
            role: "user",
            content: trimmedMessage,
            timestamp,
            status: "done",
        }
        const assistantId = createTimestampId("assistant")
        const assistantMessage: Message = {
            id: assistantId,
            role: "assistant",
            content: "",
            timestamp,
            status: "thinking",
        }

        setMessages((prev) => {
            const next = [...prev, userMessage, assistantMessage]
            updateSessionMessages(dispatchChat, chatStateRef, chatHistory, sessionId, next)
            return next
        })
        setMessage("")

        streamAbortRef.current?.abort()
        stopRequestedRef.current = false
        const controller = new AbortController()
        streamAbortRef.current = controller
        streamingMessageIdRef.current = assistantId
        setIsStreaming(true)
        const finishStreaming = () => {
            setIsStreaming(false)
            streamingMessageIdRef.current = null
        }

        try {
            const request = {
                message: trimmedMessage,
                ...(sessionConversationId ? { conversation_id: sessionConversationId } : {}),
            }
            await streamMessage(
                request,
                (event) => {
                    if (event.type === 'start') {
                        updateMessageById(assistantId, (msg) => ({
                            ...msg,
                            status: "thinking",
                        }))
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
                        updateMessageAndSession(
                            assistantId,
                            (msg) => ({
                                ...msg,
                                content: event.data.content,
                                proposed_actions: event.data.proposed_actions,
                                status: "done",
                                timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
                            }),
                            sessionId,
                            { conversationId: event.data.conversation_id ?? null }
                        )
                        return
                    }

                    if (event.type === 'error') {
                        setAssistantError(
                            assistantId,
                            `Sorry, I encountered an error: ${event.data.message || 'Unknown error'}. Please try again.`,
                            sessionId
                        )
                    }
                },
                controller.signal
            )
        } catch (error) {
            if (error instanceof DOMException && error.name === 'AbortError') {
                if (stopRequestedRef.current) {
                    updateMessageAndSession(
                        assistantId,
                        (msg) => ({
                            ...msg,
                            content: msg.content || "Stopped.",
                            status: "done",
                        }),
                        sessionId
                    )
                }
                stopRequestedRef.current = false
                finishStreaming()
                return
            }
            setAssistantError(
                assistantId,
                `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
                sessionId
            )
        }
        finishStreaming()
    }

    const handleStop = () => {
        if (!isStreaming) return
        stopRequestedRef.current = true
        streamAbortRef.current?.abort()
        setIsStreaming(false)
    }

    const syncSessionFromMessages = (nextMessages: Message[]) => {
        if (!activeSessionId) return
        updateSessionMessages(dispatchChat, chatStateRef, chatHistory, activeSessionId, nextMessages)
    }

    const handleApprove = async (approvalId: string | null) => {
        if (!approvalId) return
        try {
            await approveAction.mutateAsync(approvalId)
            // Update the action status in messages
            setMessages(prev => {
                const next = prev.map(msg => {
                    if (!msg.proposed_actions) return msg
                    return {
                        ...msg,
                        proposed_actions: msg.proposed_actions.map(action =>
                            action.approval_id === approvalId ? { ...action, status: 'approved' } : action
                        ),
                    }
                })
                syncSessionFromMessages(next)
                return next
            })
        } catch (error) {
            console.error('Failed to approve action:', error)
        }
    }

    const handleReject = async (approvalId: string | null) => {
        if (!approvalId) return
        try {
            await rejectAction.mutateAsync(approvalId)
            setMessages(prev => {
                const next = prev.map(msg => {
                    if (!msg.proposed_actions) return msg
                    return {
                        ...msg,
                        proposed_actions: msg.proposed_actions.map(action =>
                            action.approval_id === approvalId ? { ...action, status: 'rejected' } : action
                        ),
                    }
                })
                syncSessionFromMessages(next)
                return next
            })
        } catch (error) {
            console.error('Failed to reject action:', error)
        }
    }

    const isAIEnabled = Boolean(aiSettings?.is_enabled)
    const modelName = aiSettings?.model || aiSettings?.provider?.toUpperCase() || 'AI'

    return {
        activeSessionId,
        aiSettingsError,
        aiSettingsErrorMessage,
        approveActionPending: approveAction.isPending,
        chatHistory,
        handleApprove,
        handleNewChat,
        handleReject,
        handleSelectSession,
        handleSend,
        handleStop,
        isAIEnabled,
        isStreaming,
        message,
        messages,
        modelName,
        refetchAISettings: aiSettingsQuery.refetch,
        rejectActionPending: rejectAction.isPending,
        scrollRef,
        setMessage,
        showDisabledWarning: Boolean(aiSettings && !isAIEnabled),
    }
}

type AIAssistantSidebarProps = {
    activeSessionId: string | null
    chatHistory: ChatSession[]
    isAIEnabled: boolean
    isStreaming: boolean
    onNewChat: () => void
    onSelectSession: (session: ChatSession) => void
    setMessage: Dispatch<SetStateAction<string>>
}

type AIAssistantChatWindowProps = {
    approveActionPending: boolean
    isAIEnabled: boolean
    isStreaming: boolean
    message: string
    messages: Message[]
    modelName: string
    onApprove: (approvalId: string | null) => Promise<void>
    onReject: (approvalId: string | null) => Promise<void>
    onSend: () => Promise<void>
    onStop: () => void
    scrollRef: RefObject<HTMLDivElement | null>
    setMessage: Dispatch<SetStateAction<string>>
    rejectActionPending: boolean
}

type ProposedActionListProps = {
    actions: ProposedAction[]
    approveActionPending: boolean
    onApprove: (approvalId: string | null) => Promise<void>
    onReject: (approvalId: string | null) => Promise<void>
    rejectActionPending: boolean
}

function AIAssistantHeader() {
    return (
        <div className="flex shrink-0 items-center gap-3 border-b p-4">
            <div className="flex-1">
                <h1 className="text-2xl font-semibold">AI Assistant</h1>
                <p className="text-xs text-muted-foreground">Get help with your tasks and workflows</p>
            </div>
            <Badge variant="outline">Global mode</Badge>
        </div>
    )
}

function AISettingsErrorBanner({
    message,
    onRetry,
}: {
    message: string
    onRetry: () => void
}) {
    return (
        <div className="mx-4 mt-4 flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
            <AlertCircleIcon className="size-5 text-destructive" />
            <div className="flex-1">
                <p className="text-sm font-medium">Unable to load AI settings</p>
                <p className="text-xs text-muted-foreground">{message || "Please try again."}</p>
            </div>
            <Button variant="outline" size="sm" onClick={onRetry}>
                Retry
            </Button>
        </div>
    )
}

function AINotEnabledBanner() {
    return (
        <div className="mx-4 mt-4 flex items-center gap-3 rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-3">
            <AlertCircleIcon className="size-5 text-yellow-500" />
            <div className="flex-1">
                <p className="text-sm font-medium">AI Assistant is not enabled</p>
                <p className="text-xs text-muted-foreground">Contact your admin to enable AI features and configure an API key.</p>
            </div>
        </div>
    )
}

function AIAssistantSidebar({
    activeSessionId,
    chatHistory,
    isAIEnabled,
    isStreaming,
    onNewChat,
    onSelectSession,
    setMessage,
}: AIAssistantSidebarProps) {
    return (
        <div className="hidden lg:block lg:overflow-y-auto">
            <div className="space-y-4 pr-2">
                <Card className="gap-2 p-3">
                    <div className="text-sm font-medium">Quick Actions</div>
                    <div className="text-xs text-muted-foreground">Common tasks to get started</div>
                    <div className="space-y-1">
                        {QUICK_ACTIONS.map((action) => (
                            <Button
                                key={action.label}
                                variant="outline"
                                size="sm"
                                className="w-full justify-start gap-2 bg-transparent text-sm"
                                onClick={() => setMessage(action.label)}
                                disabled={!isAIEnabled || isStreaming}
                            >
                                <action.icon className={`size-3.5 ${action.color}`} />
                                {action.label}
                            </Button>
                        ))}
                    </div>
                </Card>

                <Card className="gap-2 p-3">
                    <div className="text-sm font-medium">Suggested Actions</div>
                    <div className="text-xs text-muted-foreground">Based on your recent activity</div>
                    <div className="space-y-0">
                        {SUGGESTED_ACTIONS.map((suggestion) => (
                            <Button unstyled
                                type="button"
                                key={suggestion}
                                onClick={() => setMessage(suggestion)}
                                disabled={!isAIEnabled || isStreaming}
                                className="flex w-full items-start gap-2 rounded-md py-1 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50"
                            >
                                <SparklesIcon className="mt-0.5 size-3.5 flex-shrink-0 text-teal-500" />
                                <span className="text-sm leading-tight">{suggestion}</span>
                            </Button>
                        ))}
                    </div>
                </Card>

                <Card className="gap-2 p-3">
                    <div className="flex items-center justify-between">
                        <div className="text-sm font-medium">Chat History</div>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={onNewChat}
                            disabled={!isAIEnabled || isStreaming}
                        >
                            New Chat
                        </Button>
                    </div>
                    <div className="text-xs text-muted-foreground">Recent conversations</div>
                    <div className="mt-1 space-y-1">
                        {chatHistory.length > 0 ? (
                            <div className="space-y-1">
                                {chatHistory.map((session) => (
                                    <Button unstyled
                                        type="button"
                                        key={session.id}
                                        data-testid="chat-history-item"
                                        onClick={() => onSelectSession(session)}
                                        disabled={isStreaming}
                                        className={`w-full rounded-md border px-2 py-1.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${session.id === activeSessionId
                                            ? "border-primary/30 bg-primary/5"
                                            : "border-transparent bg-muted/40 hover:bg-muted/60"
                                            }`}
                                    >
                                        <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-medium text-foreground">
                                                {session.label}
                                            </span>
                                            <span className="text-[10px] text-muted-foreground">
                                                {formatHistoryTime(session.updatedAt)}
                                            </span>
                                        </div>
                                        <div className="truncate text-[10px] text-muted-foreground">
                                            {session.preview || "New chat"}
                                        </div>
                                    </Button>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs italic text-muted-foreground">No chat history yet</p>
                        )}
                    </div>
                </Card>
            </div>
        </div>
    )
}

function AIAssistantChatWindow({
    approveActionPending,
    isAIEnabled,
    isStreaming,
    message,
    messages,
    modelName,
    onApprove,
    onReject,
    onSend,
    onStop,
    rejectActionPending,
    scrollRef,
    setMessage,
}: AIAssistantChatWindowProps) {
    return (
        <Card className="flex h-full min-h-0 flex-col overflow-hidden">
            <CardHeader className="shrink-0 border-b py-3">
                <div className="flex items-center gap-3">
                    <div className="flex size-9 items-center justify-center rounded-full bg-primary/10">
                        <BotIcon className="size-4 text-primary" />
                    </div>
                    <div className="flex-1">
                        <CardTitle className="text-sm">AI Assistant</CardTitle>
                        <div className="flex items-center gap-1.5">
                            <div className={`size-1.5 rounded-full ${isAIEnabled ? "bg-green-500" : "bg-gray-400"}`} />
                            <CardDescription className="text-xs">
                                {isAIEnabled ? "Online" : "Not configured"}
                            </CardDescription>
                        </div>
                    </div>
                    <Badge variant="secondary" className="text-[10px]">
                        {modelName}
                    </Badge>
                </div>
            </CardHeader>

            <AIAssistantMessageList
                approveActionPending={approveActionPending}
                messages={messages}
                onApprove={onApprove}
                onReject={onReject}
                rejectActionPending={rejectActionPending}
                scrollRef={scrollRef}
            />

            <AIAssistantComposer
                isAIEnabled={isAIEnabled}
                isStreaming={isStreaming}
                message={message}
                onSend={onSend}
                onStop={onStop}
                setMessage={setMessage}
            />
        </Card>
    )
}

function AIAssistantMessageList({
    approveActionPending,
    messages,
    onApprove,
    onReject,
    rejectActionPending,
    scrollRef,
}: {
    approveActionPending: boolean
    messages: Message[]
    onApprove: (approvalId: string | null) => Promise<void>
    onReject: (approvalId: string | null) => Promise<void>
    rejectActionPending: boolean
    scrollRef: RefObject<HTMLDivElement | null>
}) {
    return (
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
            <div className="space-y-3 p-4">
                {messages.map((msg) => (
                    <AIAssistantMessageItem
                        key={msg.id}
                        approveActionPending={approveActionPending}
                        message={msg}
                        onApprove={onApprove}
                        onReject={onReject}
                        rejectActionPending={rejectActionPending}
                    />
                ))}
            </div>
        </div>
    )
}

function AIAssistantMessageItem({
    approveActionPending,
    message,
    onApprove,
    onReject,
    rejectActionPending,
}: {
    approveActionPending: boolean
    message: Message
    onApprove: (approvalId: string | null) => Promise<void>
    onReject: (approvalId: string | null) => Promise<void>
    rejectActionPending: boolean
}) {
    return (
        <div className="space-y-2">
            <div className={`flex gap-2 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                {message.role === "assistant" && (
                    <div className="flex size-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                        <BotIcon className="size-3.5 text-primary" />
                    </div>
                )}
                <div className={`max-w-[80%] space-y-0.5 ${message.role === "user" ? "items-end" : "items-start"}`}>
                    <div
                        className={`rounded-lg px-3 py-2 ${message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                            }`}
                    >
                        {message.role === "assistant" && message.status === "thinking" && !message.content ? (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <Loader2Icon className="size-3.5 animate-spin" />
                                Thinking
                            </div>
                        ) : message.role === "assistant" ? (
                            <AssistantRichText content={message.content} />
                        ) : (
                            <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
                        )}
                    </div>
                    <p className="px-1 text-[10px] text-muted-foreground">{message.timestamp}</p>
                </div>
                {message.role === "user" && (
                    <div className="flex size-7 flex-shrink-0 items-center justify-center rounded-full bg-muted">
                        <UserIcon className="size-3.5 text-muted-foreground" />
                    </div>
                )}
            </div>

            {message.proposed_actions && message.proposed_actions.length > 0 && (
                <ProposedActionList
                    actions={message.proposed_actions}
                    approveActionPending={approveActionPending}
                    onApprove={onApprove}
                    onReject={onReject}
                    rejectActionPending={rejectActionPending}
                />
            )}
        </div>
    )
}

function ProposedActionList({
    actions,
    approveActionPending,
    onApprove,
    onReject,
    rejectActionPending,
}: ProposedActionListProps) {
    return (
        <div className="ml-9 space-y-2">
            {actions.map((action) => (
                <div key={action.approval_id} className="rounded-lg border bg-muted/50 p-3">
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="text-xs font-medium uppercase text-muted-foreground">
                                Proposed Action
                            </div>
                            <div className="text-sm font-medium capitalize">
                                {action.action_type.replace(/_/g, " ")}
                            </div>
                        </div>
                        {action.status === "pending" ? (
                            <div className="flex gap-2">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                        void onReject(action.approval_id)
                                    }}
                                    disabled={rejectActionPending}
                                    aria-label={`Reject action ${action.action_type.replace(/_/g, " ")}`}
                                >
                                    <XIcon className="size-4" />
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={() => {
                                        void onApprove(action.approval_id)
                                    }}
                                    disabled={approveActionPending}
                                >
                                    <CheckIcon className="mr-1 size-4" />
                                    Approve
                                </Button>
                            </div>
                        ) : (
                            <Badge variant={action.status === "approved" ? "default" : "secondary"}>
                                {action.status}
                            </Badge>
                        )}
                    </div>
                    <pre className="mt-2 overflow-x-auto rounded bg-background/50 p-2 text-xs">
                        {JSON.stringify(action.action_data, null, 2)}
                    </pre>
                </div>
            ))}
        </div>
    )
}

function AIAssistantComposer({
    isAIEnabled,
    isStreaming,
    message,
    onSend,
    onStop,
    setMessage,
}: {
    isAIEnabled: boolean
    isStreaming: boolean
    message: string
    onSend: () => Promise<void>
    onStop: () => void
    setMessage: Dispatch<SetStateAction<string>>
}) {
    return (
        <CardContent className="shrink-0 border-t bg-background p-3">
            <div className="flex gap-2">
                <Input
                    placeholder="Ask anything"
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                            event.preventDefault()
                            void onSend()
                        }
                    }}
                    className="flex-1 text-sm"
                    disabled={!isAIEnabled || isStreaming}
                />
                {isStreaming ? (
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
                        onClick={() => {
                            void onSend()
                        }}
                        size="icon"
                        disabled={!message.trim() || !isAIEnabled}
                        aria-label="Send message"
                    >
                        <SendIcon className="size-4" aria-hidden="true" />
                    </Button>
                )}
            </div>
            <p className="mt-1.5 text-[10px] text-muted-foreground">
                Global mode · Press Enter to send
            </p>
        </CardContent>
    )
}

export default function AIAssistantPage() {
    const chat = useAIAssistantChat()

    return (
        <div className="flex h-[calc(100vh-4rem)] flex-col overflow-hidden">
            <AIAssistantHeader />
            {chat.aiSettingsError && (
                <AISettingsErrorBanner
                    message={chat.aiSettingsErrorMessage}
                    onRetry={() => {
                        void chat.refetchAISettings()
                    }}
                />
            )}
            {chat.showDisabledWarning && <AINotEnabledBanner />}

            <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[280px_1fr]">
                <AIAssistantSidebar
                    activeSessionId={chat.activeSessionId}
                    chatHistory={chat.chatHistory}
                    isAIEnabled={chat.isAIEnabled}
                    isStreaming={chat.isStreaming}
                    onNewChat={chat.handleNewChat}
                    onSelectSession={chat.handleSelectSession}
                    setMessage={chat.setMessage}
                />
                <AIAssistantChatWindow
                    approveActionPending={chat.approveActionPending}
                    isAIEnabled={chat.isAIEnabled}
                    isStreaming={chat.isStreaming}
                    message={chat.message}
                    messages={chat.messages}
                    modelName={chat.modelName}
                    onApprove={chat.handleApprove}
                    onReject={chat.handleReject}
                    onSend={chat.handleSend}
                    onStop={chat.handleStop}
                    rejectActionPending={chat.rejectActionPending}
                    scrollRef={chat.scrollRef}
                    setMessage={chat.setMessage}
                />
            </div>
        </div>
    )
}

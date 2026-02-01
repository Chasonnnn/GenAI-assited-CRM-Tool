"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SendIcon, SparklesIcon, FileTextIcon, UserIcon, CalendarIcon, ClockIcon, BotIcon, Loader2Icon, AlertCircleIcon, CheckIcon, XIcon, StopCircleIcon } from "lucide-react"
import { useState, useRef, useEffect, useMemo, useCallback } from "react"
import { useStreamChatMessage, useAISettings, useApproveAction, useRejectAction, useConversation } from "@/lib/hooks/use-ai"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"

interface SurrogateOption {
    id: string
    surrogate_number: string
    full_name: string
}

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
    entityType: "surrogate" | "global"
    entityId: string | null
    messages: Message[]
}

const CHAT_HISTORY_KEY = "ai-assistant-chat-history-v1"
const CHAT_HISTORY_USER_KEY = "ai-assistant-chat-history-user-v1"
const MAX_CHAT_HISTORY = 10
const SESSION_MESSAGE_LIMIT = 50
const SESSION_TITLE_MAX = 40
const SESSION_PREVIEW_LIMIT = 80
const GLOBAL_CONTEXT_VALUE = "__global__"

// Fetch recent surrogates for the selector
function useSurrogates() {
    return useQuery({
        queryKey: ['surrogates', 'ai-selector'],
        queryFn: async () => {
            const response = await api.get<{ items: SurrogateOption[] }>('/surrogates?per_page=20');
            return response.items;
        },
        staleTime: 60 * 1000,
    });
}

function truncateText(text: string, max: number) {
    if (text.length <= max) return text
    return `${text.slice(0, max)}...`
}

function formatHistoryTime(value: string) {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ""
    return date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
}

function normalizeMessagesForSession(messages: Message[]) {
    return messages
        .filter((msg) => msg.id !== "welcome")
        .slice(-SESSION_MESSAGE_LIMIT)
        .map((msg) => ({
            ...msg,
            status: msg.status === "thinking" || msg.status === "streaming" ? "done" : msg.status,
        }))
}

function safeParseHistory(raw: string | null): ChatSession[] {
    if (!raw) return []
    try {
        const parsed = JSON.parse(raw)
        if (!Array.isArray(parsed)) return []
        return parsed
            .filter((entry) => entry && typeof entry === "object")
            .map((entry) => ({
                id: typeof entry.id === "string" ? entry.id : `session-${Date.now()}`,
                label: typeof entry.label === "string" ? entry.label : "Chat",
                preview: typeof entry.preview === "string" ? entry.preview : "",
                updatedAt: typeof entry.updatedAt === "string" ? entry.updatedAt : new Date().toISOString(),
                entityType: entry.entityType === "surrogate" ? "surrogate" : "global",
                entityId: typeof entry.entityId === "string" ? entry.entityId : null,
                messages: Array.isArray(entry.messages) ? entry.messages : [],
            }))
            .slice(0, MAX_CHAT_HISTORY)
    } catch {
        return []
    }
}

export default function AIAssistantPage() {
    const { user } = useAuth()
    const [selectedSurrogateId, setSelectedSurrogateId] = useState<string>("")
    const [message, setMessage] = useState("")
    const [isStreaming, setIsStreaming] = useState(false)
    const [chatHistory, setChatHistory] = useState<ChatSession[]>([])
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "welcome",
            role: "assistant",
            content: "Hello! I'm your AI assistant. Ask me anything, or select a surrogate to add context.",
            timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
            status: "done",
        },
    ])
    const scrollRef = useRef<HTMLDivElement>(null)
    const streamingMessageIdRef = useRef<string | null>(null)
    const streamAbortRef = useRef<AbortController | null>(null)
    const stopRequestedRef = useRef(false)

    const surrogatesQuery = useSurrogates()
    const { data: surrogates, isLoading: surrogatesLoading, isError: surrogatesError, error: surrogatesErrorData } = surrogatesQuery
    const aiSettingsQuery = useAISettings()
    const {
        data: aiSettings,
        isError: aiSettingsError,
        error: aiSettingsErrorData,
    } = aiSettingsQuery
    const streamMessage = useStreamChatMessage()
    const approveAction = useApproveAction()
    const rejectAction = useRejectAction()
    const conversationQuery = useConversation(
        selectedSurrogateId ? "surrogate" : null,
        selectedSurrogateId || null,
        { enabled: true }
    )
    const {
        data: conversation,
        isFetching: conversationFetching,
    } = conversationQuery

    const quickActions = [
        { icon: FileTextIcon, label: "Summarize this surrogate", color: "text-blue-500" },
        { icon: UserIcon, label: "Draft a follow-up email", color: "text-green-500" },
        { icon: CalendarIcon, label: "What are the next steps?", color: "text-purple-500" },
        { icon: ClockIcon, label: "Create a task list", color: "text-orange-500" },
    ]

    const suggestedActions = [
        "What's the current status of this surrogate?",
        "Are there any pending tasks?",
        "Summarize recent notes",
        "Draft an email to the intended parents",
    ]
    const surrogatesErrorMessage = surrogatesErrorData instanceof Error ? surrogatesErrorData.message : ""
    const aiSettingsErrorMessage = aiSettingsErrorData instanceof Error ? aiSettingsErrorData.message : ""
    const conversationMessages = useMemo(() => {
        if (!conversation?.messages?.length) {
            return []
        }
        return conversation.messages.map((msg) => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: msg.created_at
                ? new Date(msg.created_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
                : new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
            ...(msg.proposed_actions ? { proposed_actions: msg.proposed_actions } : {}),
            status: "done" as const,
        }))
    }, [conversation])

    const buildWelcomeMessage = useCallback(() => ({
        id: "welcome",
        role: "assistant" as const,
        content: "Hello! I'm your AI assistant. Ask me anything, or select a surrogate to add context.",
        timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
        status: "done" as const,
    }), [])

    const persistHistory = useCallback((next: ChatSession[]) => {
        if (typeof window === "undefined") return
        sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(next))
    }, [])

    const updateHistory = useCallback(
        (updater: (prev: ChatSession[]) => ChatSession[]) => {
            setChatHistory((prev) => {
                const next = updater(prev)
                persistHistory(next)
                return next
            })
        },
        [persistHistory]
    )

    const buildSessionLabel = useCallback((entityType: "surrogate" | "global", entityId: string | null) => {
        if (entityType === "surrogate" && entityId) {
            const surrogate = surrogates?.find((item) => item.id === entityId)
            if (surrogate) {
                return truncateText(
                    `#${surrogate.surrogate_number} \u2022 ${surrogate.full_name}`,
                    SESSION_TITLE_MAX
                )
            }
            return "Surrogate Chat"
        }
        return "Global Chat"
    }, [surrogates])

    const derivePreview = useCallback((sessionMessages: Message[]) => {
        const lastUserMessage = [...sessionMessages].reverse().find((msg) => msg.role === "user" && msg.content)
        if (!lastUserMessage) return ""
        return truncateText(lastUserMessage.content, SESSION_PREVIEW_LIMIT)
    }, [])

    const upsertSession = useCallback(
        (session: ChatSession) => {
            updateHistory((prev) => {
                const filtered = prev.filter((item) => item.id !== session.id)
                const next = [session, ...filtered].slice(0, MAX_CHAT_HISTORY)
                return next
            })
        },
        [updateHistory]
    )

    const updateSessionMessages = useCallback(
        (sessionId: string, sessionMessages: Message[], context: { entityType: "surrogate" | "global"; entityId: string | null }) => {
            const normalized = normalizeMessagesForSession(sessionMessages)
            const session: ChatSession = {
                id: sessionId,
                label: buildSessionLabel(context.entityType, context.entityId),
                preview: derivePreview(sessionMessages),
                updatedAt: new Date().toISOString(),
                entityType: context.entityType,
                entityId: context.entityId,
                messages: normalized,
            }
            upsertSession(session)
        },
        [buildSessionLabel, derivePreview, upsertSession]
    )

    const clearChatHistory = useCallback(() => {
        setChatHistory([])
        setActiveSessionId(null)
        setMessages([buildWelcomeMessage()])
        if (typeof window !== "undefined") {
            sessionStorage.removeItem(CHAT_HISTORY_KEY)
            sessionStorage.removeItem(CHAT_HISTORY_USER_KEY)
        }
    }, [buildWelcomeMessage])

    const historyLoadedRef = useRef(false)

    useEffect(() => {
        if (typeof window === "undefined") return
        if (!user?.user_id) {
            historyLoadedRef.current = false
            clearChatHistory()
            return
        }
        const storedUserId = sessionStorage.getItem(CHAT_HISTORY_USER_KEY)
        if (storedUserId && storedUserId !== user.user_id) {
            clearChatHistory()
            historyLoadedRef.current = false
        }
        if (!historyLoadedRef.current) {
            const storedHistory = safeParseHistory(sessionStorage.getItem(CHAT_HISTORY_KEY))
            setChatHistory(storedHistory)
            if (storedHistory.length > 0) {
                const mostRecent = storedHistory[0]
                setActiveSessionId(mostRecent.id)
                if (mostRecent.entityType === "surrogate" && mostRecent.entityId) {
                    setSelectedSurrogateId(mostRecent.entityId)
                } else {
                    setSelectedSurrogateId("")
                }
            }
            historyLoadedRef.current = true
        }
        sessionStorage.setItem(CHAT_HISTORY_USER_KEY, user.user_id)
    }, [user?.user_id, clearChatHistory])

    const currentSession = useMemo(
        () => chatHistory.find((session) => session.id === activeSessionId) || null,
        [chatHistory, activeSessionId]
    )

    useEffect(() => {
        if (isStreaming) return
        if (currentSession) {
            const sessionMessages = currentSession.messages.length
                ? currentSession.messages
                : [buildWelcomeMessage()]
            setMessages(sessionMessages)
            return
        }
        if (!conversationFetching && conversationMessages.length > 0) {
            setMessages(conversationMessages)
            return
        }
        setMessages([buildWelcomeMessage()])
    }, [
        currentSession,
        conversationMessages,
        conversationFetching,
        isStreaming,
        buildWelcomeMessage,
    ])

    // Scroll to bottom when messages change
    useEffect(() => {
        const container = scrollRef.current
        if (!container) return
        container.scrollTop = container.scrollHeight
    }, [messages])

    useEffect(() => {
        return () => {
            streamAbortRef.current?.abort()
        }
    }, [])

    useEffect(() => {
        if (!isStreaming) return
        streamAbortRef.current?.abort()
        setIsStreaming(false)
        streamingMessageIdRef.current = null
        stopRequestedRef.current = false
    }, [selectedSurrogateId, isStreaming])

    const ensureSessionId = useCallback(
        (context: { entityType: "surrogate" | "global"; entityId: string | null }) => {
            const active = activeSessionId
                ? chatHistory.find((session) => session.id === activeSessionId)
                : null
            if (active && active.entityType === context.entityType && active.entityId === context.entityId) {
                return active.id
            }
            const existing = chatHistory.find(
                (session) => session.entityType === context.entityType && session.entityId === context.entityId
            )
            if (existing) {
                setActiveSessionId(existing.id)
                return existing.id
            }

            const sessionId = `session-${Date.now()}`
            upsertSession({
                id: sessionId,
                label: buildSessionLabel(context.entityType, context.entityId),
                preview: "",
                updatedAt: new Date().toISOString(),
                entityType: context.entityType,
                entityId: context.entityId,
                messages: [],
            })
            setActiveSessionId(sessionId)
            return sessionId
        },
        [activeSessionId, chatHistory, buildSessionLabel, upsertSession]
    )

    const updateMessageById = useCallback((id: string, updater: (msg: Message) => Message) => {
        setMessages((prev) => prev.map((msg) => (msg.id === id ? updater(msg) : msg)))
    }, [])

    const updateMessageAndSession = useCallback(
        (
            id: string,
            updater: (msg: Message) => Message,
            sessionId: string,
            context: { entityType: "surrogate" | "global"; entityId: string | null }
        ) => {
            setMessages((prev) => {
                const next = prev.map((msg) => (msg.id === id ? updater(msg) : msg))
                updateSessionMessages(sessionId, next, context)
                return next
            })
        },
        [updateSessionMessages]
    )

    const handleSelectSession = useCallback(
        (session: ChatSession) => {
            setActiveSessionId(session.id)
            if (session.entityType === "surrogate" && session.entityId) {
                setSelectedSurrogateId(session.entityId)
            } else {
                setSelectedSurrogateId("")
            }
            const sessionMessages = session.messages.length ? session.messages : [buildWelcomeMessage()]
            setMessages(sessionMessages)
        },
        [buildWelcomeMessage]
    )

    const handleNewChat = useCallback(() => {
        const context = selectedSurrogateId
            ? { entityType: "surrogate" as const, entityId: selectedSurrogateId }
            : { entityType: "global" as const, entityId: null }
        const sessionId = `session-${Date.now()}`
        upsertSession({
            id: sessionId,
            label: buildSessionLabel(context.entityType, context.entityId),
            preview: "",
            updatedAt: new Date().toISOString(),
            entityType: context.entityType,
            entityId: context.entityId,
            messages: [],
        })
        setActiveSessionId(sessionId)
        setMessages([buildWelcomeMessage()])
    }, [selectedSurrogateId, buildSessionLabel, upsertSession, buildWelcomeMessage])

    const setAssistantError = useCallback(
        (
            assistantId: string,
            errorText: string,
            sessionId?: string,
            context?: { entityType: "surrogate" | "global"; entityId: string | null }
        ) => {
            if (sessionId && context) {
                updateMessageAndSession(
                    assistantId,
                    (msg) => ({
                        ...msg,
                        content: errorText,
                        status: "error",
                    }),
                    sessionId,
                    context
                )
                return
            }
            updateMessageById(assistantId, (msg) => ({
                ...msg,
                content: errorText,
                status: "error",
            }))
        },
        [updateMessageAndSession, updateMessageById]
    )

    const handleSend = async () => {
        const trimmedMessage = message.trim()
        if (!trimmedMessage || !isAIEnabled || isStreaming) return

        const context = selectedSurrogateId
            ? { entityType: "surrogate" as const, entityId: selectedSurrogateId }
            : { entityType: "global" as const, entityId: null }
        const sessionId = ensureSessionId(context)

        const timestamp = new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
        const userMessage: Message = {
            id: `user-${Date.now()}`,
            role: "user",
            content: trimmedMessage,
            timestamp,
            status: "done",
        }
        const assistantId = `assistant-${Date.now()}`
        const assistantMessage: Message = {
            id: assistantId,
            role: "assistant",
            content: "",
            timestamp,
            status: "thinking",
        }

        setMessages((prev) => {
            const next = [...prev, userMessage, assistantMessage]
            updateSessionMessages(sessionId, next, context)
            return next
        })
        setMessage("")

        streamAbortRef.current?.abort()
        stopRequestedRef.current = false
        const controller = new AbortController()
        streamAbortRef.current = controller
        streamingMessageIdRef.current = assistantId
        setIsStreaming(true)

        try {
            await streamMessage(
                context.entityType === "surrogate" && context.entityId
                    ? {
                        entity_type: "surrogate",
                        entity_id: context.entityId,
                        message: trimmedMessage,
                    }
                    : {
                        message: trimmedMessage,
                    },
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
                            context
                        )
                        return
                    }

                    if (event.type === 'error') {
                        setAssistantError(
                            assistantId,
                            `Sorry, I encountered an error: ${event.data.message || 'Unknown error'}. Please try again.`,
                            sessionId,
                            context
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
                        sessionId,
                        context
                    )
                }
                stopRequestedRef.current = false
                return
            }
            setAssistantError(
                assistantId,
                `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
                sessionId,
                context
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

    const syncSessionFromMessages = useCallback(
        (nextMessages: Message[]) => {
            if (!activeSessionId) return
            const context = selectedSurrogateId
                ? { entityType: "surrogate" as const, entityId: selectedSurrogateId }
                : { entityType: "global" as const, entityId: null }
            updateSessionMessages(activeSessionId, nextMessages, context)
        },
        [activeSessionId, selectedSurrogateId, updateSessionMessages]
    )

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

    const handleSurrogateChange = useCallback((value?: string) => {
        const nextId = value ?? ""
        setSelectedSurrogateId(nextId)
        if (!nextId) {
            const globalSession = chatHistory.find((session) => session.entityType === "global")
            if (globalSession) {
                setActiveSessionId(globalSession.id)
                setMessages(globalSession.messages.length ? globalSession.messages : [buildWelcomeMessage()])
                return
            }
            setActiveSessionId(null)
            setMessages([buildWelcomeMessage()])
            return
        }
        const session = chatHistory.find(
            (item) => item.entityType === "surrogate" && item.entityId === nextId
        )
        if (session) {
            setActiveSessionId(session.id)
            setMessages(session.messages.length ? session.messages : [buildWelcomeMessage()])
            return
        }
        setActiveSessionId(null)
        setMessages([buildWelcomeMessage()])
    }, [chatHistory, buildWelcomeMessage])

    const selectedSurrogate = surrogates?.find(surrogate => surrogate.id === selectedSurrogateId)
    const isAIEnabled = aiSettings?.is_enabled
    const modelName = aiSettings?.model || aiSettings?.provider?.toUpperCase() || 'AI'

    return (
        <div className="flex h-[calc(100vh-4rem)] flex-col overflow-hidden">
            {/* Header */}
            <div className="flex shrink-0 items-center gap-3 border-b p-4">
                <div className="flex-1">
                    <h1 className="text-2xl font-semibold">AI Assistant</h1>
                    <p className="text-xs text-muted-foreground">Get help with your surrogates, tasks, and workflows</p>
                </div>
                {/* Surrogate Selector */}
                <Select
                    value={selectedSurrogateId || GLOBAL_CONTEXT_VALUE}
                    onValueChange={(v) => handleSurrogateChange(v === GLOBAL_CONTEXT_VALUE ? "" : v)}
                >
                    <SelectTrigger className="w-64">
                        <SelectValue placeholder={surrogatesLoading ? "Loading surrogates..." : "Global mode"} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value={GLOBAL_CONTEXT_VALUE}>Global mode</SelectItem>
                        {surrogates?.map(surrogate => (
                            <SelectItem key={surrogate.id} value={surrogate.id}>
                                #{surrogate.surrogate_number} - {surrogate.full_name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {(surrogatesError || aiSettingsError) && (
                <div className="mx-4 mt-4 flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                    <AlertCircleIcon className="h-5 w-5 text-destructive" />
                    <div className="flex-1">
                        <p className="text-sm font-medium">Unable to load AI settings or surrogates</p>
                        <p className="text-xs text-muted-foreground">
                            {surrogatesErrorMessage || aiSettingsErrorMessage || "Please try again."}
                        </p>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                            if (surrogatesError) {
                                void surrogatesQuery.refetch()
                            }
                            if (aiSettingsError) {
                                void aiSettingsQuery.refetch()
                            }
                        }}
                    >
                        Retry
                    </Button>
                </div>
            )}

            {/* AI Not Enabled Warning */}
            {aiSettings && !isAIEnabled && (
                <div className="mx-4 mt-4 flex items-center gap-3 rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-3">
                    <AlertCircleIcon className="h-5 w-5 text-yellow-500" />
                    <div className="flex-1">
                        <p className="text-sm font-medium">AI Assistant is not enabled</p>
                        <p className="text-xs text-muted-foreground">Contact your admin to enable AI features and configure an API key.</p>
                    </div>
                </div>
            )}

            {/* Main Content */}
            <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[280px_1fr]">
                {/* Left Sidebar - scrollable */}
                <div className="hidden lg:block lg:overflow-y-auto">
                    <div className="space-y-4 pr-2">
                        {/* Quick Actions */}
                        <Card className="gap-2 py-3 px-3">
                            <div className="text-sm font-medium">Quick Actions</div>
                            <div className="text-xs text-muted-foreground">Common tasks to get started</div>
                            <div className="space-y-1">
                                {quickActions.map((action, index) => (
                                    <Button
                                        key={index}
                                        variant="outline"
                                        size="sm"
                                        className="w-full justify-start gap-2 bg-transparent text-sm"
                                        onClick={() => setMessage(action.label)}
                                        disabled={!selectedSurrogateId || !isAIEnabled || isStreaming}
                                    >
                                        <action.icon className={`h-3.5 w-3.5 ${action.color}`} />
                                        {action.label}
                                    </Button>
                                ))}
                            </div>
                        </Card>

                        {/* Suggested Actions */}
                        <Card className="gap-2 py-3 px-3">
                            <div className="text-sm font-medium">Suggested Actions</div>
                            <div className="text-xs text-muted-foreground">Based on your recent activity</div>
                            <div className="space-y-0">
                                {suggestedActions.map((suggestion, index) => (
                                    <button
                                        key={index}
                                        onClick={() => setMessage(suggestion)}
                                        disabled={!selectedSurrogateId || !isAIEnabled || isStreaming}
                                        className="flex w-full items-start gap-2 rounded-md py-1 text-left hover:bg-muted/50 transition-colors disabled:opacity-50"
                                    >
                                        <SparklesIcon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-teal-500" />
                                        <span className="text-sm leading-tight">{suggestion}</span>
                                    </button>
                                ))}
                            </div>
                        </Card>

                        {/* Selected Surrogate Info */}
                        {selectedSurrogate && (
                            <Card className="gap-2 py-3 px-3">
                                <div className="text-sm font-medium">Current Surrogate</div>
                                <div className="text-xs text-muted-foreground">Chatting about:</div>
                                <div className="rounded-md border p-2">
                                    <div className="font-medium text-sm">#{selectedSurrogate.surrogate_number}</div>
                                    <div className="text-xs text-muted-foreground">{selectedSurrogate.full_name}</div>
                                </div>
                            </Card>
                        )}

                        {/* Chat History */}
                        <Card className="gap-2 py-3 px-3">
                            <div className="flex items-center justify-between">
                                <div className="text-sm font-medium">Chat History</div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2 text-xs"
                                    onClick={handleNewChat}
                                    disabled={!isAIEnabled || isStreaming}
                                >
                                    New Chat
                                </Button>
                            </div>
                            <div className="text-xs text-muted-foreground">Recent conversations</div>
                            <div className="space-y-1 mt-1">
                                {chatHistory.length > 0 ? (
                                    <div className="space-y-1">
                                        {chatHistory.map((session) => (
                                            <button
                                                key={session.id}
                                                data-testid="chat-history-item"
                                                onClick={() => handleSelectSession(session)}
                                                disabled={isStreaming}
                                                className={`w-full rounded-md border px-2 py-1.5 text-left transition-colors ${session.id === activeSessionId
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
                                                <div className="text-[10px] text-muted-foreground truncate">
                                                    {session.preview || "New chat"}
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-xs text-muted-foreground italic">
                                        No chat history yet
                                    </p>
                                )}
                            </div>
                        </Card>
                    </div>
                </div>

                {/* Right Chat Window */}
                <Card className="flex h-full min-h-0 flex-col overflow-hidden">
                    <CardHeader className="shrink-0 border-b py-3">
                        <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10">
                                <BotIcon className="h-4 w-4 text-primary" />
                            </div>
                            <div className="flex-1">
                                <CardTitle className="text-sm">AI Assistant</CardTitle>
                                <div className="flex items-center gap-1.5">
                                    <div className={`h-1.5 w-1.5 rounded-full ${isAIEnabled ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                                    <CardDescription className="text-xs">
                                        {isAIEnabled ? 'Online' : 'Not configured'}
                                    </CardDescription>
                                </div>
                            </div>
                            <Badge variant="secondary" className="text-[10px]">
                                {modelName}
                            </Badge>
                        </div>
                    </CardHeader>

                    {/* Chat Messages - scrollable */}
                    <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto">
                        <div className="space-y-3 p-4">
                            {messages.map((msg) => (
                                <div key={msg.id} className="space-y-2">
                                    <div className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                                        {msg.role === "assistant" && (
                                            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                                                <BotIcon className="h-3.5 w-3.5 text-primary" />
                                            </div>
                                        )}
                                        <div className={`max-w-[80%] space-y-0.5 ${msg.role === "user" ? "items-end" : "items-start"}`}>
                                            <div
                                                className={`rounded-lg px-3 py-2 ${msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                                                    }`}
                                            >
                                                {msg.role === "assistant" && msg.status === "thinking" && !msg.content ? (
                                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                        <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                                                        Thinking...
                                                    </div>
                                                ) : (
                                                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                                                )}
                                            </div>
                                            <p className="px-1 text-[10px] text-muted-foreground">{msg.timestamp}</p>
                                        </div>
                                        {msg.role === "user" && (
                                            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-muted">
                                                <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                                            </div>
                                        )}
                                    </div>

                                    {/* Proposed Actions */}
                                    {msg.proposed_actions && msg.proposed_actions.length > 0 && (
                                        <div className="ml-9 space-y-2">
                                            {msg.proposed_actions.map((action) => (
                                                <div
                                                    key={action.approval_id}
                                                    className="rounded-lg border bg-muted/50 p-3"
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <div>
                                                            <div className="text-xs font-medium text-muted-foreground uppercase">
                                                                Proposed Action
                                                            </div>
                                                            <div className="text-sm font-medium capitalize">
                                                                {action.action_type.replace(/_/g, ' ')}
                                                            </div>
                                                        </div>
                                                        {action.status === 'pending' ? (
                                                            <div className="flex gap-2">
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    onClick={() => handleReject(action.approval_id)}
                                                                    disabled={rejectAction.isPending}
                                                                >
                                                                    <XIcon className="h-4 w-4" />
                                                                </Button>
                                                                <Button
                                                                    size="sm"
                                                                    onClick={() => handleApprove(action.approval_id)}
                                                                    disabled={approveAction.isPending}
                                                                >
                                                                    <CheckIcon className="h-4 w-4 mr-1" />
                                                                    Approve
                                                                </Button>
                                                            </div>
                                                        ) : (
                                                            <Badge variant={action.status === 'approved' ? 'default' : 'secondary'}>
                                                                {action.status}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    <pre className="mt-2 text-xs bg-background/50 p-2 rounded overflow-x-auto">
                                                        {JSON.stringify(action.action_data, null, 2)}
                                                    </pre>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}

                        </div>
                    </div>

                    {/* Input Area */}
                    <CardContent className="shrink-0 border-t bg-background p-3">
                        <div className="flex gap-2">
                            <Input
                                placeholder="Ask anything..."
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault()
                                        handleSend()
                                    }
                                }}
                                className="flex-1 text-sm"
                                disabled={!isAIEnabled || isStreaming}
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
                                    size="icon"
                                    disabled={!message.trim() || !isAIEnabled}
                                    aria-label="Send message"
                                >
                                    <SendIcon className="h-4 w-4" />
                                </Button>
                            )}
                        </div>
                        <p className="mt-1.5 text-[10px] text-muted-foreground">
                            {selectedSurrogateId
                                ? "Press Enter to send"
                                : "Global mode \u2014 select a surrogate to add context"}
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

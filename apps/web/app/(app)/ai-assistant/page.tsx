"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SendIcon, SparklesIcon, FileTextIcon, UserIcon, CalendarIcon, ClockIcon, BotIcon, Loader2Icon, AlertCircleIcon, CheckIcon, XIcon } from "lucide-react"
import { useState, useRef, useEffect } from "react"
import { useSendMessage, useAISettings, useApproveAction, useRejectAction } from "@/lib/hooks/use-ai"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

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
}

interface ProposedAction {
    approval_id: string | null
    action_type: string
    action_data: Record<string, unknown>
    status: string
}


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

export default function AIAssistantPage() {
    const [selectedSurrogateId, setSelectedSurrogateId] = useState<string>("")
    const [message, setMessage] = useState("")
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "welcome",
            role: "assistant",
            content: "Hello! I'm your AI assistant. Select a surrogate above to start chatting about it, or use the quick actions to get started.",
            timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
        },
    ])
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const surrogatesQuery = useSurrogates()
    const { data: surrogates, isLoading: surrogatesLoading, isError: surrogatesError, error: surrogatesErrorData } = surrogatesQuery
    const aiSettingsQuery = useAISettings()
    const {
        data: aiSettings,
        isError: aiSettingsError,
        error: aiSettingsErrorData,
    } = aiSettingsQuery
    const sendMessage = useSendMessage()
    const approveAction = useApproveAction()
    const rejectAction = useRejectAction()

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

    // Scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleSend = async () => {
        if (!message.trim() || !selectedSurrogateId) return

        const userMessage: Message = {
            id: `user-${Date.now()}`,
            role: "user",
            content: message,
            timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
        }

        setMessages(prev => [...prev, userMessage])
        setMessage("")

        try {
            const response = await sendMessage.mutateAsync({
                entity_type: 'surrogate',
                entity_id: selectedSurrogateId,
                message: message,
            })

            const aiMessage: Message = {
                id: `ai-${Date.now()}`,
                role: "assistant",
                content: response.content,
                timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
                proposed_actions: response.proposed_actions,
            }

            setMessages(prev => [...prev, aiMessage])
        } catch (error) {
            const errorMessage: Message = {
                id: `error-${Date.now()}`,
                role: "assistant",
                content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
                timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
            }
            setMessages(prev => [...prev, errorMessage])
        }
    }

    const handleApprove = async (approvalId: string | null) => {
        if (!approvalId) return
        try {
            await approveAction.mutateAsync(approvalId)
            // Update the action status in messages
            setMessages(prev => prev.map(msg => {
                if (!msg.proposed_actions) return msg
                return {
                    ...msg,
                    proposed_actions: msg.proposed_actions.map(action =>
                        action.approval_id === approvalId ? { ...action, status: 'approved' } : action
                    ),
                }
            }))
        } catch (error) {
            console.error('Failed to approve action:', error)
        }
    }

    const handleReject = async (approvalId: string | null) => {
        if (!approvalId) return
        try {
            await rejectAction.mutateAsync(approvalId)
            setMessages(prev => prev.map(msg => {
                if (!msg.proposed_actions) return msg
                return {
                    ...msg,
                    proposed_actions: msg.proposed_actions.map(action =>
                        action.approval_id === approvalId ? { ...action, status: 'rejected' } : action
                    ),
                }
            }))
        } catch (error) {
            console.error('Failed to reject action:', error)
        }
    }

    const selectedSurrogate = surrogates?.find(surrogate => surrogate.id === selectedSurrogateId)
    const isAIEnabled = aiSettings?.is_enabled
    const modelName = aiSettings?.model || aiSettings?.provider?.toUpperCase() || 'AI'

    return (
        <div className="flex h-[calc(100vh-4rem)] flex-col">
            {/* Header */}
            <div className="flex shrink-0 items-center gap-3 border-b p-4">
                <div className="flex-1">
                    <h1 className="text-2xl font-semibold">AI Assistant</h1>
                    <p className="text-xs text-muted-foreground">Get help with your surrogates, tasks, and workflows</p>
                </div>
                {/* Surrogate Selector */}
                <Select value={selectedSurrogateId} onValueChange={(v) => setSelectedSurrogateId(v ?? "")}>
                    <SelectTrigger className="w-64">
                        <SelectValue placeholder={surrogatesLoading ? "Loading surrogates..." : "Select a surrogate"} />
                    </SelectTrigger>
                    <SelectContent>
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
            <div className="grid min-h-0 flex-1 gap-4 p-4 lg:grid-cols-[280px_1fr]">
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
                                        disabled={!selectedSurrogateId}
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
                                        disabled={!selectedSurrogateId}
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
                            <div className="text-sm font-medium">Chat History</div>
                            <div className="text-xs text-muted-foreground">Recent conversations</div>
                            <div className="space-y-1 mt-1">
                                {messages.length > 1 ? (
                                    <div className="space-y-1">
                                        {messages
                                            .filter(m => m.role === 'user')
                                            .slice(-5)
                                            .reverse()
                                            .map((msg, idx) => (
                                                <div
                                                    key={msg.id || idx}
                                                    className="text-xs p-2 rounded-md bg-muted/50 truncate"
                                                    title={msg.content}
                                                >
                                                    {msg.content.slice(0, 40)}{msg.content.length > 40 ? '...' : ''}
                                                </div>
                                            ))
                                        }
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
                <Card className="flex min-h-0 flex-col">
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
                    <ScrollArea className="flex-1 min-h-0">
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
                                                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
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

                            {/* Loading indicator */}
                            {sendMessage.isPending && (
                                <div className="flex gap-2 justify-start">
                                    <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/10">
                                        <BotIcon className="h-3.5 w-3.5 text-primary" />
                                    </div>
                                    <div className="rounded-lg px-3 py-2 bg-muted">
                                        <Loader2Icon className="h-4 w-4 animate-spin" />
                                    </div>
                                </div>
                            )}

                            {/* Scroll anchor */}
                            <div ref={messagesEndRef} />
                        </div>
                    </ScrollArea>

                    {/* Input Area */}
                    <CardContent className="shrink-0 border-t p-3">
                        <div className="flex gap-2">
                            <Input
                                placeholder={selectedSurrogateId ? "Type your message..." : "Select a surrogate to start chatting"}
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault()
                                        handleSend()
                                    }
                                }}
                                className="flex-1 text-sm"
                                disabled={!selectedSurrogateId || !isAIEnabled || sendMessage.isPending}
                            />
                            <Button
                                onClick={handleSend}
                                size="icon"
                                disabled={!message.trim() || !selectedSurrogateId || !isAIEnabled || sendMessage.isPending}
                            >
                                {sendMessage.isPending ? (
                                    <Loader2Icon className="h-4 w-4 animate-spin" />
                                ) : (
                                    <SendIcon className="h-4 w-4" />
                                )}
                            </Button>
                        </div>
                        <p className="mt-1.5 text-[10px] text-muted-foreground">
                            {!selectedSurrogateId ? "Select a surrogate above to start" : "Press Enter to send"}
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

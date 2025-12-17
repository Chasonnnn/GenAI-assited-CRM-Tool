"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { SendIcon, SparklesIcon, FileTextIcon, UserIcon, CalendarIcon, ClockIcon, BotIcon } from "lucide-react"
import { useState } from "react"

export default function AIAssistantPage() {
    const [message, setMessage] = useState("")
    const [messages, setMessages] = useState([
        {
            id: 1,
            role: "assistant",
            content: "Hello! I'm your AI assistant. How can I help you with your surrogacy cases today?",
            timestamp: "10:30 AM",
        },
    ])

    const quickActions = [
        { icon: FileTextIcon, label: "Summarize Case", color: "text-blue-500" },
        { icon: UserIcon, label: "Draft Email", color: "text-green-500" },
        { icon: CalendarIcon, label: "Schedule Meeting", color: "text-purple-500" },
        { icon: ClockIcon, label: "Generate Report", color: "text-orange-500" },
    ]

    const suggestedActions = [
        "Review pending cases from this week",
        "Draft welcome email for new intended parents",
        "Summarize recent activity for Case #12345",
        "Create task list for upcoming screenings",
    ]

    const pastConversations = [
        { id: 1, title: "Case #12345 Summary", date: "Today, 9:15 AM", preview: "Generated case summary for..." },
        { id: 2, title: "Email Draft for IPs", date: "Yesterday, 4:30 PM", preview: "Drafted welcome email..." },
        { id: 3, title: "Workflow Automation", date: "Dec 15, 2:20 PM", preview: "Discussed task automation..." },
        { id: 4, title: "Report Generation", date: "Dec 14, 11:45 AM", preview: "Created monthly report..." },
        { id: 5, title: "Case Analysis", date: "Dec 13, 3:10 PM", preview: "Analyzed case timeline..." },
    ]

    const handleSend = () => {
        if (!message.trim()) return

        const newMessage = {
            id: messages.length + 1,
            role: "user" as const,
            content: message,
            timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
        }

        setMessages([...messages, newMessage])
        setMessage("")

        // Simulate AI response
        setTimeout(() => {
            const aiResponse = {
                id: messages.length + 2,
                role: "assistant" as const,
                content: "I understand. Let me help you with that. I'm processing your request...",
                timestamp: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
            }
            setMessages((prev) => [...prev, aiResponse])
        }, 1000)
    }

    return (
        <div className="flex h-[calc(100vh-4rem)] flex-col">
            {/* Header */}
            <div className="flex shrink-0 items-center gap-3 border-b p-4">
                <SidebarTrigger />
                <div>
                    <h1 className="text-xl font-bold">AI Assistant</h1>
                    <p className="text-xs text-muted-foreground">Get help with your cases, tasks, and workflows</p>
                </div>
            </div>

            {/* Main Content - fills remaining height */}
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
                                        className="flex w-full items-start gap-2 rounded-md py-1 text-left hover:bg-muted/50 transition-colors"
                                    >
                                        <SparklesIcon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-teal-500" />
                                        <span className="text-sm leading-tight">{suggestion}</span>
                                    </button>
                                ))}
                            </div>
                        </Card>

                        {/* Past Conversations */}
                        <Card className="gap-2 py-3 px-3">
                            <div className="text-sm font-medium">Past Conversations</div>
                            <div className="text-xs text-muted-foreground">Your recent chats</div>
                            <div className="space-y-1.5">
                                {pastConversations.map((conv) => (
                                    <button
                                        key={conv.id}
                                        className="flex w-full flex-col items-start gap-0.5 rounded-md border p-2 text-left hover:bg-muted/50 transition-colors"
                                    >
                                        <div className="font-medium text-sm">{conv.title}</div>
                                        <div className="text-xs text-muted-foreground">{conv.date}</div>
                                        <div className="text-xs text-muted-foreground line-clamp-1">{conv.preview}</div>
                                    </button>
                                ))}
                            </div>
                        </Card>
                    </div>
                </div>

                {/* Right Chat Window - fixed height, input at bottom */}
                <Card className="flex min-h-0 flex-col">
                    <CardHeader className="shrink-0 border-b py-3">
                        <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10">
                                <BotIcon className="h-4 w-4 text-primary" />
                            </div>
                            <div className="flex-1">
                                <CardTitle className="text-sm">AI Assistant</CardTitle>
                                <div className="flex items-center gap-1.5">
                                    <div className="h-1.5 w-1.5 rounded-full bg-green-500"></div>
                                    <CardDescription className="text-xs">Online</CardDescription>
                                </div>
                            </div>
                            <Badge variant="secondary" className="text-[10px]">
                                GPT-4
                            </Badge>
                        </div>
                    </CardHeader>

                    {/* Chat Messages - scrollable */}
                    <ScrollArea className="flex-1 min-h-0">
                        <div className="space-y-3 p-4">
                            {messages.map((msg) => (
                                <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
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
                                            <p className="text-sm leading-relaxed">{msg.content}</p>
                                        </div>
                                        <p className="px-1 text-[10px] text-muted-foreground">{msg.timestamp}</p>
                                    </div>
                                    {msg.role === "user" && (
                                        <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-muted">
                                            <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </ScrollArea>

                    {/* Input Area - fixed at bottom */}
                    <CardContent className="shrink-0 border-t p-3">
                        <div className="flex gap-2">
                            <Input
                                placeholder="Type your message..."
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault()
                                        handleSend()
                                    }
                                }}
                                className="flex-1 text-sm"
                            />
                            <Button onClick={handleSend} size="icon" disabled={!message.trim()}>
                                <SendIcon className="h-4 w-4" />
                            </Button>
                        </div>
                        <p className="mt-1.5 text-[10px] text-muted-foreground">Press Enter to send</p>
                    </CardContent>
                </Card>
            </div>
        </div >
    )
}

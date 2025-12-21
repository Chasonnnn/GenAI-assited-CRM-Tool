"use client"

import * as React from "react"
import { useAIContext } from "@/lib/context/ai-context"
import { AIChatPanel } from "./AIChatPanel"
import { cn } from "@/lib/utils"
import { XIcon } from "lucide-react"
import { Button } from "@/components/ui/button"

export function AIChatDrawer() {
    const { isOpen, closePanel, entityType, entityId, entityName, canUseAI } = useAIContext()

    // Don't render if AI is not available or panel is closed
    if (!canUseAI || !isOpen) {
        return null
    }

    // Don't render chat if no context is set
    const hasContext = entityType && entityId && entityName

    return (
        <>
            {/* Backdrop for mobile */}
            <div
                className={cn(
                    "fixed inset-0 z-40 bg-background/80 backdrop-blur-sm md:hidden",
                    isOpen ? "block" : "hidden"
                )}
                onClick={closePanel}
            />

            {/* Drawer */}
            <div
                className={cn(
                    "fixed inset-y-0 right-0 z-50 w-full max-w-md border-l bg-background shadow-xl transition-transform duration-300 ease-in-out",
                    "md:w-[400px]",
                    isOpen ? "translate-x-0" : "translate-x-full"
                )}
            >
                {hasContext && entityType !== "dashboard" ? (
                    <AIChatPanel
                        entityType={entityType}
                        entityId={entityId}
                        entityName={entityName}
                        onClose={closePanel}
                    />
                ) : (
                    <NoContextView onClose={closePanel} />
                )}
            </div>
        </>
    )
}

// View when no entity context is set
function NoContextView({ onClose }: { onClose: () => void }) {
    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
                <span className="font-semibold">AI Assistant</span>
                <Button variant="ghost" size="icon" onClick={onClose}>
                    <XIcon className="h-4 w-4" />
                </Button>
            </div>

            {/* Content */}
            <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
                <div className="mb-4 rounded-full bg-muted p-4">
                    <svg
                        className="h-8 w-8 text-muted-foreground"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={1.5}
                            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                        />
                    </svg>
                </div>
                <h3 className="mb-2 font-semibold">No Case Selected</h3>
                <p className="text-sm text-muted-foreground">
                    Open a case or intended parent to start chatting with the AI assistant.
                </p>
                <p className="mt-4 text-xs text-muted-foreground">
                    Tip: Use <kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs">⌘⇧A</kbd> to
                    toggle this panel
                </p>
            </div>
        </div>
    )
}

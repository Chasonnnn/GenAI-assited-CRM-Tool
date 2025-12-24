"use client"

import * as React from "react"
import { useAIContext } from "@/lib/context/ai-context"
import { AIChatPanel } from "./AIChatPanel"
import { cn } from "@/lib/utils"

export function AIChatDrawer() {
    const { isOpen, closePanel, entityType, entityId, entityName, canUseAI } = useAIContext()

    // Don't render if AI is not available or panel is closed
    if (!canUseAI || !isOpen) {
        return null
    }

    // Determine props for AIChatPanel
    // Support case, task, and match context - otherwise works in global mode
    const getChatProps = () => {
        if ((entityType === "case" || entityType === "task" || entityType === "match") && entityId && entityName) {
            // Map match to case for the chat API (match tasks link to case)
            const chatEntityType = entityType === "match" ? "case" : entityType
            return { entityType: chatEntityType as "case" | "task", entityId, entityName }
        }
        return { entityType: null, entityId: null, entityName: null }
    }
    const chatProps = getChatProps()

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
                <AIChatPanel
                    {...chatProps}
                    onClose={closePanel}
                />
            </div>
        </>
    )
}

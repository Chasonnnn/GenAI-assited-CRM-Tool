"use client"

import * as React from "react"
import { createContext, useContext, useState, useCallback, useEffect } from "react"
import { usePathname } from "next/navigation"
import { useAuth } from "@/lib/auth-context"

// Types
export interface EntityContext {
    entityType: "case" | "intended-parent" | "dashboard" | "task"
    entityId: string
    entityName: string
}

interface AIContextValue {
    // Current entity context
    entityType: "case" | "intended-parent" | "dashboard" | "task" | null
    entityId: string | null
    entityName: string | null

    // Panel state
    isOpen: boolean
    togglePanel: () => void
    openPanel: () => void
    closePanel: () => void

    // Context management
    setContext: (ctx: EntityContext) => void
    clearContext: () => void

    // Permission flags
    canUseAI: boolean
    isAIEnabled: boolean
}

const AIContext = createContext<AIContextValue | undefined>(undefined)

export function AIContextProvider({ children }: { children: React.ReactNode }) {
    const { user } = useAuth()
    const pathname = usePathname()

    // Context state
    const [entityType, setEntityType] = useState<"case" | "intended-parent" | "dashboard" | "task" | null>(null)
    const [entityId, setEntityId] = useState<string | null>(null)
    const [entityName, setEntityName] = useState<string | null>(null)

    // Panel state
    const [isOpen, setIsOpen] = useState(false)

    // Permission check - AI is optional
    // Visibility is controlled by ai_enabled flag from org settings
    // Backend enforces use_ai_assistant permission on API calls (returns 403 if missing)
    const isAIEnabled = user?.ai_enabled ?? false
    const canUseAI = isAIEnabled

    // Clear context on route change if navigating away from entity pages
    useEffect(() => {
        const isEntityPage =
            pathname.includes("/cases/") ||
            pathname.includes("/intended-parents/")

        if (!isEntityPage && entityId) {
            // User navigated away from an entity page
            // Keep the panel open but clear the context indicator
            setEntityType(null)
            setEntityId(null)
            setEntityName(null)
        }
    }, [pathname, entityId])

    // Keyboard shortcut: Cmd+Shift+A or Ctrl+Shift+A
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "a") {
                e.preventDefault()
                if (canUseAI) {
                    setIsOpen(prev => !prev)
                }
            }
        }

        window.addEventListener("keydown", handleKeyDown)
        return () => window.removeEventListener("keydown", handleKeyDown)
    }, [canUseAI])

    const setContext = useCallback((ctx: EntityContext) => {
        setEntityType(ctx.entityType)
        setEntityId(ctx.entityId)
        setEntityName(ctx.entityName)
    }, [])

    const clearContext = useCallback(() => {
        setEntityType(null)
        setEntityId(null)
        setEntityName(null)
    }, [])

    const togglePanel = useCallback(() => {
        setIsOpen(prev => !prev)
    }, [])

    const openPanel = useCallback(() => {
        setIsOpen(true)
    }, [])

    const closePanel = useCallback(() => {
        setIsOpen(false)
    }, [])

    const value: AIContextValue = {
        entityType,
        entityId,
        entityName,
        isOpen,
        togglePanel,
        openPanel,
        closePanel,
        setContext,
        clearContext,
        canUseAI,
        isAIEnabled,
    }

    return <AIContext.Provider value={value}>{children}</AIContext.Provider>
}

export function useAIContext() {
    const context = useContext(AIContext)
    if (context === undefined) {
        throw new Error("useAIContext must be used within an AIContextProvider")
    }
    return context
}

// Hook for setting context on page load
export function useSetAIContext(ctx: EntityContext | null) {
    const { setContext, clearContext, canUseAI } = useAIContext()

    useEffect(() => {
        if (ctx && canUseAI) {
            setContext(ctx)
        }
        return () => {
            clearContext()
        }
    }, [ctx?.entityId, ctx?.entityType, canUseAI, setContext, clearContext])
}

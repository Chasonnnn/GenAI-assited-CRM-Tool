"use client"

import * as React from "react"
import { createContext, use, useEffect, useReducer, useState } from "react"
import { usePathname } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useAIToggleHotkey } from "@/lib/hooks/use-ai-toggle-hotkey"

// Types
export interface EntityContext {
    entityType: "surrogate" | "intended-parent" | "dashboard" | "task" | "match"
    entityId: string
    entityName: string
}

interface AIContextValue {
    // Current entity context
    entityType: "surrogate" | "intended-parent" | "dashboard" | "task" | "match" | null
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

type EntityContextState = {
    pathname: string
    entityType: EntityContext["entityType"] | null
    entityId: string | null
    entityName: string | null
}

type EntityContextAction =
    | { type: "set"; context: EntityContext }
    | { type: "clear" }
    | { type: "sync-pathname"; pathname: string }

function createEmptyEntityContext(pathname: string): EntityContextState {
    return {
        pathname,
        entityType: null,
        entityId: null,
        entityName: null,
    }
}

function isEntityPathname(pathname: string) {
    return (
        pathname.includes("/surrogates/") ||
        pathname.includes("/intended-parents/") ||
        pathname.includes("/matches/") ||
        pathname === "/tasks" ||
        pathname.startsWith("/tasks/")
    )
}

function aiEntityContextReducer(
    state: EntityContextState,
    action: EntityContextAction
): EntityContextState {
    switch (action.type) {
        case "set":
            if (
                state.entityType === action.context.entityType &&
                state.entityId === action.context.entityId &&
                state.entityName === action.context.entityName
            ) {
                return state
            }
            return {
                pathname: state.pathname,
                entityType: action.context.entityType,
                entityId: action.context.entityId,
                entityName: action.context.entityName,
            }
        case "clear":
            return state.entityId ? createEmptyEntityContext(state.pathname) : state
        case "sync-pathname":
            if (state.pathname === action.pathname) return state
            return state.entityId && !isEntityPathname(action.pathname)
                ? createEmptyEntityContext(action.pathname)
                : { ...state, pathname: action.pathname }
    }
}

export function AIContextProvider({ children }: { children: React.ReactNode }) {
    const { user } = useAuth()
    const pathname = usePathname()
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)

    const [entityContext, dispatchEntityContext] = useReducer(
        aiEntityContextReducer,
        pathname,
        createEmptyEntityContext
    )

    if (entityContext.pathname !== pathname) {
        dispatchEntityContext({ type: "sync-pathname", pathname })
    }

    // Panel state
    const [isOpen, setIsOpen] = useState(false)

    // Permission check - AI is optional
    // Visibility is controlled by ai_enabled flag from org settings
    // Backend enforces use_ai_assistant permission on API calls (returns 403 if missing)
    const isAIEnabled = user?.ai_enabled ?? false
    const canUseAI =
        isAIEnabled && (effectivePermissions?.permissions || []).includes("use_ai_assistant")

    useAIToggleHotkey(canUseAI, () => {
        setIsOpen(prev => !prev)
    })

    const [setContext] = useState(
        () => (ctx: EntityContext) => {
            dispatchEntityContext({ type: "set", context: ctx })
        },
    )

    const [clearContext] = useState(
        () => () => {
            dispatchEntityContext({ type: "clear" })
        },
    )

    const togglePanel = () => {
        setIsOpen(prev => !prev)
    }

    const openPanel = () => {
        setIsOpen(true)
    }

    const closePanel = () => {
        setIsOpen(false)
    }

    const value: AIContextValue = {
        entityType: entityContext.entityType,
        entityId: entityContext.entityId,
        entityName: entityContext.entityName,
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
    const context = use(AIContext)
    if (context === undefined) {
        throw new Error("useAIContext must be used within an AIContextProvider")
    }
    return context
}

// Hook for setting context on page load
export function useSetAIContext(ctx: EntityContext | null) {
    const { setContext, clearContext, canUseAI } = useAIContext()
    const entityType = ctx?.entityType ?? null
    const entityId = ctx?.entityId ?? null
    const entityName = ctx?.entityName ?? null

    useEffect(() => {
        if (entityType && entityId && entityName && canUseAI) {
            setContext({ entityType, entityId, entityName })
        }
        return () => {
            clearContext()
        }
    }, [canUseAI, clearContext, entityId, entityName, entityType, setContext])
}

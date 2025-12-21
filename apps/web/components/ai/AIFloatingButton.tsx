"use client"

import { useAIContext } from "@/lib/context/ai-context"
import { Button } from "@/components/ui/button"
import { SparklesIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { usePathname } from "next/navigation"

// Pages where the floating button should be hidden
const HIDDEN_PATHS = [
    "/settings",
    "/auth",
    "/onboarding",
]

export function AIFloatingButton() {
    const { canUseAI, isOpen, togglePanel, entityName } = useAIContext()
    const pathname = usePathname()

    // Don't show if AI is not available
    if (!canUseAI) {
        return null
    }

    // Hide on certain pages
    const shouldHide = HIDDEN_PATHS.some((path) => pathname.startsWith(path))
    if (shouldHide) {
        return null
    }

    return (
        <Button
            onClick={togglePanel}
            size="lg"
            className={cn(
                "fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full shadow-lg transition-all hover:scale-105",
                "bg-primary text-primary-foreground hover:bg-primary/90",
                isOpen && "opacity-0 pointer-events-none"
            )}
            title={`AI Assistant${entityName ? ` • ${entityName}` : ""}`}
        >
            <SparklesIcon className="h-6 w-6" />

            {/* Pulse indicator when context is available */}
            {entityName && !isOpen && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                    <span className="relative inline-flex h-4 w-4 rounded-full bg-green-500" />
                </span>
            )}
        </Button>
    )
}

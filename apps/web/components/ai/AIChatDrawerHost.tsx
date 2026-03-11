"use client"

import dynamic from "next/dynamic"
import { useAIContext } from "@/lib/context/ai-context"

const AIChatDrawer = dynamic(
    () => import("@/components/ai/AIChatDrawer").then((mod) => mod.AIChatDrawer),
    {
        loading: () => (
            <div
                aria-hidden="true"
                className="fixed inset-y-0 right-0 z-50 w-full max-w-md border-l bg-background shadow-xl md:w-[400px]"
            >
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    Loading AI assistant...
                </div>
            </div>
        ),
    }
)

export function AIChatDrawerHost() {
    const { canUseAI, isOpen } = useAIContext()

    if (!canUseAI || !isOpen) {
        return null
    }

    return <AIChatDrawer />
}

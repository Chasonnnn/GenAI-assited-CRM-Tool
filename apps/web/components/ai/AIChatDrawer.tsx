"use client"

import { AIChatPanel } from "./AIChatPanel"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetTitle,
} from "@/components/ui/sheet"
import { useIsMobile } from "@/hooks/use-mobile"
import { useAIContext } from "@/lib/context/ai-context"

function getAIChatFinalFocus() {
    return document.querySelector<HTMLElement>("[data-ai-chat-trigger]")
}

export function AIChatDrawer() {
    const {
        isOpen,
        closePanel,
        entityType,
        entityId,
        entityName,
        entityContextLabel,
        entityStatusLabel,
        canUseAI,
    } = useAIContext()
    const isMobile = useIsMobile()

    if (!canUseAI) {
        return null
    }

    const chatProps =
        (entityType === "surrogate" || entityType === "task") &&
        entityId &&
        entityName
            ? {
                entityType,
                entityId,
                entityName,
                entityContextLabel,
                entityStatusLabel,
            }
            : {
                entityType: null,
                entityId: null,
                entityName: null,
                entityContextLabel: null,
                entityStatusLabel: null,
            }

    return (
        <Sheet
            open={isOpen}
            onOpenChange={(open) => {
                if (!open) closePanel()
            }}
            modal={isMobile}
            disablePointerDismissal={!isMobile}
        >
            <SheetContent
                side="right"
                showCloseButton={false}
                showOverlay={isMobile}
                overlayClassName="bg-background/80 backdrop-blur-sm"
                finalFocus={getAIChatFinalFocus}
                className="w-full! max-w-none! p-0 md:w-[400px]!"
            >
                <SheetTitle className="sr-only">AI Assistant</SheetTitle>
                <SheetDescription className="sr-only">
                    Context-aware assistant for the current workspace record.
                </SheetDescription>
                <AIChatPanel {...chatProps} onClose={closePanel} />
            </SheetContent>
        </Sheet>
    )
}

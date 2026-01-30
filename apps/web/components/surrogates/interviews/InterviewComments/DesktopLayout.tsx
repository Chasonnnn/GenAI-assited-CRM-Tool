"use client"

import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { MessageSquareIcon, ChevronDownIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useInterviewComments } from "./context"
import { useCommentPositions } from "./hooks/useCommentPositions"
import { TranscriptPane } from "./TranscriptPane"
import { CommentsSidebar } from "./CommentsSidebar"
import { ConnectorLines } from "./ConnectorLines"
import { GeneralNotesSection } from "./GeneralNotesSection"

interface DesktopLayoutProps {
    className?: string | undefined
}

export function DesktopLayout({ className }: DesktopLayoutProps) {
    const {
        scrollContainerRef,
        layoutRef,
        generalNotes,
        layoutMinHeight,
    } = useInterviewComments()

    // Set up position recalculation observers
    useCommentPositions()

    return (
        <div className={cn("flex flex-col h-full", className)}>
            {/* Main content area: Transcript + Comments */}
            <div className="flex-1 flex overflow-hidden">
                {/* Main scrollable area containing transcript and positioned comments */}
                <div
                    ref={scrollContainerRef}
                    className="flex-1 overflow-auto"
                >
                    <div
                        ref={layoutRef}
                        className="flex min-h-full relative"
                        style={{ minHeight: layoutMinHeight || undefined }}
                    >
                        {/* SVG connector lines */}
                        <ConnectorLines />

                        {/* Transcript pane */}
                        <div className="flex-1 min-w-0 relative z-10">
                            <TranscriptPane />
                        </div>

                        {/* Anchored comments sidebar - scrolls with transcript */}
                        <CommentsSidebar />
                    </div>
                </div>
            </div>

            {/* General notes - full width at bottom (collapsible) */}
            <Collapsible defaultOpen={generalNotes.length > 0} className="shrink-0 border-t border-stone-200 dark:border-stone-800">
                <CollapsibleTrigger className="w-full px-4 py-2 flex items-center justify-between text-sm hover:bg-muted/50 transition-colors">
                    <div className="flex items-center gap-2">
                        <MessageSquareIcon className="size-4 text-muted-foreground" />
                        <span className="font-medium text-sm">General Notes</span>
                        {generalNotes.length > 0 && (
                            <Badge variant="secondary" className="text-xs px-1.5 py-0">{generalNotes.length}</Badge>
                        )}
                    </div>
                    <ChevronDownIcon className="size-4 text-muted-foreground transition-transform [[data-state=open]>&]:rotate-180" />
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <div className="max-h-48 overflow-auto bg-muted/20">
                        <GeneralNotesSection className="flex flex-col h-full" />
                    </div>
                </CollapsibleContent>
            </Collapsible>
        </div>
    )
}

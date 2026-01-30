"use client"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react"
import { useProfileCard } from "./context"

interface SectionProps {
    index: number
    title: string
    children: React.ReactNode
}

export function Section({ index, title, children }: SectionProps) {
    const { sectionOpen, toggleSection } = useProfileCard()
    const isOpen = sectionOpen[index] ?? true

    return (
        <Collapsible
            open={isOpen}
            onOpenChange={() => toggleSection(index)}
        >
            <CollapsibleTrigger className="flex w-full items-center justify-between py-2 text-sm font-medium hover:text-primary transition-colors">
                <span>{title}</span>
                {isOpen ? (
                    <ChevronUpIcon className="h-4 w-4" />
                ) : (
                    <ChevronDownIcon className="h-4 w-4" />
                )}
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-2 pt-2">
                {children}
            </CollapsibleContent>
        </Collapsible>
    )
}

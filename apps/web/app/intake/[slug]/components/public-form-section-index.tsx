"use client"

import * as React from "react"
import { CheckIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export type PublicFormSectionStatus = "complete" | "error" | "pending"

export type PublicFormSectionLink = {
    id: string
    title: string
    status: PublicFormSectionStatus
}

const STATUS_LABELS: Record<PublicFormSectionStatus, string> = {
    complete: "Complete",
    error: "Needs attention",
    pending: "Not complete",
}

function SectionStatusDot({ status, active }: { status: PublicFormSectionStatus; active: boolean }) {
    return (
        <span
            aria-hidden="true"
            className={cn(
                "flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white",
                status === "complete" && "bg-emerald-700",
                status === "error" && "bg-red-600",
                status === "pending" && (active ? "border-2 border-primary bg-white" : "border-[1.5px] border-neutral-400 bg-white"),
            )}
        >
            {status === "complete" ? <CheckIcon className="size-3" strokeWidth={3} /> : null}
            {status === "error" ? "!" : null}
        </span>
    )
}

export function PublicFormSectionIndex({
    sections,
    activeId,
}: {
    sections: PublicFormSectionLink[]
    activeId: string | null
}) {
    return (
        <nav aria-label="Sections" className="sticky top-6 hidden w-56 shrink-0 flex-col gap-1 lg:flex">
            {sections.map((section) => {
                const active = section.id === activeId
                return (
                    <a
                        key={section.id}
                        href={`#${section.id}`}
                        aria-current={active ? "location" : undefined}
                        className={cn(
                            "flex min-h-10 items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm leading-5 text-neutral-600 transition-colors",
                            "hover:bg-white/70 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30",
                            active && "bg-white font-semibold text-neutral-950 shadow-xs",
                        )}
                    >
                        <SectionStatusDot status={section.status} active={active} />
                        <span className="min-w-0 break-words">{section.title}</span>
                        <span className="sr-only">{`, ${STATUS_LABELS[section.status]}`}</span>
                    </a>
                )
            })}
        </nav>
    )
}

// The topmost section inside a band near the top of the viewport is the current one.
export function useActivePublicFormSection(sectionIds: string[]): string | null {
    const [activeId, setActiveId] = React.useState<string | null>(null)
    const idsKey = sectionIds.join("|")

    React.useEffect(() => {
        if (!idsKey || typeof IntersectionObserver === "undefined") return
        const ids = idsKey.split("|")
        const inBand = new Set<string>()
        const observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) inBand.add(entry.target.id)
                    else inBand.delete(entry.target.id)
                }
                const next = ids.find((id) => inBand.has(id))
                if (next) setActiveId(next)
            },
            { rootMargin: "-20% 0px -60% 0px" },
        )
        for (const id of ids) {
            const element = document.getElementById(id)
            if (element) observer.observe(element)
        }
        return () => observer.disconnect()
    }, [idsKey])

    return activeId && sectionIds.includes(activeId) ? activeId : sectionIds[0] ?? null
}

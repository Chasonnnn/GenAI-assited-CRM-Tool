"use client"

import type { ReactNode } from "react"
import Image from "next/image"
import { cn } from "@/lib/utils"

interface PublicFormHeaderProps {
    agencyName?: string | null | undefined
    eyebrow?: string | null | undefined
    publicTitle: string
    description?: string | null | undefined
    resolvedLogoUrl?: string | null
    showLogo: boolean
    onLogoError: () => void
    metadata: ReactNode
    children?: ReactNode
}

function getInitials(name: string): string {
    return name
        .split(/\s+/)
        .map((part) => part.replace(/^[^A-Za-z0-9À-￿]+/, ""))
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part.charAt(0))
        .join("")
        .toUpperCase()
}

function getMetadataTone(metadata: ReactNode): "success" | "warning" | "error" | "neutral" {
    const label = typeof metadata === "string" ? metadata.toLowerCase() : ""
    if (label.includes("unavailable") || label.includes("failed") || label.includes("error")) return "error"
    if (label.includes("saving") || label.includes("preview")) return "warning"
    if (label.includes("saved") || label.includes("autosave on")) return "success"
    return "neutral"
}

export function PublicFormHeader({
    agencyName,
    eyebrow,
    publicTitle,
    description,
    resolvedLogoUrl,
    showLogo,
    onLogoError,
    metadata,
    children,
}: PublicFormHeaderProps) {
    const metadataTone = getMetadataTone(metadata)
    const titleText = publicTitle.trim()
    const fallbackInitial = titleText.charAt(0).toUpperCase()
    const agencyText = agencyName?.trim()
    const eyebrowText = eyebrow?.trim()
    const descriptionText = description?.trim()

    return (
        <header>
            <div className="border-b border-stone-200/80 bg-white">
                <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-12">
                    {agencyText ? (
                        <div data-slot="public-form-agency" className="flex min-w-0 items-center gap-3">
                            {showLogo && resolvedLogoUrl ? (
                                <div className="flex h-9 min-w-9 max-w-40 shrink-0 items-center justify-center rounded-lg border border-stone-200 bg-stone-50 px-1.5">
                                    <Image
                                        src={resolvedLogoUrl}
                                        alt={`${agencyText} logo`}
                                        width={112}
                                        height={56}
                                        unoptimized
                                        className="max-h-7 w-auto max-w-full rounded-sm object-contain"
                                        onError={onLogoError}
                                    />
                                </div>
                            ) : (
                                <div
                                    aria-hidden="true"
                                    className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-[13px] font-semibold text-primary-foreground"
                                >
                                    {getInitials(agencyText)}
                                </div>
                            )}
                            <p className="line-clamp-2 min-w-0 break-words text-[15px] font-semibold leading-5 text-stone-900">
                                {agencyText}
                            </p>
                        </div>
                    ) : showLogo && resolvedLogoUrl ? (
                        <div className="flex h-10 max-w-40 shrink-0 items-center justify-center rounded-lg border border-stone-200 bg-stone-50 px-2">
                            <Image
                                src={resolvedLogoUrl}
                                alt={titleText ? `${titleText} logo` : "Form logo"}
                                width={112}
                                height={56}
                                unoptimized
                                className="max-h-8 w-auto max-w-full rounded-md object-contain"
                                onError={onLogoError}
                            />
                        </div>
                    ) : fallbackInitial ? (
                        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary">
                            <span className="text-[15px] font-semibold text-primary-foreground">{fallbackInitial}</span>
                        </div>
                    ) : (
                        <span />
                    )}
                    <div className="inline-flex items-center gap-2 text-[13px] font-medium text-stone-600">
                        <span
                            aria-hidden="true"
                            className={cn(
                                "size-1.5 rounded-full",
                                metadataTone === "success" && "bg-emerald-600",
                                metadataTone === "warning" && "bg-amber-500",
                                metadataTone === "error" && "bg-red-600",
                                metadataTone === "neutral" && "bg-stone-400",
                            )}
                        />
                        <span className={cn(metadataTone === "error" && "text-red-700")}>{metadata}</span>
                    </div>
                </div>
            </div>
            <div className="mx-auto max-w-6xl px-4 pt-10 pb-8 sm:px-6 lg:px-12">
                <div className="flex max-w-3xl flex-col gap-2.5">
                    {eyebrowText ? (
                        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-stone-500">
                            {eyebrowText}
                        </p>
                    ) : null}
                    {titleText ? (
                        <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-stone-950 md:text-4xl">
                            {titleText}
                        </h1>
                    ) : null}
                    {descriptionText ? (
                        <p className="text-base leading-7 text-stone-600">{descriptionText}</p>
                    ) : null}
                </div>
                {children ? <div className="mt-6 flex max-w-3xl flex-col gap-3">{children}</div> : null}
            </div>
        </header>
    )
}

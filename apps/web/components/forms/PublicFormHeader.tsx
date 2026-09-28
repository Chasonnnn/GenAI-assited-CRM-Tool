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
        .map((part) => part.replace(/^[^A-Za-z0-9\u00C0-\uFFFF]+/, ""))
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
        <header className="py-5 md:py-7">
            <div className="mx-auto max-w-3xl px-4">
                <div className="rounded-lg border border-stone-200/80 bg-white/95 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.07)] md:p-6">
                    <div className="flex flex-col gap-5">
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                            <div className="flex min-w-0 items-start gap-4">
                                {/* With an agency name the tile moves into the agency row above the title;
                                    the builder preview passes none and keeps the tile beside the title. */}
                                {agencyText ? null : showLogo && resolvedLogoUrl ? (
                                    <div className="flex size-12 shrink-0 items-center justify-center rounded-lg border border-stone-200 bg-stone-50 px-2 py-1">
                                        <Image
                                            src={resolvedLogoUrl}
                                            alt={titleText ? `${titleText} logo` : "Form logo"}
                                            width={112}
                                            height={56}
                                            unoptimized
                                            className="max-h-10 max-w-full rounded-md object-contain"
                                            onError={onLogoError}
                                        />
                                    </div>
                                ) : fallbackInitial ? (
                                    <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-primary">
                                        <span className="text-lg font-semibold text-primary-foreground">
                                            {fallbackInitial}
                                        </span>
                                    </div>
                                ) : null}
                                <div className="min-w-0">
                                    {agencyText ? (
                                        <div
                                            data-slot="public-form-agency"
                                            className="mb-3 flex min-w-0 items-center gap-2.5"
                                        >
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
                                            <p className="line-clamp-2 min-w-0 break-words text-[15px] font-medium leading-5 text-stone-900">
                                                {agencyText}
                                            </p>
                                        </div>
                                    ) : null}
                                    {eyebrowText ? (
                                        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">
                                            {eyebrowText}
                                        </p>
                                    ) : null}
                                    {titleText ? (
                                        <h1 className="text-2xl font-semibold leading-tight tracking-tight text-stone-950 md:text-[28px]">
                                            {titleText}
                                        </h1>
                                    ) : null}
                                    {descriptionText ? (
                                        <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600 md:text-base">
                                            {descriptionText}
                                        </p>
                                    ) : null}
                                </div>
                            </div>
                            <div
                                className={cn(
                                    "inline-flex w-fit shrink-0 items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium",
                                    metadataTone === "success" && "border-emerald-200 bg-emerald-50 text-emerald-700",
                                    metadataTone === "warning" && "border-amber-200 bg-amber-50 text-amber-700",
                                    metadataTone === "error" && "border-red-200 bg-red-50 text-red-700",
                                    metadataTone === "neutral" && "border-stone-200 bg-stone-50 text-stone-600",
                                )}
                            >
                                <span
                                    className={cn(
                                        "size-1.5 rounded-full",
                                        metadataTone === "success" && "bg-emerald-500",
                                        metadataTone === "warning" && "bg-amber-500",
                                        metadataTone === "error" && "bg-red-500",
                                        metadataTone === "neutral" && "bg-stone-400",
                                    )}
                                />
                                {metadata}
                            </div>
                        </div>
                        {children ? <div className="space-y-4">{children}</div> : null}
                    </div>
                </div>
            </div>
        </header>
    )
}

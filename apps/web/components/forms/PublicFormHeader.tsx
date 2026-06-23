"use client"

import type { ReactNode } from "react"
import Image from "next/image"
import { cn } from "@/lib/utils"

interface PublicFormHeaderProps {
    eyebrow?: string | null | undefined
    publicTitle: string
    description?: string | null | undefined
    resolvedLogoUrl?: string | null
    showLogo: boolean
    onLogoError: () => void
    metadata: ReactNode
    children?: ReactNode
}

function getMetadataTone(metadata: ReactNode): "success" | "warning" | "error" | "neutral" {
    const label = typeof metadata === "string" ? metadata.toLowerCase() : ""
    if (label.includes("unavailable") || label.includes("failed") || label.includes("error")) return "error"
    if (label.includes("saving") || label.includes("preview")) return "warning"
    if (label.includes("saved") || label.includes("autosave on")) return "success"
    return "neutral"
}

export function PublicFormHeader({
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
    const eyebrowText = eyebrow?.trim()
    const descriptionText = description?.trim()

    return (
        <header className="py-5 md:py-7">
            <div className="mx-auto max-w-3xl px-4">
                <div className="rounded-lg border border-stone-200/80 bg-white/95 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.07)] md:p-6">
                    <div className="flex flex-col gap-5">
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                            <div className="flex min-w-0 items-start gap-4">
                                {showLogo && resolvedLogoUrl ? (
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
                                    <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-violet-600 shadow-[0_10px_24px_rgba(79,70,229,0.24)]">
                                        <span className="text-lg font-semibold text-white">
                                            {fallbackInitial}
                                        </span>
                                    </div>
                                ) : null}
                                <div className="min-w-0">
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

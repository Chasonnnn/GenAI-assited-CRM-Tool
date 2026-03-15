"use client"

import type { ReactNode } from "react"
import Image from "next/image"

interface PublicFormHeaderProps {
    publicTitle: string
    description?: string | null | undefined
    resolvedLogoUrl?: string | null
    showLogo: boolean
    onLogoError: () => void
    metadata: ReactNode
    children?: ReactNode
}

export function PublicFormHeader({
    publicTitle,
    description,
    resolvedLogoUrl,
    showLogo,
    onLogoError,
    metadata,
    children,
}: PublicFormHeaderProps) {
    return (
        <header className="py-8 md:py-10">
            <div className="mx-auto max-w-3xl px-4">
                <div className="rounded-3xl border border-stone-200/70 bg-white/95 p-8 shadow-[0_2px_12px_rgba(15,23,42,0.06)] md:p-10">
                    <div className="flex flex-col items-center gap-4 text-center">
                        {showLogo && resolvedLogoUrl ? (
                            <div className="flex min-h-24 w-full items-center justify-center rounded-3xl border border-stone-100 bg-stone-50/80 px-4 py-3">
                                <Image
                                    src={resolvedLogoUrl}
                                    alt={`${publicTitle} logo`}
                                    width={352}
                                    height={112}
                                    unoptimized
                                    className="max-h-24 max-w-full w-auto rounded-2xl object-contain"
                                    onError={onLogoError}
                                />
                            </div>
                        ) : (
                            <div className="flex size-16 items-center justify-center rounded-2xl bg-primary/10">
                                <span className="text-2xl font-semibold text-primary">
                                    {publicTitle.charAt(0).toUpperCase()}
                                </span>
                            </div>
                        )}
                        <div className="space-y-3">
                            <h1 className="text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
                                {publicTitle}
                            </h1>
                            <p className="mx-auto max-w-2xl text-base text-stone-500 md:text-lg">
                                {description || "Thank you for your interest in our program"}
                            </p>
                            <div className="pt-2 text-[11px] uppercase tracking-[0.3em] text-stone-400">
                                {metadata}
                            </div>
                            {children}
                        </div>
                    </div>
                </div>
            </div>
        </header>
    )
}

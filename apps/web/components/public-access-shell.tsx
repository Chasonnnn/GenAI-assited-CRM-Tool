"use client"

import type { ReactNode } from "react"
import { ArrowRight, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

type PublicAccessFact = {
  label: string
  value: ReactNode
}

type PublicAccessNote = {
  label: string
  value: ReactNode
}

interface PublicAccessShellProps {
  title: string
  description: ReactNode
  panel: ReactNode
  facts?: PublicAccessFact[]
  notes?: PublicAccessNote[]
  footer?: ReactNode
  brandLabel?: string
  statusLabel?: string
  className?: string
}

export function PublicAccessShell({
  title,
  description,
  panel,
  facts = [],
  notes = [],
  footer,
  brandLabel = "Surrogacy Force",
  statusLabel = "Secure workspace access",
  className,
}: PublicAccessShellProps) {
  return (
    <main className={cn("relative min-h-screen overflow-hidden bg-background", className)}>
      <div className="absolute inset-0 bg-[linear-gradient(to_right,transparent_0,transparent_23px,color-mix(in_oklch,var(--border)_55%,transparent)_24px),linear-gradient(to_bottom,transparent_0,transparent_23px,color-mix(in_oklch,var(--border)_45%,transparent)_24px)] bg-[size:24px_24px] opacity-25" />
      <div className="absolute left-0 top-0 h-56 w-56 border-b border-r border-border/70 bg-primary/5" />
      <div className="absolute bottom-0 right-0 h-64 w-64 border-l border-t border-border/70 bg-card/80" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl items-center px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid w-full gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(24rem,31rem)] lg:gap-14">
          <section className="flex flex-col justify-center gap-6">
            <div className="flex items-center gap-3 text-[0.7rem] font-semibold uppercase tracking-[0.3em] text-muted-foreground">
              <span>{brandLabel}</span>
              <span className="h-px flex-1 bg-border/80" />
            </div>

            <Badge
              variant="outline"
              className="h-auto rounded-full border-primary/25 bg-primary/8 px-3 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.26em] text-foreground"
            >
              <ShieldCheck className="size-3.5 text-primary" />
              {statusLabel}
            </Badge>

            <div className="max-w-2xl space-y-4">
              <h1 className="font-[family-name:var(--font-display)] text-5xl leading-none text-foreground sm:text-6xl">
                {title}
              </h1>
              <p className="max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
                {description}
              </p>
            </div>

            {facts.length > 0 ? (
              <dl className="grid gap-3 border-y border-border/80 py-5 sm:grid-cols-3">
                {facts.map((fact) => (
                  <div key={fact.label} className="space-y-1">
                    <dt className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                      {fact.label}
                    </dt>
                    <dd className="text-sm font-medium leading-6 text-foreground">{fact.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}

            {notes.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-3">
                {notes.map((note) => (
                  <div
                    key={note.label}
                    className="rounded-2xl border border-border/70 bg-card/90 px-4 py-4"
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                      {note.label}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-foreground">{note.value}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="flex items-center">
            <div className="w-full rounded-[2rem] border border-border/80 bg-card/95 p-6 shadow-sm sm:p-8">
              {panel}

              <div className="mt-6 border-t border-border/70 pt-5">
                {footer ?? (
                  <div className="flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
                    <span>Need help signing in? Contact your administrator.</span>
                    <span className="inline-flex items-center gap-2">
                      Request access
                      <ArrowRight className="size-4" />
                    </span>
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  )
}

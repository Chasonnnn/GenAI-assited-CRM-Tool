"use client"

import * as React from "react"
import { CheckIcon, CircleAlertIcon, Loader2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { toastClearanceRef } from "@/components/ui/toast-clearance"
import { cn } from "@/lib/utils"

type SaveBarProps = {
  /** The bar renders only while there are unsaved changes or a save is running. */
  dirty: boolean
  /** Number of changed items; omit when the editor cannot count them. */
  changeCount?: number | undefined
  /** Number of invalid fields. Save stays disabled while it is above zero. */
  errorCount?: number | undefined
  /** Moves focus to the first error, for example `() => focusFirstInvalid(editorRef.current)`. */
  onErrorsClick?: (() => void) | undefined
  /** Extra status after the change and error counts, such as the areas a save affects. */
  details?: React.ReactNode
  saving?: boolean | undefined
  saveDisabled?: boolean | undefined
  onSave: () => void
  onDiscard: () => void
  saveLabel?: React.ReactNode
  discardLabel?: React.ReactNode
  className?: string | undefined
}

function formatCount(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`
}

/**
 * Sticky bottom bar for multi-field editors. Place it as the last child of the page's outer
 * container so it spans the content column; it sticks to the bottom of the nearest scroll
 * container, so no ancestor between it and that container may set overflow hidden.
 * The status live region stays mounted while the bar is hidden, so the bar's first
 * appearance is announced (a region inserted together with its text is often skipped).
 */
function SaveBar({
  dirty,
  changeCount,
  errorCount = 0,
  onErrorsClick,
  details,
  saving = false,
  saveDisabled = false,
  onSave,
  onDiscard,
  saveLabel = "Save changes",
  discardLabel = "Discard",
  className,
}: SaveBarProps) {
  const visible = dirty || saving
  const changeText =
    changeCount === undefined
      ? "Unsaved changes"
      : formatCount(changeCount, "unsaved change", "unsaved changes")
  const errorText = errorCount > 0 ? formatCount(errorCount, "error", "errors") : null

  return (
    <>
      <span role="status" data-slot="save-bar-status" className="sr-only">
        {visible ? [changeText, errorText].filter(Boolean).join(", ") : null}
      </span>
      {visible ? (
        <div
          ref={toastClearanceRef}
          role="region"
          aria-label="Unsaved changes"
          data-slot="save-bar"
          className={cn(
            "bg-card sticky bottom-0 z-20 flex flex-wrap items-center gap-x-3 gap-y-2 border-t px-4 py-3 shadow-[0_-6px_16px_-8px_rgb(0_0_0/0.12)] sm:px-6",
            className
          )}
        >
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="flex items-center gap-2 font-medium">
              <span aria-hidden="true" className="bg-warning size-2 shrink-0 rounded-full" />
              {changeText}
            </span>
            {errorText ? (
              onErrorsClick ? (
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="text-destructive h-auto gap-1 px-0"
                  onClick={onErrorsClick}
                >
                  <CircleAlertIcon aria-hidden="true" />
                  {errorText}
                </Button>
              ) : (
                <span className="text-destructive flex items-center gap-1">
                  <CircleAlertIcon aria-hidden="true" className="size-4" />
                  {errorText}
                </span>
              )
            ) : null}
            {details}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Button type="button" variant="outline" onClick={onDiscard} disabled={saving}>
              {discardLabel}
            </Button>
            <Button
              type="button"
              onClick={onSave}
              disabled={saving || saveDisabled || errorCount > 0}
            >
              {saving ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : null}
              {saveLabel}
            </Button>
          </div>
        </div>
      ) : null}
    </>
  )
}

type SaveStatusState = "idle" | "saving" | "saved" | "error"

/**
 * Inline result for a control that saves on its own (toggle, single select, blur-saved input).
 * The live region stays mounted so each state change is announced.
 */
function SaveStatus({
  state,
  className,
}: {
  state: SaveStatusState
  className?: string | undefined
}) {
  return (
    <span
      role="status"
      data-slot="save-status"
      data-state={state}
      className={cn("inline-flex min-h-4 items-center gap-1 text-xs", className)}
    >
      {state === "saving" ? (
        <span className="text-muted-foreground inline-flex items-center gap-1">
          <Loader2Icon className="size-3.5 animate-spin" aria-hidden="true" />
          Saving
        </span>
      ) : state === "saved" ? (
        <span className="text-success inline-flex items-center gap-1">
          <CheckIcon className="size-3.5" aria-hidden="true" />
          Saved
        </span>
      ) : state === "error" ? (
        <span className="text-destructive inline-flex items-center gap-1">
          <CircleAlertIcon className="size-3.5" aria-hidden="true" />
          Not saved
        </span>
      ) : null}
    </span>
  )
}

export { SaveBar, SaveStatus }
export type { SaveBarProps, SaveStatusState }

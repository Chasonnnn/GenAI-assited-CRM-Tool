"use client"

import * as React from "react"
import { Loader2Icon } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"

type ConfirmDialogProps = {
  /** A specific question that names the target, for example "Archive S10152?". */
  title: React.ReactNode
  /** One line that states the consequence. */
  description?: React.ReactNode
  /** Extra detail the decision needs, such as the stage changes or the recipient count. */
  children?: React.ReactNode
  confirmLabel: React.ReactNode
  cancelLabel?: React.ReactNode
  /** "destructive" for delete, remove, revoke and discard; "default" for sends and other commits. */
  confirmVariant?: "destructive" | "default" | "success"
  confirmIcon?: React.ReactNode
  confirmDisabled?: boolean
  /** Shown inline when onConfirm rejects with a server or network error. */
  errorFallback?: string
  /**
   * Return a promise (for example `mutation.mutateAsync(...)`) to keep the dialog open while it
   * runs: both buttons are disabled, dismissal is blocked, the dialog closes when it resolves and
   * shows the error inline when it rejects. A synchronous handler closes the dialog at once.
   */
  onConfirm: () => void | Promise<unknown>
  open?: boolean
  defaultOpen?: boolean
  onOpenChange?: (open: boolean) => void
  /** Element that opens the dialog, for example `<Button variant="destructive-ghost">Delete</Button>`. */
  trigger?: React.ReactElement
}

function isPromiseLike(value: unknown): value is PromiseLike<unknown> {
  return typeof (value as PromiseLike<unknown> | null)?.then === "function"
}

function ConfirmDialog({
  title,
  description,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  confirmVariant = "destructive",
  confirmIcon,
  confirmDisabled = false,
  errorFallback = "Couldn't complete this action. Try again.",
  onConfirm,
  open,
  defaultOpen = false,
  onOpenChange,
  trigger,
}: ConfirmDialogProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen)
  const [running, setRunning] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const cancelRef = React.useRef<HTMLButtonElement | null>(null)

  const isOpen = open ?? uncontrolledOpen

  // A parent that controls `open` can reopen the dialog for another target without calling
  // onOpenChange, so the previous error is cleared on every closed-to-open change.
  const [wasOpen, setWasOpen] = React.useState(isOpen)
  if (wasOpen !== isOpen) {
    setWasOpen(isOpen)
    if (isOpen) setError(null)
  }

  const setOpen = (next: boolean) => {
    if (open === undefined) setUncontrolledOpen(next)
    onOpenChange?.(next)
  }

  const handleOpenChange = (next: boolean) => {
    if (!next && running) return
    setOpen(next)
  }

  const handleConfirm = () => {
    setError(null)
    const result = onConfirm()
    if (!isPromiseLike(result)) {
      setOpen(false)
      return
    }
    setRunning(true)
    result.then(
      () => {
        setRunning(false)
        setOpen(false)
      },
      (reason: unknown) => {
        setRunning(false)
        setError(getActionErrorMessage(reason, errorFallback))
      },
    )
  }

  return (
    <AlertDialog open={isOpen} onOpenChange={handleOpenChange}>
      {trigger ? <AlertDialogTrigger render={trigger} /> : null}
      <AlertDialogContent initialFocus={cancelRef} aria-busy={running || undefined}>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description ? <AlertDialogDescription>{description}</AlertDialogDescription> : null}
        </AlertDialogHeader>
        {children}
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel ref={cancelRef} disabled={running}>
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            variant={confirmVariant}
            disabled={running || confirmDisabled}
            onClick={handleConfirm}
          >
            {running ? <Loader2Icon className="animate-spin" aria-hidden="true" /> : confirmIcon}
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export { ConfirmDialog }
export type { ConfirmDialogProps }

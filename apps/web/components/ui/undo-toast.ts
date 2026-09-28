import type * as React from "react"

import { toast } from "@/components/ui/toast"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"

const UNDO_TOAST_DURATION_MS = 8_000

/**
 * Success toast with an Undo action, for reversible actions that skip a confirmation dialog
 * (archive, complete task). Undo closes the toast and runs once; a failed undo shows an error toast.
 */
export function showUndoToast(
  message: React.ReactNode,
  onUndo: () => void | Promise<unknown>,
  { undoErrorMessage = "Couldn't undo. Try again." }: { undoErrorMessage?: string | undefined } = {},
): string {
  // The toast action does not close its toast, so a second click would run the undo again.
  let undoStarted = false
  const toastId = toast.success(message, {
    duration: UNDO_TOAST_DURATION_MS,
    action: {
      label: "Undo",
      onClick: () => {
        if (undoStarted) return
        undoStarted = true
        toast.dismiss(toastId)
        void Promise.resolve()
          .then(onUndo)
          .catch((error: unknown) => {
            const errorMessage = getActionErrorMessage(error, undoErrorMessage)
            if (errorMessage) toast.error(errorMessage)
          })
      },
    },
  })
  return toastId
}

"use client"

import * as React from "react"
import { Toast as ToastPrimitive } from "@base-ui/react/toast"
import {
  CircleCheckIcon,
  InfoIcon,
  OctagonXIcon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"

type ToastKind = "message" | "success" | "error" | "info" | "warning"

type ToastAction = {
  label: React.ReactNode
  onClick: () => void
}

type ToastOptions = {
  action?: ToastAction | undefined
  description?: React.ReactNode | undefined
  duration?: number | undefined
}

type ToastMethod = (title: React.ReactNode, options?: ToastOptions) => string

type ToastApi = ToastMethod & {
  dismiss: (toastId?: string) => void
  error: ToastMethod
  info: ToastMethod
  message: ToastMethod
  success: ToastMethod
  warning: ToastMethod
}

const toastManager = ToastPrimitive.createToastManager()

function addToast(kind: ToastKind, title: React.ReactNode, options: ToastOptions = {}) {
  return toastManager.add({
    title,
    type: kind,
    priority: kind === "error" ? "high" : "low",
    ...(options.description !== undefined ? { description: options.description } : {}),
    ...(options.duration !== undefined ? { timeout: options.duration } : {}),
    ...(options.action
      ? {
          actionProps: {
            children: options.action.label,
            onClick: options.action.onClick,
          },
        }
      : {}),
  })
}

const toast = Object.assign(
  ((title: React.ReactNode, options?: ToastOptions) =>
    addToast("message", title, options)) as ToastApi,
  {
    dismiss: (toastId?: string) => toastManager.close(toastId),
    error: (title: React.ReactNode, options?: ToastOptions) => addToast("error", title, options),
    info: (title: React.ReactNode, options?: ToastOptions) => addToast("info", title, options),
    message: (title: React.ReactNode, options?: ToastOptions) => addToast("message", title, options),
    success: (title: React.ReactNode, options?: ToastOptions) => addToast("success", title, options),
    warning: (title: React.ReactNode, options?: ToastOptions) => addToast("warning", title, options),
  },
)

const TOAST_ICONS: Record<ToastKind, React.ComponentType<{ className?: string }>> = {
  error: OctagonXIcon,
  info: InfoIcon,
  message: InfoIcon,
  success: CircleCheckIcon,
  warning: TriangleAlertIcon,
}

function ToastIcon({ kind }: { kind: ToastKind }) {
  const Icon = TOAST_ICONS[kind]
  return (
    <Icon
      aria-hidden="true"
      className={cn(
        "mt-0.5 size-4",
        kind === "success" && "text-emerald-600",
        kind === "error" && "text-destructive",
        kind === "warning" && "text-amber-600",
        (kind === "info" || kind === "message") && "text-primary",
      )}
    />
  )
}

function ToastViewport() {
  const { toasts } = ToastPrimitive.useToastManager()

  return (
    <ToastPrimitive.Portal>
      <ToastPrimitive.Viewport
        data-slot="toast-viewport"
        className="fixed top-4 right-4 z-[100] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2 outline-none sm:w-full"
      >
        {toasts.map((toastObject) => {
          const kind = (toastObject.type ?? "message") as ToastKind
          return (
            <ToastPrimitive.Root
              key={toastObject.id}
              toast={toastObject}
              data-slot="toast"
              swipeDirection="right"
              className="pointer-events-auto relative grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 rounded-xl border bg-popover p-4 text-popover-foreground shadow-lg transition-[transform,opacity] duration-200 data-limited:hidden data-starting-style:translate-x-6 data-starting-style:opacity-0 data-ending-style:translate-x-6 data-ending-style:opacity-0"
            >
              <ToastIcon kind={kind} />
              <ToastPrimitive.Content className="min-w-0">
                <ToastPrimitive.Title className="text-sm font-medium leading-5" />
                {toastObject.description !== undefined ? (
                  <ToastPrimitive.Description className="mt-1 text-sm text-muted-foreground" />
                ) : null}
                {toastObject.actionProps ? (
                  <ToastPrimitive.Action
                    className="mt-3 inline-flex h-8 items-center justify-center rounded-md border bg-background px-3 text-xs font-medium shadow-xs transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  />
                ) : null}
              </ToastPrimitive.Content>
              <ToastPrimitive.Close
                aria-label="Dismiss notification"
                className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >
                <XIcon className="size-4" aria-hidden="true" />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          )
        })}
      </ToastPrimitive.Viewport>
    </ToastPrimitive.Portal>
  )
}

type ToasterProps = {
  className?: string | undefined
  limit?: number | undefined
  timeout?: number | undefined
}

function Toaster({ className, limit = 3, timeout = 5_000 }: ToasterProps) {
  return (
    <div className={className} data-slot="toaster">
      <ToastPrimitive.Provider
        toastManager={toastManager}
        limit={limit}
        timeout={timeout}
      >
        <ToastViewport />
      </ToastPrimitive.Provider>
    </div>
  )
}

export { toast, Toaster }
export type { ToastOptions, ToasterProps }

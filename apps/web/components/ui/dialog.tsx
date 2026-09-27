"use client"

import * as React from "react"
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { XIcon } from "lucide-react"

function Dialog({ ...props }: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({ ...props }: DialogPrimitive.Trigger.Props) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({ ...props }: DialogPrimitive.Portal.Props) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({ ...props }: DialogPrimitive.Close.Props) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: DialogPrimitive.Backdrop.Props) {
  return (
    <DialogPrimitive.Backdrop
      data-slot="dialog-overlay"
      className={cn("data-open:animate-in data-closed:animate-out data-closed:fade-out-0 data-open:fade-in-0 bg-black/80 duration-100 supports-backdrop-filter:backdrop-blur-xs fixed inset-0 isolate z-50", className)}
      {...props}
    />
  )
}

// Unprefixed max widths so a className max-w-* replaces the size class instead of losing to a
// breakpoint variant; the calc width keeps a 1rem gutter on each side at every viewport.
const DIALOG_CONTENT_SIZE_CLASSES = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
  "2xl": "max-w-2xl",
  "3xl": "max-w-3xl",
  "4xl": "max-w-4xl",
  "5xl": "max-w-5xl",
} as const

type DialogContentSize = keyof typeof DIALOG_CONTENT_SIZE_CLASSES

/**
 * "default": one padded grid that scrolls as a whole when taller than the viewport.
 * "sectioned": fixed DialogHeader, scrolling DialogBody and fixed DialogFooter, each with its own
 * padding and dividers; use it for configuration and other long dialogs.
 */
type DialogContentLayout = "default" | "sectioned"

const DIALOG_CONTENT_LAYOUT_CLASSES: Record<DialogContentLayout, string> = {
  default: "grid gap-6 overflow-y-auto p-6",
  sectioned: "flex flex-col gap-0 overflow-hidden p-0",
}

type DialogLayoutContextValue = {
  layout: DialogContentLayout
  showCloseButton: boolean
}

const DialogLayoutContext = React.createContext<DialogLayoutContextValue>({
  layout: "default",
  showCloseButton: false,
})

function DialogContent({
  className,
  children,
  showCloseButton = true,
  size = "md",
  layout = "default",
  ...props
}: DialogPrimitive.Popup.Props & {
  showCloseButton?: boolean
  size?: DialogContentSize
  layout?: DialogContentLayout
}) {
  // The React Compiler keeps this object stable between renders with the same props.
  const layoutContext = { layout, showCloseButton }

  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Popup
        data-slot="dialog-content"
        data-size={size}
        data-layout={layout}
        className={cn(
          // A nested dialog (for example a delete confirm) renders no backdrop of its own, so the
          // parent dims itself while the nested one is open.
          "bg-background data-open:animate-in data-closed:animate-out data-closed:fade-out-0 data-open:fade-in-0 data-closed:zoom-out-95 data-open:zoom-in-95 data-nested-dialog-open:brightness-50 ring-foreground/5 w-[calc(100%-2rem)] max-h-[calc(100dvh-2rem)] rounded-4xl text-sm ring-1 duration-100 fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2 outline-none",
          DIALOG_CONTENT_LAYOUT_CLASSES[layout],
          DIALOG_CONTENT_SIZE_CLASSES[size],
          className
        )}
        {...props}
      >
        <DialogLayoutContext.Provider value={layoutContext}>
          {children}
        </DialogLayoutContext.Provider>
        {showCloseButton && (
          <DialogPrimitive.Close
            data-slot="dialog-close"
            render={
              <Button
                aria-label="Close"
                variant="ghost"
                className="absolute top-4 right-4"
                size="icon-sm"
              >
                <XIcon aria-hidden="true" />
              </Button>
            }
          />
        )}
      </DialogPrimitive.Popup>
    </DialogPortal>
  )
}

/**
 * Pass `icon` and `status` for the identity row of a configuration dialog:
 * icon tile, title with one detail line (DialogDescription), and one status badge.
 * The header keeps clear of the close button in both layouts.
 */
function DialogHeader({
  className,
  icon,
  status,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  /** Decorative icon shown in a tile before the title. */
  icon?: React.ReactNode
  /** One status element, usually a Badge, aligned to the end of the row. */
  status?: React.ReactNode
}) {
  const { layout, showCloseButton } = React.useContext(DialogLayoutContext)
  const sectioned = layout === "sectioned"
  const hasIdentityRow = Boolean(icon) || Boolean(status)

  return (
    <div
      data-slot="dialog-header"
      className={cn(
        "gap-2 flex flex-col",
        !sectioned && showCloseButton && "pr-8",
        sectioned && "shrink-0 border-b pt-5 pb-4 pl-6",
        sectioned && (showCloseButton ? "pr-14" : "pr-6"),
        hasIdentityRow && "flex-row items-center gap-3",
        className
      )}
      {...props}
    >
      {hasIdentityRow ? (
        <>
          {icon ? (
            <span
              data-slot="dialog-header-icon"
              aria-hidden="true"
              className="bg-muted text-foreground flex size-10 shrink-0 items-center justify-center rounded-xl [&_svg:not([class*='size-'])]:size-5"
            >
              {icon}
            </span>
          ) : null}
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">{children}</div>
          {status ? (
            <div
              data-slot="dialog-header-status"
              className="flex shrink-0 flex-wrap items-center justify-end gap-2"
            >
              {status}
            </div>
          ) : null}
        </>
      ) : (
        children
      )}
    </div>
  )
}

/** The scrolling region between DialogHeader and DialogFooter in the sectioned layout. */
function DialogBody({ className, ...props }: React.ComponentProps<"div">) {
  const { layout } = React.useContext(DialogLayoutContext)

  return (
    <div
      data-slot="dialog-body"
      className={cn(
        "flex flex-col gap-5",
        layout === "sectioned" && "min-h-0 flex-1 overflow-y-auto px-6 py-5",
        className
      )}
      {...props}
    />
  )
}

/**
 * One row of live state under the header, such as "Last sync 4 minutes ago" with a Sync now
 * button. Put the action last; it aligns to the end.
 */
function DialogStatusBar({ className, ...props }: React.ComponentProps<"div">) {
  const { layout } = React.useContext(DialogLayoutContext)

  return (
    <div
      data-slot="dialog-status-bar"
      className={cn(
        "bg-muted/50 flex min-h-11 flex-wrap items-center gap-x-2 gap-y-1 text-sm [&>:last-child:not(:first-child)]:ml-auto",
        layout === "sectioned" ? "shrink-0 border-b py-1.5 pr-4 pl-6" : "rounded-xl px-3 py-1.5",
        className
      )}
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  start,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
  /** Actions kept apart from Cancel/Save: left on desktop, last on mobile (for example Delete). */
  start?: React.ReactNode
}) {
  const { layout } = React.useContext(DialogLayoutContext)

  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        layout === "sectioned" && "bg-background shrink-0 border-t px-6 py-3",
        className
      )}
      {...props}
    >
      {start ? (
        <div
          data-slot="dialog-footer-start"
          className="flex flex-col-reverse gap-2 sm:mr-auto sm:flex-row"
        >
          {start}
        </div>
      ) : null}
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close render={<Button variant="outline">Close</Button>} />
      )}
    </div>
  )
}

function DialogTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-base leading-none font-medium", className)}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-muted-foreground *:[a]:hover:text-foreground text-sm *:[a]:underline *:[a]:underline-offset-3", className)}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogStatusBar,
  DialogTitle,
  DialogTrigger,
}
export type { DialogContentLayout, DialogContentSize }

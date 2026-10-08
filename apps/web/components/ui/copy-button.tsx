"use client"

import * as React from "react"
import { CheckIcon, CopyIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { ButtonVariantProps } from "@/components/ui/button-variants"
import { toast } from "@/components/ui/toast"
import { cn } from "@/lib/utils"

const COPIED_RESET_MS = 2_000

// buttonVariants tightens padding with has-[>svg], which cannot see icons inside the stacking span.
const STACKED_ICON_PADDING: Partial<Record<NonNullable<ButtonVariantProps["size"]>, string>> = {
  default: "has-[>[data-slot=copy-button-icon]]:px-3",
  sm: "has-[>[data-slot=copy-button-icon]]:px-2.5",
  lg: "has-[>[data-slot=copy-button-icon]]:px-4",
}

const ICON_CLASS = "[grid-area:1/1] transition-[opacity,scale,filter] duration-200 ease-smooth-out"
const VISIBLE_ICON_CLASS = "scale-100 opacity-100"
const HIDDEN_ICON_CLASS = "scale-25 opacity-0 blur-[2px]"

type CopyButtonProps = Omit<
  React.ComponentProps<typeof Button>,
  "children" | "onClick" | "render" | "value"
> & {
  value: string
  iconClassName?: string | undefined
} & (
    | { children: NonNullable<React.ReactNode>; "aria-label"?: string | undefined }
    | { children?: undefined; "aria-label": string }
  )

/**
 * Copies `value` and cross-fades the copy icon to a check once the clipboard write resolves.
 * The label never changes, so the button keeps its width; a polite status region announces the copy.
 */
function CopyButton({
  value,
  iconClassName,
  children,
  className,
  size = "default",
  ...props
}: CopyButtonProps) {
  // Incremented per successful copy so a repeated copy restarts the reset timer.
  const [copyCount, setCopyCount] = React.useState(0)
  const copied = copyCount > 0

  React.useEffect(() => {
    if (copyCount === 0) return
    const timer = window.setTimeout(() => setCopyCount(0), COPIED_RESET_MS)
    return () => window.clearTimeout(timer)
  }, [copyCount])

  const handleCopy = async () => {
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopyCount((count) => count + 1)
    } catch {
      setCopyCount(0)
      toast.error("Failed to copy")
    }
  }

  return (
    <>
      <Button
        aria-label={props["aria-label"] || (children ? undefined : "Copy to clipboard")}
        {...props}
        size={size}
        className={cn(STACKED_ICON_PADDING[size ?? "default"], className)}
        data-copied={copied ? "" : undefined}
        onClick={handleCopy}
      >
        <span data-slot="copy-button-icon" className="grid place-items-center">
          <CopyIcon
            aria-hidden="true"
            className={cn(ICON_CLASS, copied ? HIDDEN_ICON_CLASS : VISIBLE_ICON_CLASS, iconClassName)}
          />
          <CheckIcon
            aria-hidden="true"
            className={cn(ICON_CLASS, copied ? VISIBLE_ICON_CLASS : HIDDEN_ICON_CLASS, iconClassName)}
          />
        </span>
        {children}
      </Button>
      <span role="status" className="sr-only">
        {copied ? "Copied" : null}
      </span>
    </>
  )
}

export { CopyButton }
export type { CopyButtonProps }

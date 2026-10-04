"use client"

import { Radio as RadioPrimitive } from "@base-ui/react/radio"
import { RadioGroup as RadioGroupPrimitive } from "@base-ui/react/radio-group"

import { cn } from '@/lib/utils'

/**
 * Single-choice segmented control with radio semantics. Tab lands on the selected segment,
 * arrow keys move and select, Space and Enter select, and the selection cannot be cleared.
 */
function SegmentedControl<Value>({ className, ...props }: RadioGroupPrimitive.Props<Value>) {
  return (
    <RadioGroupPrimitive
      data-slot="segmented-control"
      className={cn(
        "inline-flex w-fit max-w-full flex-wrap items-center gap-0.5 rounded-4xl bg-muted p-[3px] data-disabled:opacity-70",
        className
      )}
      {...props}
    />
  )
}

function SegmentedControlItem({ className, onKeyDown, ...props }: RadioPrimitive.Root.Props) {
  return (
    <RadioPrimitive.Root
      data-slot="segmented-control-item"
      className={cn(
        "inline-flex h-8 cursor-pointer select-none items-center justify-center whitespace-nowrap rounded-xl border border-transparent px-3 text-sm font-medium text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 data-checked:bg-background data-checked:text-foreground data-checked:shadow-sm dark:data-checked:border-input dark:data-checked:bg-input/30 data-disabled:cursor-not-allowed data-disabled:hover:text-muted-foreground",
        className
      )}
      onKeyDown={(event) => {
        onKeyDown?.(event)
        // Base UI radios ignore Enter; a segment looks like a button, so Enter selects it too.
        if (event.key === "Enter" && !event.defaultPrevented) event.currentTarget.click()
      }}
      {...props}
    />
  )
}

export { SegmentedControl, SegmentedControlItem }

"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Label component - a styled label element.
 * 
 * For use with Base UI Field components, wrap in <Field.Root> and use <Field.Label>.
 * This standalone Label is for general use cases.
 */
function Label({
  className,
  ...props
}: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }

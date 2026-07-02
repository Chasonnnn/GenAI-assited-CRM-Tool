"use client"

import { Popover as PopoverPrimitive } from "@base-ui/react/popover"

import { PopoverContent } from "./popover-content"
import { PopoverTrigger } from "./popover-trigger"

function Popover({ ...props }: PopoverPrimitive.Root.Props) {
  return <PopoverPrimitive.Root data-slot="popover" {...props} />
}

export {
  Popover,
  PopoverContent,
  PopoverTrigger,
}

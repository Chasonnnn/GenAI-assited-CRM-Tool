"use client"

import { Popover as PopoverPrimitive } from "@base-ui/react/popover"

function PopoverTrigger({ ...props }: PopoverPrimitive.Trigger.Props) {
  return <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props} />
}

export { PopoverTrigger }

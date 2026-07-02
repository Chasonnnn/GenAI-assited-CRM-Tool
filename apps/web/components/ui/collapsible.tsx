"use client"

import { Collapsible as CollapsiblePrimitive } from "@base-ui/react/collapsible"

import { CollapsibleContent } from "./collapsible-content"
import { CollapsibleTrigger } from "./collapsible-trigger"

function Collapsible({ ...props }: CollapsiblePrimitive.Root.Props) {
  return <CollapsiblePrimitive.Root data-slot="collapsible" {...props} />
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent }

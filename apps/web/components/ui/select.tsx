"use client"

import * as React from "react"
import { Select as SelectPrimitive } from "@base-ui/react/select"

import { cn } from '@/lib/utils'
import { ChevronDownIcon, CheckIcon, ChevronUpIcon } from "lucide-react"

type SelectLabelsContextValue = {
  labels: ReadonlyMap<string, React.ReactNode>
  /** The root's itemToStringLabel resolves every value, so Base UI's own rendering is safe. */
  hasItemToStringLabel: boolean
}

const SelectItemLabelsContext = React.createContext<SelectLabelsContextValue | null>(null)

function addItemsPropLabels(labels: Map<string, React.ReactNode>, items: unknown) {
  if (items == null) return
  if (!Array.isArray(items)) {
    for (const [value, label] of Object.entries(items as Record<string, React.ReactNode>)) {
      if (!labels.has(value)) labels.set(value, label)
    }
    return
  }
  for (const entry of items as unknown[]) {
    if (!entry || typeof entry !== "object") continue
    if ("items" in entry && Array.isArray(entry.items)) {
      addItemsPropLabels(labels, entry.items)
      continue
    }
    const { value, label } = entry as { value?: unknown; label?: React.ReactNode }
    if (typeof value === "string" && label != null && !labels.has(value)) labels.set(value, label)
  }
}

function collectSelectItemLabels(children: React.ReactNode, items?: unknown) {
  const labels = new Map<string, React.ReactNode>()

  const visit = (nodes: React.ReactNode) => {
    React.Children.forEach(nodes, (child) => {
      if (!React.isValidElement(child)) return

      const element = child as React.ReactElement<{
        children?: React.ReactNode
        value?: unknown
      }>
      if (element.type === SelectItem && typeof element.props.value === "string") {
        labels.set(element.props.value, element.props.children)
        return
      }

      visit(element.props.children)
    })
  }

  visit(children)
  addItemsPropLabels(labels, items)
  return labels
}

function Select<Value = string, Multiple extends boolean | undefined = false>(
  props: SelectPrimitive.Root.Props<Value, Multiple>
) {
  const labels = collectSelectItemLabels(props.children, props.items)
  const context = { labels, hasItemToStringLabel: props.itemToStringLabel != null }

  return (
    <SelectItemLabelsContext.Provider value={context}>
      <SelectPrimitive.Root {...props} />
    </SelectItemLabelsContext.Provider>
  )
}

function SelectGroup({ className, ...props }: SelectPrimitive.Group.Props) {
  return (
    <SelectPrimitive.Group
      data-slot="select-group"
      className={cn("scroll-my-1 p-1", className)}
      {...props}
    />
  )
}

function isUnselectedValue(value: unknown) {
  return value == null || value === ""
}

function isBlankSelectLabel(label: React.ReactNode) {
  return label == null || label === false || label === ""
}

function SelectValue({
  className,
  placeholder,
  children,
  ...props
}: SelectPrimitive.Value.Props & {
  placeholder?: string
  children?: (value: string | null) => React.ReactNode
}) {
  const labelsContext = React.useContext(SelectItemLabelsContext)

  // Base UI ignores `placeholder` when children is a render function, so both render paths
  // fall back to it here. "" counts as no selection, matching Base UI's data-placeholder state.
  if (typeof children === "function") {
    return (
      <SelectPrimitive.Value
        data-slot="select-value"
        className={cn("flex flex-1 text-left", className)}
        placeholder={placeholder}
        {...props}
      >
        {(value) => {
          const label = children(value as string | null)
          if (isBlankSelectLabel(label) && isUnselectedValue(value)) return placeholder ?? null
          return label
        }}
      </SelectPrimitive.Value>
    )
  }

  // Caller-provided children, or a root itemToStringLabel, already resolve the label.
  if (children != null || labelsContext?.hasItemToStringLabel) {
    return (
      <SelectPrimitive.Value
        data-slot="select-value"
        className={cn("flex flex-1 text-left", className)}
        placeholder={placeholder}
        {...props}
      >
        {children}
      </SelectPrimitive.Value>
    )
  }

  const itemLabels = labelsContext?.labels ?? new Map<string, React.ReactNode>()

  // Base UI falls back to the raw value when it cannot resolve a label, so a stored id, enum
  // or slug would leak. Labels come from the SelectItems and the root's `items` prop instead.
  return (
    <SelectPrimitive.Value
      data-slot="select-value"
      className={cn("flex flex-1 text-left", className)}
      placeholder={placeholder}
      {...props}
    >
      {(value) => {
        // An explicit <SelectItem value=""> ("Any stage") is a real choice and keeps its label.
        if (value === "" && itemLabels.has("")) return itemLabels.get("")
        if (isUnselectedValue(value)) return placeholder ?? itemLabels.get("") ?? null
        if (typeof value === "string" && itemLabels.has(value)) return itemLabels.get(value)
        if (value && typeof value === "object" && "label" in value && value.label != null) {
          return value.label as React.ReactNode
        }
        // No item label is available yet (options still loading, or SelectItems rendered inside
        // a custom child component): show the muted placeholder or nothing, never the raw value.
        if (itemLabels.size === 0 || typeof value !== "string") {
          return placeholder ? (
            <span data-slot="select-value-unresolved" className="text-muted-foreground">
              {placeholder}
            </span>
          ) : null
        }
        return "Unknown selection"
      }}
    </SelectPrimitive.Value>
  )
}

function SelectTrigger({
  className,
  size = "default",
  children,
  ...props
}: SelectPrimitive.Trigger.Props & {
  size?: "sm" | "default"
}) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      data-size={size}
      className={cn(
        "border-input data-[placeholder]:text-muted-foreground bg-input/30 dark:hover:bg-input/50 focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors focus-visible:ring-[3px] aria-invalid:ring-[3px] data-[size=default]:h-9 data-[size=sm]:h-8 *:data-[slot=select-value]:flex *:data-[slot=select-value]:gap-1.5 [&_svg:not([class*='size-'])]:size-4 flex w-full items-center justify-between whitespace-nowrap outline-none disabled:cursor-not-allowed disabled:opacity-50 *:data-[slot=select-value]:line-clamp-1 *:data-[slot=select-value]:flex *:data-[slot=select-value]:items-center [&_svg]:pointer-events-none [&_svg]:shrink-0",
        className
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon
        render={
          <ChevronDownIcon className="text-muted-foreground size-4 pointer-events-none" />
        }
      />
    </SelectPrimitive.Trigger>
  )
}

function SelectContent({
  className,
  children,
  side = "bottom",
  sideOffset = 4,
  align = "start",
  alignOffset = 0,
  alignItemWithTrigger = false,
  ...props
}: SelectPrimitive.Popup.Props &
  Pick<
    SelectPrimitive.Positioner.Props,
    "align" | "alignOffset" | "side" | "sideOffset" | "alignItemWithTrigger"
  >) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner
        side={side}
        sideOffset={sideOffset}
        align={align}
        alignOffset={alignOffset}
        alignItemWithTrigger={alignItemWithTrigger}
        className="isolate z-[100]"
      >
        <SelectPrimitive.Popup
          data-slot="select-content"
          className={cn("bg-popover text-popover-foreground data-open:animate-in data-closed:animate-out data-closed:fade-out-0 data-open:fade-in-0 data-closed:zoom-out-95 data-open:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 ring-foreground/5 min-w-36 rounded-2xl shadow-2xl ring-1 duration-100 relative isolate z-[100] max-h-(--available-height) w-(--anchor-width) origin-(--transform-origin) overflow-x-hidden overflow-y-auto", className)}
          {...props}
        >
          <SelectScrollUpButton />
          <SelectPrimitive.List>{children}</SelectPrimitive.List>
          <SelectScrollDownButton />
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  )
}

function SelectItem({
  className,
  children,
  ...props
}: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "focus:bg-accent focus:text-accent-foreground not-data-[variant=destructive]:focus:**:text-accent-foreground gap-2.5 rounded-xl py-2 pr-8 pl-3 text-sm [&_svg:not([class*='size-'])]:size-4 *:[span]:last:flex *:[span]:last:items-center *:[span]:last:gap-2 relative flex w-full cursor-default items-center outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
        className
      )}
      {...props}
    >
      <SelectPrimitive.ItemText className="flex flex-1 gap-2 shrink-0 whitespace-nowrap">
        {children}
      </SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator render={<span className="pointer-events-none absolute right-2 flex size-4 items-center justify-center"><CheckIcon className="pointer-events-none" /></span>} />
    </SelectPrimitive.Item>
  )
}

function SelectLabel({
  className,
  ...props
}: SelectPrimitive.GroupLabel.Props) {
  return (
    <SelectPrimitive.GroupLabel
      data-slot="select-label"
      className={cn("text-muted-foreground px-3 pt-2 pb-1 text-xs", className)}
      {...props}
    />
  )
}

function SelectSeparator({
  className,
  ...props
}: SelectPrimitive.Separator.Props) {
  return (
    <SelectPrimitive.Separator
      data-slot="select-separator"
      className={cn("bg-border/50 pointer-events-none my-1 h-px", className)}
      {...props}
    />
  )
}

function SelectScrollUpButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollUpArrow>) {
  return (
    <SelectPrimitive.ScrollUpArrow
      data-slot="select-scroll-up-button"
      className={cn("bg-popover z-10 flex cursor-default items-center justify-center py-1 [&_svg:not([class*='size-'])]:size-4 top-0 w-full", className)}
      {...props}
    >
      <ChevronUpIcon
      />
    </SelectPrimitive.ScrollUpArrow>
  )
}

function SelectScrollDownButton({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.ScrollDownArrow>) {
  return (
    <SelectPrimitive.ScrollDownArrow
      data-slot="select-scroll-down-button"
      className={cn("bg-popover z-10 flex cursor-default items-center justify-center py-1 [&_svg:not([class*='size-'])]:size-4 bottom-0 w-full", className)}
      {...props}
    >
      <ChevronDownIcon
      />
    </SelectPrimitive.ScrollDownArrow>
  )
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
}

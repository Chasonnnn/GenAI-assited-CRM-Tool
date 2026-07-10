"use client"

import * as React from "react"
import { Combobox as ComboboxPrimitive } from "@base-ui/react/combobox"
import { CheckIcon, SearchIcon } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  InputGroup,
  InputGroupAddon,
} from "@/components/ui/input-group"
import { cn } from "@/lib/utils"

type CommandProps = React.ComponentProps<"div"> & {
  shouldFilter?: boolean | undefined
}

function Command({
  className,
  children,
  shouldFilter = true,
  ...props
}: CommandProps) {
  return (
    <ComboboxPrimitive.Root
      inline
      open
      autoComplete={shouldFilter ? "list" : "none"}
      filter={shouldFilter ? undefined : null}
    >
      <div
        data-slot="command"
        className={cn(
          "bg-popover text-popover-foreground flex size-full flex-col overflow-hidden rounded-4xl p-1",
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </ComboboxPrimitive.Root>
  )
}

function CommandDialog({
  title = "Command Palette",
  description = "Search for a command to run...",
  children,
  className,
  showCloseButton = false,
  ...props
}: Omit<React.ComponentProps<typeof Dialog>, "children"> & {
  title?: string
  description?: string
  className?: string
  showCloseButton?: boolean
  children: React.ReactNode
}) {
  return (
    <Dialog {...props}>
      <DialogHeader className="sr-only">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>
      <DialogContent
        className={cn("overflow-hidden rounded-4xl! p-0", className)}
        showCloseButton={showCloseButton}
      >
        {children}
      </DialogContent>
    </Dialog>
  )
}

type CommandInputProps = Omit<ComboboxPrimitive.Input.Props, "onChange"> & {
  onChange?: React.ChangeEventHandler<HTMLInputElement> | undefined
  onValueChange?: ((value: string) => void) | undefined
}

function CommandInput({
  className,
  onChange,
  onValueChange,
  ...props
}: CommandInputProps) {
  return (
    <div data-slot="command-input-wrapper" className="p-1 pb-0">
      <InputGroup className="h-9 bg-input/30">
        <ComboboxPrimitive.Input
          data-slot="command-input"
          className={cn(
            "w-full text-sm outline-hidden disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
          onChange={(event) => {
            onChange?.(event)
            onValueChange?.(event.currentTarget.value)
          }}
          {...props}
        />
        <InputGroupAddon>
          <SearchIcon className="size-4 shrink-0 opacity-50" />
        </InputGroupAddon>
      </InputGroup>
    </div>
  )
}

function CommandList({
  className,
  ...props
}: ComboboxPrimitive.List.Props) {
  return (
    <ComboboxPrimitive.List
      data-slot="command-list"
      className={cn(
        "no-scrollbar max-h-72 scroll-py-1 overflow-x-hidden overflow-y-auto outline-none",
        className,
      )}
      {...props}
    />
  )
}

function CommandEmpty({
  className,
  ...props
}: ComboboxPrimitive.Empty.Props) {
  return (
    <ComboboxPrimitive.Empty
      data-slot="command-empty"
      className={cn("py-6 text-center text-sm", className)}
      {...props}
    />
  )
}

type CommandGroupProps = Omit<ComboboxPrimitive.Group.Props, "children"> & {
  heading?: React.ReactNode
  children?: React.ReactNode
}

function CommandGroup({
  className,
  heading,
  children,
  ...props
}: CommandGroupProps) {
  return (
    <ComboboxPrimitive.Group
      data-slot="command-group"
      className={cn("overflow-hidden p-1 text-foreground", className)}
      {...props}
    >
      {heading ? (
        <ComboboxPrimitive.GroupLabel
          data-slot="command-group-heading"
          className="px-3 py-2 text-xs font-medium text-muted-foreground"
        >
          {heading}
        </ComboboxPrimitive.GroupLabel>
      ) : null}
      {children}
    </ComboboxPrimitive.Group>
  )
}

type CommandItemProps = Omit<ComboboxPrimitive.Item.Props, "onClick"> & {
  onClick?: React.MouseEventHandler<HTMLDivElement> | undefined
  onSelect?: ((value: string) => void) | undefined
}

function CommandItem({
  className,
  children,
  onClick,
  onSelect,
  value,
  ...props
}: CommandItemProps) {
  return (
    <ComboboxPrimitive.Item
      data-slot="command-item"
      className={cn(
        "group/command-item relative flex cursor-default items-center gap-2 rounded-lg px-3 py-2 text-sm outline-hidden select-none data-disabled:pointer-events-none data-disabled:opacity-50 data-highlighted:bg-muted data-highlighted:text-foreground data-highlighted:*:[svg]:text-foreground [[data-slot=dialog-content]_&]:rounded-2xl [&_svg:not([class*='size-'])]:size-4 [&_svg]:pointer-events-none [&_svg]:shrink-0",
        className,
      )}
      value={value}
      onClick={(event) => {
        onClick?.(event)
        if (!event.defaultPrevented) onSelect?.(String(value ?? ""))
      }}
      {...props}
    >
      {children}
      <CheckIcon className="ml-auto opacity-0 group-has-[[data-slot=command-shortcut]]/command-item:hidden group-data-selected/command-item:opacity-100" />
    </ComboboxPrimitive.Item>
  )
}

function CommandShortcut({
  className,
  ...props
}: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="command-shortcut"
      className={cn(
        "ml-auto text-xs tracking-widest text-muted-foreground group-data-highlighted/command-item:text-foreground",
        className,
      )}
      {...props}
    />
  )
}

export {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandShortcut,
}

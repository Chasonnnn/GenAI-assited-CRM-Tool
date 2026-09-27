"use client"

import * as React from "react"
import { Tabs as TabsPrimitive } from "@base-ui/react/tabs"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from '@/lib/utils'

function Tabs({
  className,
  orientation = "horizontal",
  resetScrollRef,
  onValueChange,
  ...props
}: TabsPrimitive.Root.Props & {
  /** Scroll container shared by the panels; it returns to the top when the tab changes. */
  resetScrollRef?: React.RefObject<HTMLElement | null> | undefined
}) {
  const handleValueChange: TabsPrimitive.Root.Props["onValueChange"] = (value, eventDetails) => {
    onValueChange?.(value, eventDetails)
    if (eventDetails.isCanceled) return
    if (resetScrollRef?.current) resetScrollRef.current.scrollTop = 0
  }

  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      className={cn(
        "gap-2 group/tabs flex data-[orientation=horizontal]:flex-col",
        className
      )}
      onValueChange={handleValueChange}
      {...props}
    />
  )
}

// Safe centering falls back to start alignment so an overflowing list can scroll to its first tab.
const tabsListVariants = cva(
  "relative isolate rounded-4xl p-[3px] group-data-vertical/tabs:rounded-2xl data-[variant=line]:rounded-none group/tabs-list text-muted-foreground inline-flex w-fit items-center justify-center-safe group-data-[orientation=vertical]/tabs:h-fit group-data-[orientation=vertical]/tabs:flex-col",
  {
    variants: {
      variant: {
        default: "bg-muted",
        line: "gap-1 bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const tabsIndicatorVariants = cva(
  "pointer-events-none absolute top-0 left-0 -z-1 transition-[translate,width,height] duration-200 ease-smooth-out",
  {
    variants: {
      variant: {
        default:
          "h-(--active-tab-height) w-(--active-tab-width) translate-x-(--active-tab-left) translate-y-(--active-tab-top) rounded-xl border border-transparent bg-background dark:border-input dark:bg-input/30",
        line: "h-0.5 w-(--active-tab-width) translate-x-(--active-tab-left) translate-y-[calc(var(--active-tab-top)+var(--active-tab-height)+1px)] bg-foreground group-data-vertical/tabs:h-(--active-tab-height) group-data-vertical/tabs:w-0.5 group-data-vertical/tabs:translate-x-[calc(var(--active-tab-left)+var(--active-tab-width)+1px)] group-data-vertical/tabs:translate-y-(--active-tab-top)",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

/**
 * Counts TabsTrigger children through fragments and arrays. Returns null when any other
 * element is present, because a wrapper component may render several tabs.
 */
function countTabTriggers(children: React.ReactNode): number | null {
  let count = 0
  let hasOtherElement = false

  const visit = (nodes: React.ReactNode) => {
    React.Children.forEach(nodes, (child) => {
      if (!React.isValidElement(child)) return
      if (child.type === React.Fragment) {
        visit((child.props as { children?: React.ReactNode }).children)
        return
      }
      if (child.type === TabsTrigger) {
        count += 1
        return
      }
      hasOtherElement = true
    })
  }

  visit(children)
  return hasOtherElement ? null : count
}

function TabsList({
  className,
  variant = "default",
  hideSingleTab = true,
  children,
  ...props
}: TabsPrimitive.List.Props &
  VariantProps<typeof tabsListVariants> & {
    /** A tab bar with one tab is hidden; its panel still renders. */
    hideSingleTab?: boolean | undefined
  }) {
  const tabCount = hideSingleTab ? countTabTriggers(children) : null
  // Hide instead of unmounting: the tabs stay registered, so uncontrolled roots keep their
  // selection and each panel keeps its aria-labelledby target.
  const isHidden = tabCount !== null && tabCount < 2

  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-variant={variant}
      className={cn(tabsListVariants({ variant }), className, isHidden && "hidden")}
      {...props}
      {...(isHidden ? { hidden: true } : {})}
    >
      {children}
      {/* After the tabs so its prehydration script finds the active tab while server HTML is parsed. */}
      <TabsPrimitive.Indicator
        data-slot="tabs-indicator"
        renderBeforeHydration
        className={tabsIndicatorVariants({ variant })}
      />
    </TabsPrimitive.List>
  )
}

function TabsTrigger({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-trigger"
      className={cn(
        "gap-1.5 rounded-xl border border-transparent px-2 py-1 text-sm font-medium group-data-vertical/tabs:px-2.5 group-data-vertical/tabs:py-1.5 [&_svg:not([class*='size-'])]:size-4 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:outline-ring text-foreground/60 hover:text-foreground dark:text-muted-foreground dark:hover:text-foreground relative inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center whitespace-nowrap transition-all group-data-[orientation=vertical]/tabs:w-full group-data-[orientation=vertical]/tabs:justify-start focus-visible:ring-[3px] focus-visible:outline-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
        "dark:data-active:text-foreground data-active:text-foreground",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      data-slot="tabs-content"
      className={cn("text-sm flex-1 outline-none", className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent }

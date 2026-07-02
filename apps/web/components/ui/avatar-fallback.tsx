"use client"

import { Avatar as AvatarPrimitive } from "@base-ui/react/avatar"

import { cn } from '@/lib/utils'

function AvatarFallback({
  className,
  ...props
}: AvatarPrimitive.Fallback.Props) {
  return (
    <AvatarPrimitive.Fallback
      data-slot="avatar-fallback"
      className={cn(
        "bg-muted text-muted-foreground rounded-full flex size-full items-center justify-center text-sm group-data-[size=sm]/avatar:text-xs",
        className
      )}
      {...props}
    />
  )
}

export { AvatarFallback }

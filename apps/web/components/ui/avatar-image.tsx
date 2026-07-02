"use client"

import { Avatar as AvatarPrimitive } from "@base-ui/react/avatar"

import { cn } from '@/lib/utils'

function AvatarImage({ className, ...props }: AvatarPrimitive.Image.Props) {
  return (
    <AvatarPrimitive.Image
      data-slot="avatar-image"
      className={cn(
        "rounded-full aspect-square size-full object-cover",
        className
      )}
      {...props}
    />
  )
}

export { AvatarImage }

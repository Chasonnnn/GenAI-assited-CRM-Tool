"use client"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { getOrgInitials } from "@/lib/org-initials"
import { cn } from "@/lib/utils"

/**
 * Square organization tile: the uploaded logo on a white plate, otherwise the initials of the
 * org name. Decorative (empty alt) because the org name is always rendered or announced next to it.
 */
export function OrgLogoTile({
    name,
    logoUrl,
    size = "default",
    className,
}: {
    name: string | null | undefined
    logoUrl: string | null | undefined
    /** default: 32px sidebar tile; lg: 64px settings preview. */
    size?: "default" | "lg"
    className?: string
}) {
    const radius = size === "lg" ? "rounded-xl" : "rounded-lg"
    return (
        <Avatar
            data-slot="org-logo-tile"
            className={cn(
                size === "lg" ? "size-16 after:rounded-xl" : "size-8 after:rounded-lg",
                radius,
                "after:border-transparent",
                className,
            )}
        >
            {logoUrl ? (
                <AvatarImage
                    src={logoUrl}
                    alt=""
                    className={cn(radius, "border border-neutral-200 bg-white object-contain dark:border-transparent")}
                />
            ) : null}
            <AvatarFallback
                // With a logo, wait briefly before showing initials so a loading logo does not flash them.
                delay={logoUrl ? 600 : undefined}
                className={cn(
                    radius,
                    size === "lg" ? "text-xl" : "text-[13px]",
                    "bg-pink-100 font-bold tracking-wide text-pink-800 dark:bg-pink-950 dark:text-pink-200",
                )}
            >
                {getOrgInitials(name)}
            </AvatarFallback>
        </Avatar>
    )
}

import Link from "next/link"
import { FileQuestion } from "lucide-react"
import { buttonVariants } from "@/components/ui/button"
import {
    Empty,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
    EmptyDescription,
} from "@/components/ui/empty"
import { cn } from "@/lib/utils"

interface NotFoundStateProps {
    title?: string
    description?: string
    primaryHref?: string
    primaryLabel?: string
    backUrl?: string
    fullHeight?: boolean
}

/**
 * Reusable 404 state component.
 *
 * Security: Uses generic "not found or no access" message to prevent
 * resource disclosure (attacker can't distinguish 403 vs 404).
 */
export function NotFoundState({
    title = "Not found",
    description = "This page doesn't exist or you don't have access.",
    primaryHref = "/dashboard",
    primaryLabel = "Go to Dashboard",
    backUrl,
    fullHeight = false,
}: NotFoundStateProps) {
    return (
        <div className={`flex ${fullHeight ? "min-h-screen" : "min-h-[50vh]"} items-center justify-center p-6`}>
            <Empty>
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <FileQuestion className="size-6" />
                    </EmptyMedia>
                    <EmptyTitle>{title}</EmptyTitle>
                    <EmptyDescription>{description}</EmptyDescription>
                </EmptyHeader>
                <div className="flex gap-2">
                    {backUrl && (
                        <Link href={backUrl} className={cn(buttonVariants({ variant: "outline" }))}>
                            Go back
                        </Link>
                    )}
                    <Link href={primaryHref} className={cn(buttonVariants())}>
                        {primaryLabel}
                    </Link>
                </div>
            </Empty>
        </div>
    )
}

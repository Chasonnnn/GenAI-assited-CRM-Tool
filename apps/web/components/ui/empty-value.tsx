import { cn } from "@/lib/utils"

/** Plain-text form for places that need a string (title attributes, exports). */
const EMPTY_VALUE_TEXT = "—"
const EMPTY_VALUE_LABEL = "Not provided"

/** True for null, undefined, and strings that are empty or whitespace. */
function isEmptyValue(value: unknown): boolean {
    return value == null || (typeof value === "string" && value.trim() === "")
}

/**
 * The one empty-field token: a muted "—" that screen readers announce as "Not provided".
 * Use `{value || <EmptyValue />}`, or `{value ?? <EmptyValue />}` when 0 is a real value.
 */
function EmptyValue({
    className,
    label = EMPTY_VALUE_LABEL,
}: {
    className?: string | undefined
    label?: string | undefined
}) {
    return (
        <span data-slot="empty-value" className={cn("text-muted-foreground", className)}>
            <span aria-hidden="true">{EMPTY_VALUE_TEXT}</span>
            <span className="sr-only">{label}</span>
        </span>
    )
}

export { EmptyValue, EMPTY_VALUE_LABEL, EMPTY_VALUE_TEXT, isEmptyValue }

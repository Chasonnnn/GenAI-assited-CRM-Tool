/** Up to two initials from an organization name, skipping symbol-only words ("Aster & Vale Family" → "AV"). */
export function getOrgInitials(name: string | null | undefined): string {
    return (name ?? "")
        .split(/\s+/)
        .map((word) => word.replace(/^[^\p{L}\p{N}]+/u, ""))
        .filter(Boolean)
        .slice(0, 2)
        .map((word) => Array.from(word)[0] ?? "")
        .join("")
        .toUpperCase()
}

export function getApiBase(): string {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    if (typeof window !== "undefined") {
        if (window.location.protocol === "https:" && base.startsWith("http://")) {
            return base.replace("http://", "https://")
        }
    }

    return base
}

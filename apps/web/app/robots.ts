import type { MetadataRoute } from "next"

export default function robots(): MetadataRoute.Robots {
    return {
        rules: {
            userAgent: "*",
            allow: ["/", "/privacy", "/privacy/", "/terms", "/terms/"],
            disallow: [
                "/dashboard",
                "/settings",
                "/appointments",
                "/surrogates",
                "/intended-parents",
                "/matches",
                "/tasks",
                "/reports",
                "/automation",
                "/ai-assistant",
                "/ai-studio",
                "/ops",
                "/mfa",
                "/auth",
                "/invite",
                "/book",
                "/intake",
                "/embed",
                "/email/unsubscribe",
            ],
        },
    }
}

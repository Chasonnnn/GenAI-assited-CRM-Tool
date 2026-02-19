"use client"

/**
 * Root crash error boundary.
 *
 * CRITICAL: This file must NOT import any modules except React.
 * It catches errors in the root layout itself, so it must be completely
 * self-contained with inline styles only.
 *
 * This is the last resort when the entire app crashes.
 */
export default function GlobalError({
    error: _error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    return (
        <html lang="en">
            <body
                style={{
                    fontFamily: "system-ui, -apple-system, sans-serif",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minHeight: "100vh",
                    margin: 0,
                    backgroundColor: "#fafaf9",
                    color: "#1c1917",
                }}
            >
                <div style={{ textAlign: "center", padding: "2rem", maxWidth: "400px" }}>
                    <div
                        style={{
                            width: "48px",
                            height: "48px",
                            margin: "0 auto 1rem",
                            borderRadius: "8px",
                            backgroundColor: "#f5f5f4",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        <svg
                            width="24"
                            height="24"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="#dc2626"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <circle cx="12" cy="12" r="10" />
                            <line x1="12" y1="8" x2="12" y2="12" />
                            <line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                    </div>
                    <h1
                        style={{
                            fontSize: "1.25rem",
                            fontWeight: 600,
                            marginBottom: "0.5rem",
                            color: "#1c1917",
                        }}
                    >
                        Something went wrong
                    </h1>
                    <p
                        style={{
                            color: "#78716c",
                            marginBottom: "1.5rem",
                            fontSize: "0.875rem",
                            lineHeight: 1.5,
                        }}
                    >
                        We're sorry, but something unexpected happened. Please try again.
                    </p>
                    <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center" }}>
                        <button
                            onClick={() => reset()}
                            style={{
                                padding: "0.5rem 1rem",
                                background:
                                    "linear-gradient(135deg, var(--primary-gradient-from), var(--primary-gradient-to))",
                                color: "white",
                                border: "none",
                                borderRadius: "0.375rem",
                                cursor: "pointer",
                                fontSize: "0.875rem",
                                fontWeight: 500,
                            }}
                        >
                            Try again
                        </button>
                        <button
                            type="button"
                            onClick={() => {
                                window.location.href = "/"
                            }}
                            style={{
                                padding: "0.5rem 1rem",
                                backgroundColor: "#f5f5f4",
                                color: "#1c1917",
                                borderRadius: "0.375rem",
                                fontSize: "0.875rem",
                                fontWeight: 500,
                                border: "none",
                                cursor: "pointer",
                            }}
                        >
                            Go home
                        </button>
                    </div>
                </div>
            </body>
        </html>
    )
}

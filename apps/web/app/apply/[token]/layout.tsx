import "@/app/globals.css"
import { ThemeProvider } from "@/components/theme-provider"

export const metadata = {
    title: "Application Form",
    description: "Submit your application",
}

export default function PublicFormLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                <link
                    href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body className="min-h-screen bg-gradient-to-b from-white to-stone-50 font-sans antialiased">
                <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
                    {children}
                </ThemeProvider>
            </body>
        </html>
    )
}

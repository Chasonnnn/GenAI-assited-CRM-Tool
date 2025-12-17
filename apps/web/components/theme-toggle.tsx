"use client"

import * as React from "react"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { cn } from "@/lib/utils"

export function ThemeToggle({ className }: { className?: string }) {
    const { resolvedTheme, setTheme } = useTheme()
    const [mounted, setMounted] = React.useState(false)

    React.useEffect(() => {
        setMounted(true)
    }, [])

    const toggleTheme = () => {
        const newTheme = resolvedTheme === "dark" ? "light" : "dark"

        // Check if View Transitions API is supported
        if (
            typeof document === 'undefined' ||
            !('startViewTransition' in document) ||
            window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ) {
            setTheme(newTheme)
            return
        }

        // Start from top-left corner
        const x = 40
        const y = 40

        // Calculate radius to cover entire screen
        const endRadius = Math.hypot(
            Math.max(x, window.innerWidth - x),
            Math.max(y, window.innerHeight - y)
        )

        // Set CSS custom properties for the animation
        document.documentElement.style.setProperty('--x', `${x}px`)
        document.documentElement.style.setProperty('--y', `${y}px`)
        document.documentElement.style.setProperty('--r', `${endRadius}px`)

        // For light->dark, we need different animation
        if (resolvedTheme === 'light') {
            document.documentElement.classList.add('dark-transition')
        }

        // Start the view transition
        document.startViewTransition(() => {
            setTheme(newTheme)
        }).finished.then(() => {
            document.documentElement.classList.remove('dark-transition')
        })
    }

    if (!mounted) {
        return (
            <button
                className={cn(
                    "relative inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors",
                    className
                )}
            >
                <span className="sr-only">Toggle theme</span>
            </button>
        )
    }

    return (
        <button
            onClick={toggleTheme}
            className={cn(
                "relative inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground transition-colors",
                className
            )}
            aria-label="Toggle theme"
        >
            <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all duration-300 dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all duration-300 dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
        </button>
    )
}

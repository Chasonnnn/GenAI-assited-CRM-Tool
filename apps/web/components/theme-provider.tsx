"use client"

import * as React from "react"
import { usePathname } from "next/navigation"
import { ThemeProvider as NextThemesProvider, type ThemeProviderProps } from "next-themes"

// Public forms are designed for a light surface (.public-form-light). Forcing the theme also
// keeps dark: utilities, the page background and portaled popovers light under a dark OS theme.
const LIGHT_ONLY_PATH_PREFIXES = ["/intake/", "/embed/forms/"]

export function ThemeProvider({ children, forcedTheme, ...props }: ThemeProviderProps) {
    const pathname = usePathname()
    const lightOnly = LIGHT_ONLY_PATH_PREFIXES.some((prefix) => pathname?.startsWith(prefix))
    return (
        <NextThemesProvider {...props} forcedTheme={lightOnly ? "light" : forcedTheme}>
            {children}
        </NextThemesProvider>
    )
}

"use client"

import * as React from "react"
import type { SurrogateRead } from "@/lib/types/surrogate"

type SurrogateDetailContextValue = {
    surrogate: SurrogateRead | null
    canEditSurrogate?: boolean
}

const SurrogateDetailContext = React.createContext<SurrogateDetailContextValue | null>(null)

type SurrogateDetailProviderProps = {
    surrogate: SurrogateRead | null
    canEditSurrogate?: boolean
    children: React.ReactNode
}

export function SurrogateDetailProvider({
    surrogate,
    canEditSurrogate = true,
    children,
}: SurrogateDetailProviderProps) {
    const value = { surrogate, canEditSurrogate }
    return (
        <SurrogateDetailContext.Provider value={value}>
            {children}
        </SurrogateDetailContext.Provider>
    )
}

export function useSurrogateDetailContext() {
    return React.use(SurrogateDetailContext)
}

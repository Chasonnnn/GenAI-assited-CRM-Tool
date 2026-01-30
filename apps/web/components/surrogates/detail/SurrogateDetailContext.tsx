"use client"

import * as React from "react"
import type { SurrogateRead } from "@/lib/types/surrogate"

type SurrogateDetailContextValue = {
    surrogate: SurrogateRead | null
}

const SurrogateDetailContext = React.createContext<SurrogateDetailContextValue | null>(null)

type SurrogateDetailProviderProps = {
    surrogate: SurrogateRead | null
    children: React.ReactNode
}

export function SurrogateDetailProvider({
    surrogate,
    children,
}: SurrogateDetailProviderProps) {
    const value = React.useMemo(() => ({ surrogate }), [surrogate])
    return (
        <SurrogateDetailContext.Provider value={value}>
            {children}
        </SurrogateDetailContext.Provider>
    )
}

export function useSurrogateDetailContext() {
    return React.useContext(SurrogateDetailContext)
}

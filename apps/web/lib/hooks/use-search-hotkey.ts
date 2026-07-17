import { useEffect, useEffectEvent } from "react"

export function useSearchHotkey(callback: () => void) {
    const onSearchHotkey = useEffectEvent(callback)

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "k") {
                event.preventDefault()
                onSearchHotkey()
            }
        }

        document.addEventListener("keydown", handleKeyDown)
        return () => document.removeEventListener("keydown", handleKeyDown)
    }, [])
}

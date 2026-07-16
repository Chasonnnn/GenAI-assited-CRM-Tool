"use client"

import { useEffect, type RefObject } from "react"

export function useEmbedFormResizeReporting(
    containerRef: RefObject<HTMLElement | null>,
    parentOrigin: string | null,
) {
    useEffect(() => {
        const element = containerRef.current
        if (!element) return

        const sendHeight = () => {
            if (!parentOrigin || window.parent === window) return
            window.parent.postMessage(
                {
                    type: "sf:form:resize",
                    height: Math.ceil(element.getBoundingClientRect().height),
                },
                parentOrigin,
            )
        }
        const observer = new ResizeObserver(sendHeight)
        observer.observe(element)
        sendHeight()

        return () => {
            observer.disconnect()
        }
    }, [containerRef, parentOrigin])
}

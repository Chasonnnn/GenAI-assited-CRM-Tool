"use client"

import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"

const POINTER_QUERIES = ["(any-pointer: fine)", "(pointer: fine)"]
const HOVER_QUERIES = ["(any-hover: hover)", "(hover: hover)"]
const HIDE_DELAY_MS = 1500
const FADE_OUT_MS = 320
const BAR_BOTTOM_OFFSET_PX = 12
const HORIZONTAL_INSET_PX = 8
const NATIVE_SCROLLBAR_VISIBILITY_THRESHOLD_PX = 6
const BOTTOM_HOVER_TRIGGER_ZONE_PX = 96

type SyncSource = "table" | "floating" | null

interface ScrollbarMetrics {
    left: number
    width: number
    viewportWidth: number
    contentWidth: number
    hasOverflow: boolean
    inView: boolean
    nativeScrollbarVisible: boolean
}

const INITIAL_METRICS: ScrollbarMetrics = {
    left: 0,
    width: 0,
    viewportWidth: 0,
    contentWidth: 0,
    hasOverflow: false,
    inView: false,
    nativeScrollbarVisible: false,
}

function clamp(value: number, min: number, max: number) {
    return Math.min(max, Math.max(min, value))
}

export function SurrogatesFloatingScrollbar({ children }: { children: ReactNode }) {
    const wrapperRef = useRef<HTMLDivElement | null>(null)
    const tableContainerRef = useRef<HTMLDivElement | null>(null)
    const floatingViewportRef = useRef<HTMLDivElement | null>(null)
    const thumbRef = useRef<HTMLDivElement | null>(null)
    const hideTimeoutRef = useRef<number | null>(null)
    const fadeTimeoutRef = useRef<number | null>(null)
    const syncSourceRef = useRef<SyncSource>(null)

    const [isMounted, setIsMounted] = useState(false)
    const [isDesktopPointer, setIsDesktopPointer] = useState(false)
    const [isActive, setIsActive] = useState(false)
    const [isFadingOut, setIsFadingOut] = useState(false)
    const [scrollLeft, setScrollLeft] = useState(0)
    const [metrics, setMetrics] = useState<ScrollbarMetrics>(INITIAL_METRICS)

    const clearHideTimeout = useCallback(() => {
        if (hideTimeoutRef.current !== null) {
            window.clearTimeout(hideTimeoutRef.current)
            hideTimeoutRef.current = null
        }
    }, [])

    const clearFadeTimeout = useCallback(() => {
        if (fadeTimeoutRef.current !== null) {
            window.clearTimeout(fadeTimeoutRef.current)
            fadeTimeoutRef.current = null
        }
    }, [])

    const detectPointerCapability = useCallback(() => {
        if (typeof window === "undefined" || !window.matchMedia) return true

        const hasFinePointer = POINTER_QUERIES.some((query) => window.matchMedia(query).matches)
        const hasHover = HOVER_QUERIES.some((query) => window.matchMedia(query).matches)

        // Prefer broader activation to avoid false negatives on mixed-input devices.
        return hasFinePointer || hasHover
    }, [])

    const resolveTableContainer = useCallback(() => {
        if (tableContainerRef.current?.isConnected) {
            return tableContainerRef.current
        }

        const wrapper = wrapperRef.current
        if (!wrapper) return null
        const container = wrapper.querySelector<HTMLDivElement>('[data-slot="table-container"]')
        tableContainerRef.current = container
        return container
    }, [])

    const resolveScrollSources = useCallback((element: HTMLElement): Array<HTMLElement | Window> => {
        const sources: Array<HTMLElement | Window> = []
        let parent = element.parentElement

        // Track all ancestors so scroll activity from any container is captured.
        while (parent) {
            sources.push(parent)
            parent = parent.parentElement
        }

        sources.push(window)
        return sources
    }, [])

    const updateMetrics = useCallback(() => {
        const tableContainer = resolveTableContainer()
        if (!tableContainer) {
            setMetrics((prev) => (prev.hasOverflow ? INITIAL_METRICS : prev))
            return false
        }

        const rect = tableContainer.getBoundingClientRect()
        const width = Math.max(0, rect.width - HORIZONTAL_INSET_PX * 2)
        const viewportWidth = tableContainer.clientWidth
        const hasOverflow = tableContainer.scrollWidth - tableContainer.clientWidth > 1
        const inView = rect.bottom > 0 && rect.top < window.innerHeight
        const nativeScrollbarVisible =
            rect.bottom >= 0 && rect.bottom <= window.innerHeight - NATIVE_SCROLLBAR_VISIBILITY_THRESHOLD_PX
        const nextMetrics: ScrollbarMetrics = {
            left: rect.left + HORIZONTAL_INSET_PX,
            width,
            viewportWidth,
            contentWidth: tableContainer.scrollWidth,
            hasOverflow,
            inView,
            nativeScrollbarVisible,
        }
        setScrollLeft(tableContainer.scrollLeft)

        setMetrics((prev) => {
            if (
                prev.left === nextMetrics.left &&
                prev.width === nextMetrics.width &&
                prev.viewportWidth === nextMetrics.viewportWidth &&
                prev.contentWidth === nextMetrics.contentWidth &&
                prev.hasOverflow === nextMetrics.hasOverflow &&
                prev.inView === nextMetrics.inView &&
                prev.nativeScrollbarVisible === nextMetrics.nativeScrollbarVisible
            ) {
                return prev
            }
            return nextMetrics
        })

        return hasOverflow && inView && width > 0 && !nativeScrollbarVisible
    }, [resolveTableContainer])

    const scheduleHide = useCallback(() => {
        clearHideTimeout()
        hideTimeoutRef.current = window.setTimeout(() => {
            setIsActive(false)
            setIsFadingOut(true)
            clearFadeTimeout()
            fadeTimeoutRef.current = window.setTimeout(() => {
                setIsFadingOut(false)
            }, FADE_OUT_MS)
        }, HIDE_DELAY_MS)
    }, [clearFadeTimeout, clearHideTimeout])

    const activateFromScroll = useCallback(() => {
        if (!isDesktopPointer) {
            setIsActive(false)
            return
        }

        const isEligible = updateMetrics()
        if (!isEligible) {
            setIsActive(false)
            setIsFadingOut(false)
            clearHideTimeout()
            clearFadeTimeout()
            return
        }

        if (isFadingOut) {
            setIsFadingOut(false)
            clearFadeTimeout()
        }
        setIsActive(true)
        scheduleHide()
    }, [clearFadeTimeout, clearHideTimeout, isDesktopPointer, isFadingOut, scheduleHide, updateMetrics])

    const syncFromTable = useCallback(() => {
        const tableContainer = resolveTableContainer()
        const floatingViewport = floatingViewportRef.current
        if (!tableContainer || !floatingViewport) return
        if (syncSourceRef.current === "floating") return

        if (Math.abs(floatingViewport.scrollLeft - tableContainer.scrollLeft) <= 1) {
            return
        }

        syncSourceRef.current = "table"
        floatingViewport.scrollLeft = tableContainer.scrollLeft
        setScrollLeft(tableContainer.scrollLeft)
        syncSourceRef.current = null
    }, [resolveTableContainer])

    const onFloatingScroll = useCallback(() => {
        const tableContainer = resolveTableContainer()
        const floatingViewport = floatingViewportRef.current
        if (!tableContainer || !floatingViewport) return
        if (syncSourceRef.current === "table") return

        if (Math.abs(tableContainer.scrollLeft - floatingViewport.scrollLeft) > 1) {
            syncSourceRef.current = "floating"
            tableContainer.scrollLeft = floatingViewport.scrollLeft
            setScrollLeft(floatingViewport.scrollLeft)
            syncSourceRef.current = null
        }

        activateFromScroll()
    }, [activateFromScroll, resolveTableContainer])

    useEffect(() => {
        setIsMounted(true)

        if (typeof window === "undefined" || !window.matchMedia) return

        const mediaQueries = [...POINTER_QUERIES, ...HOVER_QUERIES].map((query) => window.matchMedia(query))
        const handleMediaChange = () => {
            setIsDesktopPointer(detectPointerCapability())
        }

        handleMediaChange()

        if (typeof mediaQueries[0]?.addEventListener === "function") {
            for (const mediaQuery of mediaQueries) {
                mediaQuery.addEventListener("change", handleMediaChange)
            }
            return () => {
                    for (const mediaQuery of mediaQueries) {
                        mediaQuery.removeEventListener("change", handleMediaChange)
                    }
                    clearHideTimeout()
                    clearFadeTimeout()
                }
            }

        for (const mediaQuery of mediaQueries) {
            mediaQuery.addListener(handleMediaChange)
        }
        return () => {
            for (const mediaQuery of mediaQueries) {
                mediaQuery.removeListener(handleMediaChange)
            }
            clearHideTimeout()
            clearFadeTimeout()
        }
    }, [clearFadeTimeout, clearHideTimeout, detectPointerCapability])

    useEffect(() => {
        if (!isDesktopPointer) {
            setIsActive(false)
            setIsFadingOut(false)
            clearHideTimeout()
            clearFadeTimeout()
            return
        }

        const tableContainer = resolveTableContainer()
        if (!tableContainer) return
        tableContainerRef.current = tableContainer

        const onActivityScroll = () => {
            activateFromScroll()
        }
        const onMouseMove = (event: MouseEvent) => {
            if (event.clientY < window.innerHeight - BOTTOM_HOVER_TRIGGER_ZONE_PX) {
                return
            }
            activateFromScroll()
        }

        const onResize = () => {
            const isEligible = updateMetrics()
            if (!isEligible) setIsActive(false)
        }

        const onTableScroll = () => {
            syncFromTable()
            activateFromScroll()
        }

        const scrollSources = resolveScrollSources(tableContainer)
        // Capture nested scrolling from containerized layouts.
        document.addEventListener("scroll", onActivityScroll, true)
        for (const source of scrollSources) {
            if (source === window) {
                window.addEventListener("scroll", onActivityScroll, { passive: true })
                window.addEventListener("wheel", onActivityScroll, { passive: true })
                continue
            }
            source.addEventListener("scroll", onActivityScroll, { passive: true })
            source.addEventListener("wheel", onActivityScroll, { passive: true })
        }

        window.addEventListener("resize", onResize)
        window.addEventListener("mousemove", onMouseMove, { passive: true })
        tableContainer.addEventListener("scroll", onTableScroll, { passive: true })

        const resizeObserver = new ResizeObserver(() => {
            const isEligible = updateMetrics()
            if (!isEligible) {
                setIsActive(false)
            }
        })
        resizeObserver.observe(tableContainer)
        const tableElement = tableContainer.firstElementChild
        if (tableElement instanceof HTMLElement) {
            resizeObserver.observe(tableElement)
        }

        updateMetrics()

        return () => {
            resizeObserver.disconnect()
            document.removeEventListener("scroll", onActivityScroll, true)
            for (const source of scrollSources) {
                if (source === window) {
                    window.removeEventListener("scroll", onActivityScroll)
                    window.removeEventListener("wheel", onActivityScroll)
                    continue
                }
                source.removeEventListener("scroll", onActivityScroll)
                source.removeEventListener("wheel", onActivityScroll)
            }
            window.removeEventListener("resize", onResize)
            window.removeEventListener("mousemove", onMouseMove)
            tableContainer.removeEventListener("scroll", onTableScroll)
        }
    }, [activateFromScroll, clearFadeTimeout, clearHideTimeout, isDesktopPointer, resolveScrollSources, resolveTableContainer, syncFromTable, updateMetrics])

    useEffect(() => {
        if (!isActive) return
        const tableContainer = resolveTableContainer()
        const floatingViewport = floatingViewportRef.current
        if (!tableContainer || !floatingViewport) return
        floatingViewport.scrollLeft = tableContainer.scrollLeft
        setScrollLeft(tableContainer.scrollLeft)
    }, [isActive, metrics.contentWidth, resolveTableContainer])

    const isEligibleToRender =
        isMounted &&
        isDesktopPointer &&
        metrics.hasOverflow &&
        metrics.inView &&
        metrics.width > 0 &&
        !metrics.nativeScrollbarVisible
    const isVisible = isEligibleToRender && (isActive || isFadingOut)

    const floatingStyle = useMemo(
        () => ({
            left: `${Math.max(HORIZONTAL_INSET_PX, metrics.left)}px`,
            width: `${Math.max(0, metrics.width)}px`,
            bottom: `calc(env(safe-area-inset-bottom, 0px) + ${BAR_BOTTOM_OFFSET_PX}px)`,
        }),
        [metrics.left, metrics.width]
    )

    const maxScrollLeft = Math.max(0, metrics.contentWidth - metrics.viewportWidth)
    const thumbWidth = useMemo(() => {
        if (metrics.width <= 0 || metrics.contentWidth <= 0 || metrics.viewportWidth <= 0) return 0
        const ratio = metrics.viewportWidth / metrics.contentWidth
        return clamp(Math.round(metrics.width * ratio), 40, metrics.width)
    }, [metrics.contentWidth, metrics.viewportWidth, metrics.width])
    const thumbTrackWidth = Math.max(0, metrics.width - thumbWidth)
    const thumbLeft =
        maxScrollLeft > 0 && thumbTrackWidth > 0
            ? clamp((scrollLeft / maxScrollLeft) * thumbTrackWidth, 0, thumbTrackWidth)
            : 0

    const syncScrollLeft = useCallback(
        (nextScrollLeft: number) => {
            const tableContainer = resolveTableContainer()
            const floatingViewport = floatingViewportRef.current
            if (!tableContainer || !floatingViewport) return

            const bounded = clamp(nextScrollLeft, 0, Math.max(0, tableContainer.scrollWidth - tableContainer.clientWidth))
            syncSourceRef.current = "floating"
            tableContainer.scrollLeft = bounded
            floatingViewport.scrollLeft = bounded
            setScrollLeft(bounded)
            syncSourceRef.current = null
            activateFromScroll()
        },
        [activateFromScroll, resolveTableContainer]
    )

    const handleTrackPointerDown = useCallback(
        (event: React.PointerEvent<HTMLDivElement>) => {
            if (maxScrollLeft <= 0 || thumbTrackWidth <= 0 || thumbWidth <= 0) return
            if (thumbRef.current?.contains(event.target as Node)) return

            const rect = event.currentTarget.getBoundingClientRect()
            const pointerX = event.clientX - rect.left
            const nextThumbLeft = clamp(pointerX - thumbWidth / 2, 0, thumbTrackWidth)
            const nextScrollLeft = (nextThumbLeft / thumbTrackWidth) * maxScrollLeft
            syncScrollLeft(nextScrollLeft)
        },
        [maxScrollLeft, syncScrollLeft, thumbTrackWidth, thumbWidth]
    )

    const handleThumbPointerDown = useCallback(
        (event: React.PointerEvent<HTMLDivElement>) => {
            if (maxScrollLeft <= 0 || thumbTrackWidth <= 0) return

            event.preventDefault()
            event.stopPropagation()

            const startX = event.clientX
            const startScrollLeft = scrollLeft

            const handlePointerMove = (moveEvent: PointerEvent) => {
                const deltaX = moveEvent.clientX - startX
                const scrollDelta = (deltaX / thumbTrackWidth) * maxScrollLeft
                syncScrollLeft(startScrollLeft + scrollDelta)
            }

            const handlePointerUp = () => {
                window.removeEventListener("pointermove", handlePointerMove)
                window.removeEventListener("pointerup", handlePointerUp)
            }

            window.addEventListener("pointermove", handlePointerMove)
            window.addEventListener("pointerup", handlePointerUp)
        },
        [maxScrollLeft, scrollLeft, syncScrollLeft, thumbTrackWidth]
    )

    return (
        <div ref={wrapperRef}>
            {children}
            {isVisible &&
                createPortal(
                    <div
                        data-testid="surrogates-floating-scrollbar"
                        className="pointer-events-none fixed z-40 transition-[opacity,transform,filter] duration-300 ease-out motion-reduce:transition-none"
                        style={floatingStyle}
                    >
                        <div
                            className={`rounded-full border px-1.5 py-1.5 backdrop-blur-sm transition-[opacity,transform,border-color,background-color] duration-300 ease-out motion-reduce:transition-none ${
                                isActive
                                    ? "pointer-events-auto translate-y-0 border-border/80 bg-background/88 opacity-100"
                                    : "pointer-events-none translate-y-1 border-border/55 bg-background/70 opacity-0"
                            }`}
                        >
                            <div className="relative h-[8px]" onPointerDown={handleTrackPointerDown}>
                                <div
                                    ref={floatingViewportRef}
                                    data-testid="surrogates-floating-scrollbar-viewport"
                                    className="surrogates-floating-scrollbar-viewport h-[8px] overflow-x-auto overflow-y-hidden rounded-full"
                                    onScroll={onFloatingScroll}
                                >
                                    <div aria-hidden className="h-px" style={{ width: `${metrics.contentWidth}px` }} />
                                </div>
                                <div
                                    aria-hidden
                                    className="pointer-events-none absolute inset-0 rounded-full bg-muted/60"
                                />
                                <div
                                    ref={thumbRef}
                                    aria-hidden
                                    className={`absolute top-0 h-[8px] rounded-full border transition-[background-color,border-color,opacity] duration-300 ease-out motion-reduce:transition-none ${
                                        isActive
                                            ? "border-black/8 bg-[rgba(95,95,95,0.78)] opacity-100 dark:border-white/10 dark:bg-[rgba(238,238,238,0.86)]"
                                            : "border-black/6 bg-[rgba(95,95,95,0.52)] opacity-90 dark:border-white/8 dark:bg-[rgba(238,238,238,0.62)]"
                                    }`}
                                    style={{
                                        width: `${thumbWidth}px`,
                                        transform: `translateX(${thumbLeft}px)`,
                                        cursor: maxScrollLeft > 0 ? "grab" : "default",
                                    }}
                                    onPointerDown={handleThumbPointerDown}
                                />
                            </div>
                        </div>
                    </div>,
                    document.body
                )}
        </div>
    )
}

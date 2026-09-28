// Toasts sit at the bottom right. Bottom-anchored UI (floating buttons, bulk action bars, sticky
// save bars) passes `toastClearanceRef` as its ref; the toast viewport then sits above the highest
// one. This lives outside toast.tsx so tests that mock the toast module still render these callers.

const clearanceByElement = new Map<HTMLElement, number>()
const clearanceListeners = new Set<() => void>()
let toastClearance = 0
let scheduledFrame = 0

function publishToastClearance() {
  const next = Math.max(0, ...clearanceByElement.values())
  if (next === toastClearance) return
  toastClearance = next
  for (const listener of clearanceListeners) listener()
}

function subscribeToastClearance(listener: () => void) {
  clearanceListeners.add(listener)
  return () => {
    clearanceListeners.delete(listener)
  }
}

function getToastClearance() {
  return toastClearance
}

function getServerToastClearance() {
  return 0
}

/**
 * Distance from the viewport bottom to the element's top edge. A sticky bar that is not stuck sits
 * higher in the page flow than its stuck position, so this reads where the element is now.
 * Elements off screen or with their top in the upper half are ignored: toasts at the bottom cannot
 * reach them, and following them would pull the toasts up the screen.
 */
function measureToastClearance(element: HTMLElement) {
  if (element.offsetHeight === 0) return 0
  const viewportHeight = window.innerHeight
  const { top, bottom } = element.getBoundingClientRect()
  if (bottom <= 0 || top >= viewportHeight || top < viewportHeight / 2) return 0
  return Math.ceil(viewportHeight - top)
}

function remeasureToastClearance() {
  scheduledFrame = 0
  for (const element of clearanceByElement.keys()) {
    clearanceByElement.set(element, measureToastClearance(element))
  }
  publishToastClearance()
}

// Scrolling (of the page or any inner container; capture catches both) and viewport resizes move
// in-flow sticky bars without resizing them, so re-measure once per frame.
function scheduleToastClearanceMeasure() {
  if (scheduledFrame !== 0) return
  scheduledFrame = requestAnimationFrame(remeasureToastClearance)
}

function listenForLayoutChanges(listen: boolean) {
  if (listen) {
    window.addEventListener("scroll", scheduleToastClearanceMeasure, { capture: true, passive: true })
    window.addEventListener("resize", scheduleToastClearanceMeasure)
    return
  }
  window.removeEventListener("scroll", scheduleToastClearanceMeasure, { capture: true })
  window.removeEventListener("resize", scheduleToastClearanceMeasure)
  if (scheduledFrame !== 0) cancelAnimationFrame(scheduledFrame)
  scheduledFrame = 0
}

/** Callback ref for a fixed or sticky bottom element that toasts must not cover. */
function toastClearanceRef(element: HTMLElement | null) {
  if (!element) return undefined
  if (clearanceByElement.size === 0) listenForLayoutChanges(true)
  const update = () => {
    clearanceByElement.set(element, measureToastClearance(element))
    publishToastClearance()
  }
  update()
  const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update)
  observer?.observe(element)
  return () => {
    observer?.disconnect()
    clearanceByElement.delete(element)
    if (clearanceByElement.size === 0) listenForLayoutChanges(false)
    publishToastClearance()
  }
}

export { getServerToastClearance, getToastClearance, subscribeToastClearance, toastClearanceRef }

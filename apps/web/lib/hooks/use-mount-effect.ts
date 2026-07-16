import { useEffect, type EffectCallback } from "react"

/**
 * Runs a true external-system setup once for each mount and its cleanup on unmount.
 * Callers must not capture reactive values; use a named reactive hook when values can change.
 */
export function useMountEffect(effect: EffectCallback) {
    // The callback intentionally belongs to the mount that created this component instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(effect, [])
}

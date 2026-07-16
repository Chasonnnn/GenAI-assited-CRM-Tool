"use client"

import { useEffect, useReducer } from "react"

import { verifyDuoCallback } from "@/lib/api/mfa"

type DuoReturnTo = "ops" | "app"
type DuoPostMfaPath = "/dashboard" | "/ops"

type DuoCallbackState = {
    status: "loading" | "error" | "success"
    errorMessage: string | null
    recoveryCodes: string[] | null
}

type DuoCallbackAction =
    | { type: "error"; message: string }
    | { type: "success"; recoveryCodes?: string[] | null }
    | { type: "clearRecoveryCodes" }

type UseDuoCallbackVerificationOptions = {
    enabled: boolean
    refreshAuth: () => void | Promise<void>
    replace: (href: DuoPostMfaPath) => void
    returnTo: DuoReturnTo
}

const APP_POST_MFA_PATH = "/dashboard"
const duoVerifyAttempts = new Set<string>()

const initialDuoCallbackState: DuoCallbackState = {
    status: "loading",
    errorMessage: null,
    recoveryCodes: null,
}

function duoCallbackReducer(state: DuoCallbackState, action: DuoCallbackAction): DuoCallbackState {
    switch (action.type) {
        case "error":
            return {
                status: "error",
                errorMessage: action.message,
                recoveryCodes: null,
            }
        case "success":
            return {
                status: "success",
                errorMessage: null,
                recoveryCodes: action.recoveryCodes ?? null,
            }
        case "clearRecoveryCodes":
            return {
                ...state,
                recoveryCodes: null,
            }
        default:
            return state
    }
}

function setStoredAuthReturnTo(value: string) {
    try {
        sessionStorage.setItem("auth_return_to", value)
    } catch {
        // Ignore storage errors in restricted browser contexts.
    }
}

function clearStoredAuthReturnTo() {
    try {
        sessionStorage.removeItem("auth_return_to")
    } catch {
        // Ignore storage errors in restricted browser contexts.
    }
}

function navigateAfterVerification(
    returnTo: DuoReturnTo,
    replace: (href: DuoPostMfaPath) => void,
) {
    if (returnTo === "ops") {
        clearStoredAuthReturnTo()
        replace("/ops")
        return
    }
    replace(APP_POST_MFA_PATH)
}

export function useDuoCallbackVerification({
    enabled,
    refreshAuth,
    replace,
    returnTo,
}: UseDuoCallbackVerificationOptions) {
    const [{ status, errorMessage, recoveryCodes }, dispatch] = useReducer(
        duoCallbackReducer,
        initialDuoCallbackState,
    )

    useEffect(() => {
        if (!enabled) return

        const urlParams = new URLSearchParams(window.location.search)
        if (returnTo === "ops") {
            setStoredAuthReturnTo("ops")
        }

        // Duo Web SDK can return the authorization parameter as `duo_code` (default) or `code`.
        const code = urlParams.get("duo_code") ?? urlParams.get("code")
        const state = urlParams.get("state")
        if (!code || !state) {
            dispatch({
                type: "error",
                message: "Missing Duo response parameters. Please try again.",
            })
            return
        }

        const attemptKey = `${code}:${state}:${returnTo}`
        if (duoVerifyAttempts.has(attemptKey)) return
        duoVerifyAttempts.add(attemptKey)
        let active = true

        const verify = async () => {
            try {
                const result = await verifyDuoCallback(code, state, returnTo)
                if (!active) return
                const resultRecoveryCodes =
                    result.recovery_codes && result.recovery_codes.length > 0
                        ? result.recovery_codes
                        : null
                await refreshAuth()
                if (!active) return
                dispatch({ type: "success", recoveryCodes: resultRecoveryCodes })
                if (!resultRecoveryCodes) {
                    navigateAfterVerification(returnTo, replace)
                }
            } catch (error) {
                if (!active) return
                console.error("Duo verification failed:", error)
                dispatch({
                    type: "error",
                    message: "Duo verification failed. Please try again.",
                })
            }
        }

        void verify()
        return () => {
            active = false
        }
    }, [enabled, refreshAuth, replace, returnTo])

    return {
        status,
        errorMessage,
        recoveryCodes,
        completeRecoveryCodes: () => {
            dispatch({ type: "clearRecoveryCodes" })
            navigateAfterVerification(returnTo, replace)
        },
    }
}

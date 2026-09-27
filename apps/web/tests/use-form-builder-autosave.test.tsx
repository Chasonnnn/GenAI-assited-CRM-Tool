import { act, renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider, useMutation } from "@tanstack/react-query"
import { useState, type PropsWithChildren } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useFormBuilderAutosave } from "@/lib/forms/use-form-builder-autosave"

type SaveRequest = { fingerprint: string; finish: () => void }

// Mirrors the builders: autosave pauses while the save mutation is pending, and the save
// resolves with the fingerprint it submitted.
function renderAutosaveWithMutation() {
    const requests: SaveRequest[] = []
    const saveRequest = vi.fn(
        (fingerprint: string) =>
            new Promise<void>((resolve) => {
                requests.push({ fingerprint, finish: resolve })
            }),
    )
    const onSaved = vi.fn()
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const wrapper = ({ children }: PropsWithChildren) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const view = renderHook(
        ({ scopeKey }: { scopeKey: string }) => {
            const [fingerprint, setFingerprint] = useState("draft-1")
            const [savedFingerprint, setSavedFingerprint] = useState("draft-0")
            const request = useMutation({ mutationFn: saveRequest })
            useFormBuilderAutosave({
                enabled: !request.isPending,
                scopeKey,
                fingerprint,
                savedFingerprint,
                save: async () => {
                    await request.mutateAsync(fingerprint)
                    return fingerprint
                },
                onSaving: () => {},
                onSaved: (submittedFingerprint) => {
                    onSaved(submittedFingerprint)
                    setSavedFingerprint(submittedFingerprint)
                },
                onError: () => {},
            })
            return { isPending: request.isPending, savedFingerprint, setFingerprint }
        },
        { initialProps: { scopeKey: "form-1" }, wrapper },
    )
    return { ...view, client, onSaved, requests, saveRequest }
}

async function advance(ms: number) {
    await act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
    })
}

describe("useFormBuilderAutosave", () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("saves the active draft only after the debounce interval", async () => {
        const save = vi.fn().mockResolvedValue({ id: "form-1" })
        const onSaving = vi.fn()
        const onSaved = vi.fn()
        const onError = vi.fn()

        renderHook(() =>
            useFormBuilderAutosave({
                enabled: true,
                scopeKey: "form-1",
                fingerprint: "draft-1",
                savedFingerprint: "draft-0",
                save,
                onSaving,
                onSaved,
                onError,
            }),
        )

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1199)
        })
        expect(save).not.toHaveBeenCalled()

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1)
        })

        expect(onSaving).toHaveBeenCalledTimes(1)
        expect(save).toHaveBeenCalledTimes(1)
        expect(onSaved).toHaveBeenCalledWith({ id: "form-1" })
        expect(onError).not.toHaveBeenCalled()
    })

    it("records a save that finishes after its pending request paused autosave", async () => {
        const { client, onSaved, requests, result, saveRequest } = renderAutosaveWithMutation()

        await advance(1200)
        await advance(10)
        expect(saveRequest).toHaveBeenCalledTimes(1)
        expect(result.current.isPending).toBe(true)

        requests[0].finish()
        await advance(10)

        expect(onSaved).toHaveBeenCalledWith("draft-1")
        expect(result.current.savedFingerprint).toBe("draft-1")

        await advance(5000)
        expect(saveRequest).toHaveBeenCalledTimes(1)
        client.clear()
    })

    it("keeps edits made during an in-flight save dirty and saves them next", async () => {
        const { client, requests, result, saveRequest } = renderAutosaveWithMutation()

        await advance(1200)
        expect(requests.map((request) => request.fingerprint)).toEqual(["draft-1"])

        act(() => {
            result.current.setFingerprint("draft-2")
        })
        await advance(5000)
        expect(saveRequest).toHaveBeenCalledTimes(1)

        requests[0].finish()
        await advance(10)
        expect(result.current.savedFingerprint).toBe("draft-1")

        await advance(1200)
        expect(requests.map((request) => request.fingerprint)).toEqual(["draft-1", "draft-2"])

        requests[1].finish()
        await advance(10)
        expect(result.current.savedFingerprint).toBe("draft-2")

        await advance(5000)
        expect(saveRequest).toHaveBeenCalledTimes(2)
        client.clear()
    })

    it("ignores a save that finishes after the builder moves to another form", async () => {
        const { client, onSaved, requests, rerender } = renderAutosaveWithMutation()

        await advance(1200)
        rerender({ scopeKey: "form-2" })

        requests[0].finish()
        await advance(10)

        expect(onSaved).not.toHaveBeenCalled()
        client.clear()
    })
})

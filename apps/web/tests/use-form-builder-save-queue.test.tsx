import { act, render, renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider, useMutation } from "@tanstack/react-query"
import { Activity, useState, type PropsWithChildren } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useFormBuilderAutosave } from "@/lib/forms/use-form-builder-autosave"
import { useFormBuilderSaveQueue } from "@/lib/forms/use-form-builder-save-queue"

type SaveRequest = { fingerprint: string; finish: () => void; fail: () => void }

// A minimal builder: a real save mutation, the save queue, and autosave paused while the queue
// is busy, as in the automation and template builders.
function renderBuilder() {
    const requests: SaveRequest[] = []
    const saveRequest = vi.fn(
        (fingerprint: string) =>
            new Promise<void>((resolve, reject) => {
                requests.push({ fingerprint, finish: resolve, fail: () => reject(new Error("Network error")) })
            }),
    )
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const wrapper = ({ children }: PropsWithChildren) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const view = renderHook(
        ({ scopeKey }: { scopeKey: string }) => {
            const [fingerprint, setFingerprint] = useState("draft-1")
            const [savedFingerprint, setSavedFingerprint] = useState("draft-0")
            const [failedFingerprint, setFailedFingerprint] = useState("")
            const [status, setStatus] = useState("idle")
            const request = useMutation({ mutationFn: saveRequest })
            const saveQueue = useFormBuilderSaveQueue(scopeKey)
            const save = () => {
                const submitted = fingerprint
                setStatus("saving")
                return saveQueue.enqueue(
                    async () => {
                        await request.mutateAsync(submitted)
                        return submitted
                    },
                    {
                        onSuccess: (saved) => {
                            setSavedFingerprint(saved)
                            setFailedFingerprint("")
                            setStatus("saved")
                        },
                        onError: () => {
                            setFailedFingerprint(submitted)
                            setStatus("error")
                        },
                    },
                )
            }
            useFormBuilderAutosave({
                enabled: !saveQueue.isBusy,
                fingerprint,
                savedFingerprint,
                failedFingerprint,
                save: () => {
                    void save()
                },
            })
            return { isBusy: saveQueue.isBusy, save, savedFingerprint, setFingerprint, status }
        },
        { initialProps: { scopeKey: "form-a" }, wrapper },
    )
    return { ...view, client, requests }
}

async function advance(ms: number) {
    await act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
    })
}

describe("useFormBuilderSaveQueue", () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("sends one request at a time and applies results in request order", async () => {
        const { client, requests, result } = renderBuilder()
        await advance(1200)
        await advance(3000)
        expect(requests.map((request) => request.fingerprint)).toEqual(["draft-1"])

        act(() => {
            result.current.setFingerprint("draft-2")
        })
        act(() => {
            void result.current.save()
        })
        await advance(10)
        expect(requests).toHaveLength(1)
        expect(result.current.isBusy).toBe(true)

        requests[0].fail()
        await advance(10)
        expect(result.current.status).toBe("error")
        expect(requests.map((request) => request.fingerprint)).toEqual(["draft-1", "draft-2"])

        requests[1].finish()
        await advance(10)
        await advance(5000)
        expect(result.current.status).toBe("saved")
        expect(result.current.savedFingerprint).toBe("draft-2")
        expect(result.current.isBusy).toBe(false)
        expect(requests).toHaveLength(2)
        client.clear()
    })

    it("keeps edits made during a request dirty and autosaves them once after it finishes", async () => {
        const { client, requests, result } = renderBuilder()
        await advance(1200)
        act(() => {
            result.current.setFingerprint("draft-2")
        })
        await advance(3000)
        expect(requests).toHaveLength(1)

        requests[0].finish()
        await advance(10)
        expect(result.current.savedFingerprint).toBe("draft-1")

        await advance(1200)
        await advance(3000)
        expect(requests.map((request) => request.fingerprint)).toEqual(["draft-1", "draft-2"])

        requests[1].finish()
        await advance(10)
        await advance(5000)
        expect(result.current.savedFingerprint).toBe("draft-2")
        expect(requests).toHaveLength(2)
        client.clear()
    })

    it("ignores a result after the builder leaves the form and comes back", async () => {
        const { client, requests, rerender, result } = renderBuilder()
        await advance(1200)
        rerender({ scopeKey: "form-b" })
        rerender({ scopeKey: "form-a" })

        requests[0].finish()
        await advance(10)

        expect(result.current.savedFingerprint).toBe("draft-0")
        expect(result.current.isBusy).toBe(false)
        client.clear()
    })

    it("applies a result after the builder is hidden and shown again", async () => {
        let finish = () => {}
        const onSuccess = vi.fn()
        let queue: ReturnType<typeof useFormBuilderSaveQueue> | null = null
        function Builder() {
            queue = useFormBuilderSaveQueue("form-a")
            return null
        }
        const view = render(
            <Activity mode="visible">
                <Builder />
            </Activity>,
        )
        act(() => {
            void queue?.enqueue(() => new Promise<string>((resolve) => (finish = () => resolve("saved"))), {
                onSuccess,
                onError: () => {},
            })
        })
        await advance(10)

        view.rerender(
            <Activity mode="hidden">
                <Builder />
            </Activity>,
        )
        view.rerender(
            <Activity mode="visible">
                <Builder />
            </Activity>,
        )
        finish()
        await advance(10)

        expect(onSuccess).toHaveBeenCalledWith("saved", expect.anything())
        expect(queue?.isBusy).toBe(false)
    })
})

import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    createForm,
    listFormMappingOptions,
    promoteIntakeLead,
    submitSharedPublicForm,
} from "@/lib/api/forms"

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockUpload = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
        upload: (...args: unknown[]) => mockUpload(...args),
    },
}))

describe("hosted donor forms API client", () => {
    beforeEach(() => {
        mockGet.mockReset().mockResolvedValue([])
        mockPost.mockReset().mockResolvedValue({})
        mockUpload.mockReset().mockResolvedValue({})
    })

    it("requests donor-scoped mappings and carries the form lead type", async () => {
        await listFormMappingOptions("egg_donor")
        await createForm({
            name: "Egg Donor Application",
            lead_kind: "egg_donor",
        })

        expect(mockGet).toHaveBeenCalledWith("/forms/mapping-options?lead_kind=egg_donor")
        expect(mockPost).toHaveBeenCalledWith("/forms", {
            name: "Egg Donor Application",
            lead_kind: "egg_donor",
        })
    })

    it("keeps surrogate mapping requests as the default", async () => {
        await listFormMappingOptions()

        expect(mockGet).toHaveBeenCalledWith("/forms/mapping-options?lead_kind=surrogate")
    })

    it("uses the shared intake-lead promotion endpoint for donors", async () => {
        await promoteIntakeLead("lead-donor", {})

        expect(mockPost).toHaveBeenCalledWith("/forms/intake-leads/lead-donor/promote", {})
    })

    it("includes the stable submission attempt in the multipart request", async () => {
        await submitSharedPublicForm(
            "donor-intake", { full_name: "Test Applicant" }, [], undefined,
            undefined, undefined, "published-version", "submission-attempt",
        )
        expect(mockUpload).toHaveBeenCalledWith(
            "/forms/public/intake/donor-intake/submit", expect.any(FormData), undefined,
        )
        const body = mockUpload.mock.calls[0]?.[1] as FormData
        expect(body.get("idempotency_key")).toBe("submission-attempt")
        expect(body.get("published_version_id")).toBe("published-version")
    })
})

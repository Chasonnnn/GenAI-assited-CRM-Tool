import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    createEmailTemplateDraft,
    createEmailTemplateDraftFromTemplate,
    discardEmailTemplateDraft,
    getEmailTemplateDraft,
    listEmailTemplateDrafts,
    publishEmailTemplateDraft,
    sendTestEmailTemplateDraft,
    updateEmailTemplateDraft,
} from "@/lib/api/email-template-drafts"

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()
const mockDelete = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
        patch: (...args: unknown[]) => mockPatch(...args),
        delete: (...args: unknown[]) => mockDelete(...args),
    },
}))

describe("email template drafts API", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockPost.mockReset()
        mockPatch.mockReset()
        mockDelete.mockReset()
        mockGet.mockResolvedValue({})
        mockPost.mockResolvedValue({})
        mockPatch.mockResolvedValue({})
        mockDelete.mockResolvedValue(undefined)
    })

    it("lists drafts with exact visibility filters and gets one draft", async () => {
        await listEmailTemplateDrafts({
            scope: "personal",
            showAllPersonal: true,
        })
        await getEmailTemplateDraft("draft/id")

        expect(mockGet).toHaveBeenNthCalledWith(
            1,
            "/email-template-drafts?scope=personal&show_all_personal=true",
        )
        expect(mockGet).toHaveBeenNthCalledWith(
            2,
            "/email-template-drafts/draft%2Fid",
        )
    })

    it("lists drafts without a dangling query string when filters are omitted", async () => {
        await listEmailTemplateDrafts()

        expect(mockGet).toHaveBeenCalledWith("/email-template-drafts")
    })

    it("creates a new draft and creates one from a published template", async () => {
        const data = {
            name: "Journey update",
            subject: "An update for {{full_name}}",
            from_email: "Journey Team <journey@example.com>",
            body: "<p>Hello {{full_name}}</p>",
            scope: "org" as const,
        }

        await createEmailTemplateDraft(data)
        await createEmailTemplateDraftFromTemplate("template/id")

        expect(mockPost).toHaveBeenNthCalledWith(
            1,
            "/email-template-drafts",
            data,
        )
        expect(mockPost).toHaveBeenNthCalledWith(
            2,
            "/email-template-drafts/from-template/template%2Fid",
        )
    })

    it("updates with the exact revision fence and discards through the draft resource", async () => {
        const data = {
            subject: "Revised subject",
            from_email: null,
            expected_revision: 4,
        }

        await updateEmailTemplateDraft("draft/id", data)
        await discardEmailTemplateDraft("draft/id", 4)

        expect(mockPatch).toHaveBeenCalledWith(
            "/email-template-drafts/draft%2Fid",
            data,
        )
        expect(mockDelete).toHaveBeenCalledWith(
            "/email-template-drafts/draft%2Fid?expected_revision=4",
        )
    })

    it("publishes with both draft and published-version fences", async () => {
        const data = {
            expected_revision: 5,
            expected_published_version: 9,
        }

        await publishEmailTemplateDraft("draft/id", data)

        expect(mockPost).toHaveBeenCalledWith(
            "/email-template-drafts/draft%2Fid/publish",
            data,
        )
    })

    it("publishes a new draft with an explicit null published version", async () => {
        const data = {
            expected_revision: 1,
            expected_published_version: null,
        }

        await publishEmailTemplateDraft("new-draft", data)

        expect(mockPost).toHaveBeenCalledWith(
            "/email-template-drafts/new-draft/publish",
            data,
        )
    })

    it("test-sends the saved draft with the delivery idempotency payload", async () => {
        const payload = {
            to_email: "reviewer@example.com",
            variables: { full_name: "Avery" },
            idempotency_key: "template-draft-test/123",
            ignore_opt_out: true,
            expected_revision: 4,
        }

        await sendTestEmailTemplateDraft("draft/id", payload)

        expect(mockPost).toHaveBeenCalledWith(
            "/email-template-drafts/draft%2Fid/test",
            payload,
        )
    })
})

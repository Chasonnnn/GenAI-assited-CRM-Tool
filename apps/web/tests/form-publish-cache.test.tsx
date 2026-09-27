import { act, renderHook } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { PropsWithChildren } from "react"
import { describe, expect, it, vi } from "vitest"

import type { FormRead, FormSchema } from "@/lib/api/forms"
import type { PlatformFormTemplate } from "@/lib/api/platform"
import { formKeys, usePublishForm } from "@/lib/hooks/use-forms"
import {
    usePublishPlatformFormTemplate,
    useUpdatePlatformFormTemplate,
} from "@/lib/hooks/use-platform-templates"

const { publishForm, publishPlatformFormTemplate, updatePlatformFormTemplate } = vi.hoisted(() => ({
    publishForm: vi.fn(),
    publishPlatformFormTemplate: vi.fn(),
    updatePlatformFormTemplate: vi.fn(),
}))

vi.mock("@/lib/api/forms", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/forms")>()),
    publishForm,
}))

vi.mock("@/lib/api/platform", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/platform")>()),
    publishPlatformFormTemplate,
    updatePlatformFormTemplate,
}))

const buildClient = () =>
    new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })

const buildWrapper = (client: QueryClient) =>
    function Wrapper({ children }: PropsWithChildren) {
        return <QueryClientProvider client={client}>{children}</QueryClientProvider>
    }

describe("form publish cache", () => {
    it("marks the saved draft schema as live after publishing a form", async () => {
        const client = buildClient()
        const draftSchema: FormSchema = { pages: [{ title: "Application", fields: [] }], public_title: "Apply now" }
        const cachedForm: FormRead = {
            id: "form-1",
            name: "Surrogate Application",
            status: "published",
            purpose: "surrogate_application",
            lead_kind: "surrogate",
            created_at: "2026-09-20T00:00:00Z",
            updated_at: "2026-09-26T00:00:00Z",
            description: null,
            form_schema: draftSchema,
            published_schema: { ...draftSchema, public_title: "Apply today" },
            max_file_size_bytes: 10 * 1024 * 1024,
            max_file_count: 10,
            allowed_mime_types: null,
            default_application_email_template_id: null,
        }
        client.setQueryData(formKeys.detail("form-1"), cachedForm)
        publishForm.mockResolvedValue({ id: "form-1", status: "published", published_at: "2026-09-27T00:00:00Z" })
        const { result } = renderHook(() => usePublishForm(), { wrapper: buildWrapper(client) })

        await act(async () => {
            await result.current.mutateAsync("form-1")
        })

        const form = client.getQueryData<FormRead>(formKeys.detail("form-1"))
        expect(form?.status).toBe("published")
        expect(form?.published_schema).toEqual(draftSchema)
        expect(client.getQueryState(formKeys.detail("form-1"))?.isInvalidated).toBe(true)
        client.clear()
    })

    it("stores the saved and published template responses in the template detail cache", async () => {
        const client = buildClient()
        const detailKey = ["platform-templates", "forms", "tpl_form_1"]
        const draft = { name: "Intake", description: null, schema_json: { pages: [] }, settings_json: {} }
        const baseTemplate: PlatformFormTemplate = {
            id: "tpl_form_1",
            status: "published",
            current_version: 1,
            published_version: 1,
            is_published_globally: true,
            draft,
            published: draft,
            updated_at: "2026-09-26T00:00:00Z",
            created_at: "2026-09-20T00:00:00Z",
        }
        const savedTemplate = { ...baseTemplate, status: "draft" as const, current_version: 2, draft: { ...draft, name: "Renamed" } }
        const publishedTemplate = { ...savedTemplate, status: "published" as const, current_version: 3, published_version: 2, published: savedTemplate.draft }
        client.setQueryData(detailKey, baseTemplate)
        updatePlatformFormTemplate.mockResolvedValue(savedTemplate)
        publishPlatformFormTemplate.mockResolvedValue(publishedTemplate)
        const wrapper = buildWrapper(client)
        const { result: update } = renderHook(() => useUpdatePlatformFormTemplate(), { wrapper })
        const { result: publish } = renderHook(() => usePublishPlatformFormTemplate(), { wrapper })

        await act(async () => {
            await update.current.mutateAsync({ id: "tpl_form_1", payload: { name: "Renamed", expected_version: 1 } })
        })
        expect(client.getQueryData(detailKey)).toEqual(savedTemplate)

        await act(async () => {
            await publish.current.mutateAsync({
                id: "tpl_form_1",
                payload: { publish_all: true, org_ids: null, expected_version: 2 },
            })
        })
        expect(client.getQueryData(detailKey)).toEqual(publishedTemplate)
        client.clear()
    })
})

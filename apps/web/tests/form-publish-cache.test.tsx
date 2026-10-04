import { act, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { PropsWithChildren } from "react"
import { describe, expect, it, vi } from "vitest"

import type { FormRead, FormRoutingRead, FormSchema } from "@/lib/api/forms"
import type { PlatformFormTemplate } from "@/lib/api/platform"
import {
    formKeys,
    useForm,
    useFormRouting,
    usePublishForm,
    useSetDefaultSurrogateApplicationForm,
    useUpdateForm,
    useUpdateFormRouting,
} from "@/lib/hooks/use-forms"
import {
    usePlatformFormTemplate,
    usePublishPlatformFormTemplate,
    useUpdatePlatformFormTemplate,
} from "@/lib/hooks/use-platform-templates"

const {
    getForm,
    getFormRouting,
    getPlatformFormTemplate,
    publishForm,
    publishPlatformFormTemplate,
    setDefaultSurrogateApplicationForm,
    updateForm,
    updateFormRouting,
    updatePlatformFormTemplate,
} = vi.hoisted(() => ({
    getForm: vi.fn(),
    getFormRouting: vi.fn(),
    getPlatformFormTemplate: vi.fn(),
    publishForm: vi.fn(),
    publishPlatformFormTemplate: vi.fn(),
    setDefaultSurrogateApplicationForm: vi.fn(),
    updateForm: vi.fn(),
    updateFormRouting: vi.fn(),
    updatePlatformFormTemplate: vi.fn(),
}))

vi.mock("@/lib/api/forms", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/forms")>()),
    getForm,
    getFormRouting,
    publishForm,
    setDefaultSurrogateApplicationForm,
    updateForm,
    updateFormRouting,
}))

vi.mock("@/lib/api/platform", async (importOriginal) => ({
    ...(await importOriginal<typeof import("@/lib/api/platform")>()),
    getPlatformFormTemplate,
    publishPlatformFormTemplate,
    updatePlatformFormTemplate,
}))

const liveSchema: FormSchema = { pages: [{ title: "Application", fields: [] }], public_title: "Apply today" }
const draftSchema: FormSchema = { ...liveSchema, public_title: "Apply now" }

const buildForm = (overrides: Partial<FormRead> = {}): FormRead => ({
    id: "form-1",
    name: "Surrogate Application",
    status: "published",
    purpose: "surrogate_application",
    lead_kind: "surrogate",
    created_at: "2026-09-20T00:00:00Z",
    updated_at: "2026-09-26T00:00:00Z",
    description: null,
    form_schema: liveSchema,
    published_schema: liveSchema,
    max_file_size_bytes: 10 * 1024 * 1024,
    max_file_count: 10,
    allowed_mime_types: null,
    default_application_email_template_id: null,
    ...overrides,
})

// Holds a GET open so the test can resolve it after a save or publish has finished.
function deferStaleResponse<T>(mock: ReturnType<typeof vi.fn>, staleValue: T) {
    let release = () => {}
    mock.mockImplementationOnce(
        () => new Promise<T>((resolve) => {
            release = () => resolve(staleValue)
        }),
    )
    return async () => {
        await act(async () => {
            release()
            await new Promise((resolve) => setTimeout(resolve, 0))
        })
    }
}

const buildClient = () =>
    new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })

const buildWrapper = (client: QueryClient) =>
    function Wrapper({ children }: PropsWithChildren) {
        return <QueryClientProvider client={client}>{children}</QueryClientProvider>
    }

describe("form publish cache", () => {
    it("marks the saved draft schema as live after publishing a form", async () => {
        const client = buildClient()
        client.setQueryData(formKeys.detail("form-1"), buildForm({ form_schema: draftSchema }))
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

    it("keeps a saved draft when an older form detail request resolves after the save", async () => {
        const client = buildClient()
        client.setQueryData(formKeys.detail("form-1"), buildForm())
        const releaseStaleGet = deferStaleResponse(getForm, buildForm())
        getForm.mockResolvedValue(buildForm({ form_schema: draftSchema }))
        updateForm.mockResolvedValue(buildForm({ form_schema: draftSchema }))
        const { result } = renderHook(
            () => ({ form: useForm("form-1"), update: useUpdateForm() }),
            { wrapper: buildWrapper(client) },
        )
        await waitFor(() => expect(getForm).toHaveBeenCalledTimes(1))

        await act(async () => {
            await result.current.update.mutateAsync({ formId: "form-1", payload: { form_schema: draftSchema } })
        })
        await releaseStaleGet()

        const form = client.getQueryData<FormRead>(formKeys.detail("form-1"))
        expect(form?.form_schema).toEqual(draftSchema)
        expect(form?.published_schema).toEqual(liveSchema)
        client.clear()
    })

    it("keeps saved routing when an older routing request resolves after the save", async () => {
        const client = buildClient()
        const staleRouting: FormRoutingRead = {
            form_id: "form-1",
            lead_kind: "surrogate",
            exact_match: "review",
            no_match: "review",
            lead_source: null,
            auto_create_donor: false,
            updated_at: "2026-10-01T00:00:00Z",
        }
        const savedRouting: FormRoutingRead = {
            ...staleRouting,
            exact_match: "auto",
            no_match: "off",
            updated_at: "2026-10-02T00:00:00Z",
        }
        const releaseStaleGet = deferStaleResponse(getFormRouting, staleRouting)
        updateFormRouting.mockResolvedValue(savedRouting)
        const { result } = renderHook(
            () => ({ routing: useFormRouting("form-1"), update: useUpdateFormRouting() }),
            { wrapper: buildWrapper(client) },
        )
        await waitFor(() => expect(getFormRouting).toHaveBeenCalledTimes(1))

        await act(async () => {
            await result.current.update.mutateAsync({
                formId: "form-1",
                payload: { exact_match: "auto", no_match: "off", lead_source: null, auto_create_donor: false },
            })
        })
        await releaseStaleGet()

        expect(client.getQueryData(formKeys.routing("form-1"))).toEqual(savedRouting)
        expect(result.current.routing.data).toEqual(savedRouting)
        client.clear()
    })

    describe("after the detail observer unmounts", () => {
        // The observer starts a detail request and unmounts while it is still open, so
        // invalidation after the mutation neither refetches nor cancels that request.
        async function startUnobservedDetailRequest<T>(
            client: QueryClient,
            useDetail: () => unknown,
            fetchDetail: ReturnType<typeof vi.fn>,
            staleValue: T,
        ) {
            const releaseStaleGet = deferStaleResponse(fetchDetail, staleValue)
            const observer = renderHook(useDetail, { wrapper: buildWrapper(client) })
            await waitFor(() => expect(fetchDetail).toHaveBeenCalledTimes(1))
            observer.unmount()
            return releaseStaleGet
        }

        const templateDraft = { name: "Intake", description: null, schema_json: { pages: [] }, settings_json: {} }
        const baseTemplate: PlatformFormTemplate = {
            id: "tpl_form_1",
            status: "published",
            current_version: 1,
            published_version: 1,
            is_published_globally: true,
            draft: templateDraft,
            published: templateDraft,
            updated_at: "2026-09-26T00:00:00Z",
            created_at: "2026-09-20T00:00:00Z",
        }
        const savedTemplate: PlatformFormTemplate = {
            ...baseTemplate,
            status: "draft",
            current_version: 2,
            draft: { ...templateDraft, name: "Renamed" },
        }
        const publishedTemplate: PlatformFormTemplate = {
            ...savedTemplate,
            status: "published",
            current_version: 3,
            published_version: 2,
            published: savedTemplate.draft,
        }
        const templateDetailKey = ["platform-templates", "forms", "tpl_form_1"]

        it("keeps a published form", async () => {
            const client = buildClient()
            const savedForm = buildForm({ form_schema: draftSchema })
            client.setQueryData(formKeys.detail("form-1"), savedForm)
            const releaseStaleGet = await startUnobservedDetailRequest(client, () => useForm("form-1"), getForm, savedForm)
            publishForm.mockResolvedValue({ id: "form-1", status: "published", published_at: "2026-09-27T00:00:00Z" })
            const { result } = renderHook(() => usePublishForm(), { wrapper: buildWrapper(client) })

            await act(async () => {
                await result.current.mutateAsync("form-1")
            })
            await releaseStaleGet()

            expect(client.getQueryData<FormRead>(formKeys.detail("form-1"))?.published_schema).toEqual(draftSchema)
            client.clear()
        })

        it("keeps the default application form flag", async () => {
            const client = buildClient()
            client.setQueryData(formKeys.detail("form-1"), buildForm())
            const releaseStaleGet = await startUnobservedDetailRequest(client, () => useForm("form-1"), getForm, buildForm())
            setDefaultSurrogateApplicationForm.mockResolvedValue(buildForm({ is_default_surrogate_application: true }))
            const { result } = renderHook(() => useSetDefaultSurrogateApplicationForm(), { wrapper: buildWrapper(client) })

            await act(async () => {
                await result.current.mutateAsync("form-1")
            })
            await releaseStaleGet()

            expect(client.getQueryData<FormRead>(formKeys.detail("form-1"))?.is_default_surrogate_application).toBe(true)
            client.clear()
        })

        it("keeps a saved template", async () => {
            const client = buildClient()
            client.setQueryData(templateDetailKey, baseTemplate)
            const releaseStaleGet = await startUnobservedDetailRequest(
                client,
                () => usePlatformFormTemplate("tpl_form_1"),
                getPlatformFormTemplate,
                baseTemplate,
            )
            updatePlatformFormTemplate.mockResolvedValue(savedTemplate)
            const { result } = renderHook(() => useUpdatePlatformFormTemplate(), { wrapper: buildWrapper(client) })

            await act(async () => {
                await result.current.mutateAsync({ id: "tpl_form_1", payload: { name: "Renamed", expected_version: 1 } })
            })
            await releaseStaleGet()

            expect(client.getQueryData(templateDetailKey)).toEqual(savedTemplate)
            client.clear()
        })

        it("keeps a published template", async () => {
            const client = buildClient()
            client.setQueryData(templateDetailKey, savedTemplate)
            const releaseStaleGet = await startUnobservedDetailRequest(
                client,
                () => usePlatformFormTemplate("tpl_form_1"),
                getPlatformFormTemplate,
                savedTemplate,
            )
            publishPlatformFormTemplate.mockResolvedValue(publishedTemplate)
            const { result } = renderHook(() => usePublishPlatformFormTemplate(), { wrapper: buildWrapper(client) })

            await act(async () => {
                await result.current.mutateAsync({
                    id: "tpl_form_1",
                    payload: { publish_all: true, org_ids: null, expected_version: 2 },
                })
            })
            await releaseStaleGet()

            expect(client.getQueryData(templateDetailKey)).toEqual(publishedTemplate)
            client.clear()
        })
    })
})

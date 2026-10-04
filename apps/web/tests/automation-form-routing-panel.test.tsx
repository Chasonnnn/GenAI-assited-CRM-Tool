import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { useQueryClient, type QueryClient } from "@tanstack/react-query"
import type { ReactNode } from "react"

import { ApiError } from "@/lib/api"
import type { FormRoutingRead, FormWorkflowSummary } from "@/lib/api/forms"
import { getRoutingLeadSourceLabel, getRoutingReviewStepLabel } from "@/lib/forms/form-routing"
import { formKeys } from "@/lib/hooks/use-forms"
import { expectStackedTableSemantics } from "./fixtures/stacked-table"

const { getFormRoutingMock, updateFormRoutingMock, listFormWorkflowsMock, toastMock } = vi.hoisted(() => ({
    getFormRoutingMock: vi.fn(),
    updateFormRoutingMock: vi.fn(),
    listFormWorkflowsMock: vi.fn(),
    toastMock: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("@/lib/api/forms", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/forms")>("@/lib/api/forms")
    return {
        ...actual,
        getFormRouting: getFormRoutingMock,
        updateFormRouting: updateFormRoutingMock,
        listFormWorkflows: listFormWorkflowsMock,
    }
})

vi.mock("@/components/ui/toast", () => ({ toast: toastMock }))

import { AutomationFormRoutingPanel } from "@/components/forms/builder/AutomationFormRoutingPanel"

const SURROGATE_ROUTING: FormRoutingRead = {
    form_id: "form-1",
    lead_kind: "surrogate",
    exact_match: "review",
    no_match: "review",
    lead_source: null,
    auto_create_donor: false,
    updated_at: "2026-10-02T12:00:00Z",
}

const DONOR_ROUTING: FormRoutingRead = {
    form_id: "form-1",
    lead_kind: "egg_donor",
    exact_match: "auto",
    no_match: "auto",
    lead_source: "website",
    auto_create_donor: true,
    updated_at: "2026-10-02T12:00:00Z",
}

const WORKFLOWS: FormWorkflowSummary[] = [
    { id: "wf-1", name: "Notify intake coordinators", trigger_type: "form_submitted", is_enabled: true, scope: "org" },
    { id: "wf-2", name: "Alert owner on rejection", trigger_type: "form_submission_rejected", is_enabled: false, scope: "org" },
]

function renderPanel(props: Partial<Parameters<typeof AutomationFormRoutingPanel>[0]> = {}) {
    return render(<AutomationFormRoutingPanel formId="form-1" canEdit canCreateWorkflows {...props} />)
}

/** Renders the panel and returns a refetch that serves `next` as the server's routing. */
function renderPanelWithRefetch() {
    let client: QueryClient | undefined
    function CaptureClient({ children }: { children: ReactNode }) {
        client = useQueryClient()
        return children
    }
    render(<AutomationFormRoutingPanel formId="form-1" canEdit canCreateWorkflows />, { wrapper: CaptureClient })
    return async (next: FormRoutingRead) => {
        getFormRoutingMock.mockResolvedValue(next)
        await act(async () => {
            await client?.refetchQueries({ queryKey: formKeys.routing("form-1"), exact: true })
            // Query observers notify on the next tick.
            await new Promise((resolve) => setTimeout(resolve, 0))
        })
    }
}

function chooseBaseUiOption(trigger: HTMLElement, optionName: string) {
    fireEvent.click(trigger)
    const option = screen.getByRole("option", { name: optionName })
    fireEvent.mouseMove(option)
    fireEvent.click(option)
}

const exactMatchGroup = () => screen.getByRole("radiogroup", { name: "One exact match" })
const noMatchGroup = () => screen.getByRole("radiogroup", { name: "Create intake lead" })
const leadSourceSelect = () => screen.getByRole("combobox", { name: "Lead source" })
const saveButton = () => screen.getByRole("button", { name: "Save routing" })

describe("routing label helpers", () => {
    it("maps the lead source sentinel and null to Default and never shows a raw value", () => {
        expect(getRoutingLeadSourceLabel(null)).toBe("Default")
        expect(getRoutingLeadSourceLabel("default")).toBe("Default")
        expect(getRoutingLeadSourceLabel("website")).toBe("Website")
        expect(getRoutingLeadSourceLabel("form_embed")).toBe("Form embed")
        expect(getRoutingLeadSourceLabel("future_source")).toBe("Unknown source")
    })

    it("labels each review step", () => {
        expect(getRoutingReviewStepLabel("match")).toBe("Match check")
        expect(getRoutingReviewStepLabel("create_lead")).toBe("No match")
        expect(getRoutingReviewStepLabel(null)).toBe("Routing review")
    })
})

describe("AutomationFormRoutingPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        getFormRoutingMock.mockResolvedValue(SURROGATE_ROUTING)
        listFormWorkflowsMock.mockResolvedValue(WORKFLOWS)
    })

    it("shows loading, then the saved surrogate routing with Default lead source", async () => {
        renderPanel()

        expect(screen.getByText("Loading routing…")).toBeInTheDocument()
        expect(await screen.findByRole("heading", { name: "Routing" })).toBeInTheDocument()
        expect(getFormRoutingMock).toHaveBeenCalledWith("form-1")
        expect(within(exactMatchGroup()).getByRole("radio", { name: "Review first" })).toHaveAttribute("aria-checked", "true")
        expect(within(noMatchGroup()).getByRole("radio", { name: "After review" })).toHaveAttribute("aria-checked", "true")
        expect(screen.getByText("Ambiguous match queue")).toBeInTheDocument()
        expect(leadSourceSelect()).toHaveTextContent("Default")
        expect(screen.queryByRole("switch", { name: "Create donor when photo scan passes" })).not.toBeInTheDocument()
        expect(saveButton()).toBeDisabled()
    })

    it("uses radio semantics with the tab stop on the selected segment", async () => {
        renderPanel()
        await screen.findByRole("heading", { name: "Routing" })

        const automatically = within(noMatchGroup()).getByRole("radio", { name: "Automatically" })
        const afterReview = within(noMatchGroup()).getByRole("radio", { name: "After review" })
        const off = within(noMatchGroup()).getByRole("radio", { name: "Off" })
        expect(afterReview).toHaveAttribute("tabindex", "0")
        expect(automatically).toHaveAttribute("tabindex", "-1")
        expect(off).toHaveAttribute("tabindex", "-1")

        afterReview.focus()
        fireEvent.keyDown(afterReview, { key: "ArrowRight" })
        await waitFor(() => expect(off).toHaveFocus())
        expect(off).toHaveAttribute("aria-checked", "true")
        expect(off).toHaveAttribute("tabindex", "0")

        fireEvent.keyDown(off, { key: "ArrowLeft" })
        await waitFor(() => expect(afterReview).toHaveFocus())
        fireEvent.keyDown(afterReview, { key: "ArrowLeft" })
        await waitFor(() => expect(automatically).toHaveFocus())
        expect(automatically).toHaveAttribute("aria-checked", "true")

        fireEvent.click(automatically)
        expect(automatically).toHaveAttribute("aria-checked", "true")

        fireEvent.keyDown(off, { key: " " })
        fireEvent.keyUp(off, { key: " " })
        expect(off).toHaveAttribute("aria-checked", "true")

        fireEvent.keyDown(afterReview, { key: "Enter" })
        expect(afterReview).toHaveAttribute("aria-checked", "true")
        expect(saveButton()).toBeDisabled()
    })

    it("saves edited routing and reports success", async () => {
        updateFormRoutingMock.mockImplementation(async (_formId: string, payload: object) => ({
            ...SURROGATE_ROUTING,
            ...payload,
        }))
        renderPanel()
        await screen.findByRole("heading", { name: "Routing" })

        fireEvent.click(within(exactMatchGroup()).getByRole("radio", { name: "Link automatically" }))
        fireEvent.click(within(noMatchGroup()).getByRole("radio", { name: "Off" }))
        chooseBaseUiOption(leadSourceSelect(), "Form embed")
        expect(leadSourceSelect()).toHaveTextContent("Form embed")
        fireEvent.click(saveButton())

        await waitFor(() =>
            expect(updateFormRoutingMock).toHaveBeenCalledWith("form-1", {
                exact_match: "auto",
                no_match: "off",
                lead_source: "form_embed",
                auto_create_donor: false,
            }),
        )
        await waitFor(() => expect(toastMock.success).toHaveBeenCalledWith("Routing saved"))
        await waitFor(() => expect(saveButton()).toBeDisabled())
        expect(within(noMatchGroup()).getByRole("radio", { name: "Off" })).toHaveAttribute("aria-checked", "true")
    })

    it("sends Default back as a null lead source", async () => {
        getFormRoutingMock.mockResolvedValue({ ...SURROGATE_ROUTING, lead_source: "website" })
        updateFormRoutingMock.mockResolvedValue(SURROGATE_ROUTING)
        renderPanel()
        await screen.findByRole("heading", { name: "Routing" })

        expect(leadSourceSelect()).toHaveTextContent("Website")
        chooseBaseUiOption(leadSourceSelect(), "Default")
        fireEvent.click(saveButton())

        await waitFor(() =>
            expect(updateFormRoutingMock).toHaveBeenCalledWith("form-1", expect.objectContaining({ lead_source: null })),
        )
    })

    it("shows the API message when saving is forbidden and keeps the draft", async () => {
        updateFormRoutingMock.mockRejectedValue(
            new ApiError(403, "Forbidden", "Creating surrogates automatically needs the Create Surrogates permission"),
        )
        renderPanel()
        await screen.findByRole("heading", { name: "Routing" })

        fireEvent.click(within(exactMatchGroup()).getByRole("radio", { name: "Link automatically" }))
        fireEvent.click(saveButton())

        await waitFor(() =>
            expect(toastMock.error).toHaveBeenCalledWith(
                "Creating surrogates automatically needs the Create Surrogates permission",
            ),
        )
        expect(within(exactMatchGroup()).getByRole("radio", { name: "Link automatically" })).toHaveAttribute(
            "aria-checked",
            "true",
        )
        expect(saveButton()).toBeEnabled()
    })

    it("offers the photo scan switch only on donor forms and saves it", async () => {
        getFormRoutingMock.mockResolvedValue(DONOR_ROUTING)
        updateFormRoutingMock.mockImplementation(async (_formId: string, payload: object) => ({ ...DONOR_ROUTING, ...payload }))
        renderPanel()
        await screen.findByRole("heading", { name: "Routing" })

        const donorSwitch = screen.getByRole("switch", { name: "Create donor when photo scan passes" })
        expect(donorSwitch).toBeChecked()
        expect(leadSourceSelect()).toHaveTextContent("Website")
        fireEvent.click(donorSwitch)
        fireEvent.click(saveButton())

        await waitFor(() =>
            expect(updateFormRoutingMock).toHaveBeenCalledWith("form-1", {
                exact_match: "auto",
                no_match: "auto",
                lead_source: "website",
                auto_create_donor: false,
            }),
        )
    })

    it("is read-only without edit access", async () => {
        getFormRoutingMock.mockResolvedValue(DONOR_ROUTING)
        renderPanel({ canEdit: false })
        await screen.findByRole("heading", { name: "Routing" })

        expect(screen.getByText("Read-only")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Save routing" })).not.toBeInTheDocument()
        for (const group of [exactMatchGroup(), noMatchGroup()]) {
            expect(group).toHaveAttribute("aria-disabled", "true")
            for (const radio of within(group).getAllByRole("radio")) expect(radio).toHaveAttribute("aria-disabled", "true")
        }
        // Every way to pick an unselected segment leaves the saved selection.
        const cases = [
            { group: exactMatchGroup, selected: "Link automatically", other: "Review first" },
            { group: noMatchGroup, selected: "Automatically", other: "Off" },
        ]
        for (const { group, selected, other } of cases) {
            const selectedRadio = within(group()).getByRole("radio", { name: selected })
            const otherRadio = within(group()).getByRole("radio", { name: other })
            fireEvent.click(otherRadio)
            fireEvent.keyDown(otherRadio, { key: "Enter" })
            fireEvent.keyDown(otherRadio, { key: " " })
            fireEvent.keyUp(otherRadio, { key: " " })
            selectedRadio.focus()
            fireEvent.keyDown(selectedRadio, { key: "ArrowRight" })
            fireEvent.keyDown(selectedRadio, { key: "ArrowLeft" })
            await waitFor(() => expect(selectedRadio).toHaveAttribute("aria-checked", "true"))
            expect(otherRadio).toHaveAttribute("aria-checked", "false")
        }
        expect(leadSourceSelect()).toHaveAttribute("data-disabled")
        expect(screen.getByRole("switch", { name: "Create donor when photo scan passes" })).toHaveAttribute("data-disabled")
    })

    it("shows a server change after an edit is reverted", async () => {
        const refetchRouting = renderPanelWithRefetch()
        await screen.findByRole("heading", { name: "Routing" })

        fireEvent.click(within(noMatchGroup()).getByRole("radio", { name: "Automatically" }))
        expect(saveButton()).toBeEnabled()
        fireEvent.click(within(noMatchGroup()).getByRole("radio", { name: "After review" }))
        expect(saveButton()).toBeDisabled()

        await refetchRouting({ ...SURROGATE_ROUTING, no_match: "off", updated_at: "2026-10-02T13:00:00Z" })

        expect(within(noMatchGroup()).getByRole("radio", { name: "Off" })).toHaveAttribute("aria-checked", "true")
        expect(saveButton()).toBeDisabled()
    })

    it("clears an edit once the server holds the same value", async () => {
        const refetchRouting = renderPanelWithRefetch()
        await screen.findByRole("heading", { name: "Routing" })

        fireEvent.click(within(noMatchGroup()).getByRole("radio", { name: "Off" }))
        await refetchRouting({ ...SURROGATE_ROUTING, no_match: "off", updated_at: "2026-10-02T13:00:00Z" })
        expect(saveButton()).toBeDisabled()

        await refetchRouting({ ...SURROGATE_ROUTING, no_match: "auto", updated_at: "2026-10-02T14:00:00Z" })
        expect(within(noMatchGroup()).getByRole("radio", { name: "Automatically" })).toHaveAttribute("aria-checked", "true")
        expect(saveButton()).toBeDisabled()
    })

    it("keeps an unsaved edit across a refetch and saves it with the server's other changes", async () => {
        updateFormRoutingMock.mockImplementation(async (_formId: string, payload: object) => ({
            ...SURROGATE_ROUTING,
            ...payload,
        }))
        const refetchRouting = renderPanelWithRefetch()
        await screen.findByRole("heading", { name: "Routing" })

        fireEvent.click(within(exactMatchGroup()).getByRole("radio", { name: "Link automatically" }))
        await refetchRouting({ ...SURROGATE_ROUTING, no_match: "off", updated_at: "2026-10-02T13:00:00Z" })

        expect(within(exactMatchGroup()).getByRole("radio", { name: "Link automatically" })).toHaveAttribute("aria-checked", "true")
        expect(within(noMatchGroup()).getByRole("radio", { name: "Off" })).toHaveAttribute("aria-checked", "true")
        fireEvent.click(saveButton())

        await waitFor(() =>
            expect(updateFormRoutingMock).toHaveBeenCalledWith("form-1", {
                exact_match: "auto",
                no_match: "off",
                lead_source: null,
                auto_create_donor: false,
            }),
        )
    })

    it("drops unsaved edits when the form's lead kind changes", async () => {
        const refetchRouting = renderPanelWithRefetch()
        await screen.findByRole("heading", { name: "Routing" })

        fireEvent.click(within(exactMatchGroup()).getByRole("radio", { name: "Link automatically" }))
        expect(saveButton()).toBeEnabled()

        await refetchRouting({ ...DONOR_ROUTING, exact_match: "review" })

        expect(within(exactMatchGroup()).getByRole("radio", { name: "Review first" })).toHaveAttribute("aria-checked", "true")
        expect(screen.getByRole("switch", { name: "Create donor when photo scan passes" })).toBeChecked()
        expect(saveButton()).toBeDisabled()
    })

    it("renders a retryable error when routing fails to load", async () => {
        getFormRoutingMock.mockRejectedValueOnce(new ApiError(500, "Server Error", "boom")).mockResolvedValueOnce(SURROGATE_ROUTING)
        renderPanel()

        expect(await screen.findByText("Couldn't load routing")).toBeInTheDocument()
        expect(screen.queryByText("boom")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(await screen.findByRole("heading", { name: "Routing" })).toBeInTheDocument()
    })

    it("lists the form's workflows with trigger labels, status and links", async () => {
        renderPanel()

        const table = await screen.findByRole("table")
        const rows = within(table).getAllByRole("row").slice(1)
        expect(rows).toHaveLength(2)
        expect(rows[0]).toHaveTextContent("Notify intake coordinators")
        expect(rows[0]).toHaveTextContent("Application Submitted")
        expect(rows[0]).toHaveTextContent("Active")
        expect(rows[1]).toHaveTextContent("Application Rejected")
        expect(rows[1]).toHaveTextContent("Paused")
        expect(screen.getByRole("link", { name: "Open Notify intake coordinators" })).toHaveAttribute(
            "href",
            "/automation/workflows/wf-1",
        )
    })

    it("keeps the workflow column headers exposed when rows stack below sm", async () => {
        renderPanel()

        expectStackedTableSemantics(await screen.findByRole("table"), ["Name", "Trigger", "Status", "Actions"])
        expect(within(screen.getByRole("table")).getAllByRole("cell")).toHaveLength(8)
    })

    it("opens a new org workflow with the trigger and form preselected", async () => {
        renderPanel()
        await screen.findByRole("table")

        fireEvent.click(screen.getByRole("button", { name: "New workflow" }))
        expect(await screen.findByRole("menuitem", { name: "Application Submitted" })).toHaveAttribute(
            "href",
            "/automation/workflows/new?scope=org&trigger=form_submitted&form_id=form-1",
        )
        expect(screen.getByRole("menuitem", { name: "Application Approved" })).toHaveAttribute(
            "href",
            "/automation/workflows/new?scope=org&trigger=form_submission_approved&form_id=form-1",
        )
        expect(screen.getByRole("menuitem", { name: "Application Rejected" })).toHaveAttribute(
            "href",
            "/automation/workflows/new?scope=org&trigger=form_submission_rejected&form_id=form-1",
        )
    })

    it("hides New workflow without org workflow access and shows empty and error states", async () => {
        listFormWorkflowsMock.mockResolvedValueOnce([])
        const { unmount } = renderPanel({ canCreateWorkflows: false })
        expect(await screen.findByText("No workflows for this form.")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "New workflow" })).not.toBeInTheDocument()
        unmount()

        listFormWorkflowsMock.mockRejectedValueOnce(new ApiError(500, "Server Error", "boom")).mockResolvedValueOnce(WORKFLOWS)
        renderPanel()
        expect(await screen.findByText("Unable to load workflows.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByRole("table")).toBeInTheDocument()
    })

    it("asks for a saved form before routing can be configured", () => {
        renderPanel({ formId: null })

        expect(screen.getByText("Save the form before configuring routing.")).toBeInTheDocument()
        expect(getFormRoutingMock).not.toHaveBeenCalled()
    })
})

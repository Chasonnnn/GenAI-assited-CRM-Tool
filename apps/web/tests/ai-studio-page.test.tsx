import { readFileSync } from "node:fs"

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react"
import AIStudioPage from "../app/(app)/ai-studio/page"

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockGenerate = vi.fn()
const mockSaveDraft = vi.fn()
const mockUpdateSettings = vi.fn()

const generatedDraft = {
    id: "draft-1",
    status: "preview",
    platform: "instagram",
    format: "feed",
    tone: "warm",
    audience: "intended parents",
    brief: "Launch announcement",
    caption: "A thoughtful caption for intended parents.",
    hashtags: ["#SurrogacyForce", "#FamilyBuilding"],
    image_prompt: "A calm editorial image",
    image_url: "https://api.test/ai/studio/assets/ai-studio/test/image.png",
    image_revised_prompt: "A revised calm editorial image",
    image_size: "auto",
    image_quality: "auto",
    reference_images: [],
    reasoning_model: "gpt-5.5",
    image_model: "gpt-image-2",
    created_at: "2026-05-09T12:00:00Z",
    updated_at: "2026-05-09T12:00:00Z",
}

let studioSettings = {
    has_api_key: true,
    api_key_masked: "sk-s...1234",
    agents_md: "Studio agents",
    skills_md: "Studio skills",
    reasoning_model: "gpt-5.5",
    image_model: "gpt-image-2",
}

let studioDrafts = { items: [] as typeof generatedDraft[] }

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock("@/lib/hooks/use-ai-studio", () => ({
    useAIStudioSettings: () => ({ data: studioSettings, isLoading: false }),
    useUpdateAIStudioSettings: () => ({ mutateAsync: mockUpdateSettings, isPending: false }),
    useGenerateAIStudioDraft: () => ({ mutateAsync: mockGenerate, isPending: false }),
    useSaveAIStudioDraft: () => ({ mutateAsync: mockSaveDraft, isPending: false }),
    useAIStudioDrafts: () => ({ data: studioDrafts, isLoading: false }),
}))

describe("AIStudioPage", () => {
    beforeEach(() => {
        studioSettings = {
            has_api_key: true,
            api_key_masked: "sk-s...1234",
            agents_md: "Studio agents",
            skills_md: "Studio skills",
            reasoning_model: "gpt-5.5",
            image_model: "gpt-image-2",
        }
        studioDrafts = { items: [] }
        mockUseAuth.mockReturnValue({ user: { ai_enabled: true, user_id: "user-1" } })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["use_ai_assistant", "manage_ai_settings"] },
        })
        mockGenerate.mockReset()
        mockSaveDraft.mockReset()
        mockUpdateSettings.mockReset()
    })

    it("shows a key configuration state when OpenAI is not connected", () => {
        studioSettings = { ...studioSettings, has_api_key: false, api_key_masked: null }

        render(<AIStudioPage />)

        expect(screen.getByRole("heading", { name: "AI Studio Preview" })).toBeInTheDocument()
        expect(screen.getByText("Connect OpenAI")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /studio settings/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /generate draft/i })).toBeDisabled()
        expect(screen.getByText("Size")).toBeInTheDocument()
        expect(screen.getByText("Quality")).toBeInTheDocument()
    })

    it("marks decorative AI Studio icons as hidden from assistive tech", () => {
        const source = readFileSync("app/(app)/ai-studio/page.tsx", "utf8")

        for (const expected of [
            "<ImageIcon aria-hidden=\"true\" />",
            "<Spinner data-icon=\"inline-start\" aria-hidden=\"true\" />",
            "<SaveIcon data-icon=\"inline-start\" aria-hidden=\"true\" />",
            "<RefreshCwIcon data-icon=\"inline-start\" aria-hidden=\"true\" />",
            "<XIcon aria-hidden=\"true\" />",
            "<PaperclipIcon aria-hidden=\"true\" />",
            "<Settings2Icon data-icon=\"inline-start\" aria-hidden=\"true\" />",
            "<AlertCircleIcon aria-hidden=\"true\" />",
            "<SparklesIcon data-icon=\"inline-start\" aria-hidden=\"true\" />",
            "<CheckIcon className=\"size-4\" aria-hidden=\"true\" />",
        ]) {
            expect(source).toContain(expected)
        }
    })

    it("generates a preview and saves the draft", async () => {
        mockGenerate.mockResolvedValue(generatedDraft)
        mockSaveDraft.mockResolvedValue({ ...generatedDraft, status: "saved" })

        render(<AIStudioPage />)

        fireEvent.change(screen.getByLabelText(/brief/i), {
            target: { value: "Launch announcement" },
        })
        fireEvent.click(screen.getByRole("button", { name: /generate draft/i }))

        expect(mockGenerate).toHaveBeenCalledWith({
            brief: "Launch announcement",
            platform: "instagram",
            format: "feed",
            tone: "warm",
            audience: "",
            image_size: "auto",
            image_quality: "auto",
            reference_images: [],
        })
        expect(await screen.findByText("A thoughtful caption for intended parents.")).toBeInTheDocument()
        expect(screen.getByAltText("Generated social media visual")).toHaveAttribute(
            "src",
            generatedDraft.image_url,
        )

        fireEvent.click(screen.getByRole("button", { name: /save draft/i }))

        await waitFor(() => {
            expect(mockSaveDraft).toHaveBeenCalledWith("draft-1")
        })
        expect(await screen.findByText("Saved")).toBeInTheDocument()
    })

    it("adds pictures pasted into the brief composer to the generation payload", async () => {
        mockGenerate.mockResolvedValue({
            ...generatedDraft,
            audience: "clinic partners",
            reference_images: [
                { filename: "clinic-reference.png", mime_type: "image/png", size_bytes: 15 },
            ],
        })

        render(<AIStudioPage />)

        expect(screen.queryByText("Sample pictures")).not.toBeInTheDocument()
        expect(screen.queryByTestId("ai-studio-reference-dropzone")).not.toBeInTheDocument()

        const file = new File(["reference-image"], "clinic-reference.png", {
            type: "image/png",
        })
        fireEvent.paste(screen.getByLabelText(/brief/i), {
            clipboardData: { files: [file] },
        })
        expect(await screen.findByAltText("clinic-reference.png")).toBeInTheDocument()

        fireEvent.change(screen.getByLabelText(/brief/i), {
            target: { value: "Campaign announcement" },
        })
        fireEvent.click(screen.getByRole("button", { name: /generate draft/i }))

        await waitFor(() => {
            expect(mockGenerate).toHaveBeenCalled()
        })
        const payload = mockGenerate.mock.calls[0][0]
        expect(payload.audience).toBe("")
        expect(payload.reference_images).toEqual([
            {
                filename: "clinic-reference.png",
                mime_type: "image/png",
                data_base64: "cmVmZXJlbmNlLWltYWdl",
            },
        ])
        expect(await screen.findByText("Audience: clinic partners")).toBeInTheDocument()
    })

    it("keeps saved drafts in the Gallery tab", () => {
        studioDrafts = { items: [{ ...generatedDraft, status: "saved" }] }

        render(<AIStudioPage />)

        expect(screen.queryByText("Saved drafts")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("tab", { name: /gallery/i }))

        expect(screen.getByText("Saved drafts")).toBeInTheDocument()
        fireEvent.click(screen.getByText("Launch announcement"))
        expect(screen.getAllByText("A thoughtful caption for intended parents.").length).toBeGreaterThan(1)
    })

    it("keeps Studio guidance editable behind the settings dialog", async () => {
        mockUpdateSettings.mockResolvedValue({
            ...studioSettings,
            agents_md: "Updated agents",
            skills_md: "Updated skills",
        })

        render(<AIStudioPage />)
        fireEvent.click(screen.getByRole("button", { name: /studio settings/i }))

        const dialog = screen.getByRole("dialog")
        fireEvent.change(within(dialog).getByLabelText(/agents\.md/i), {
            target: { value: "Updated agents" },
        })
        fireEvent.change(within(dialog).getByLabelText(/skills\.md/i), {
            target: { value: "Updated skills" },
        })
        fireEvent.change(within(dialog).getByLabelText(/openai api key/i), {
            target: { value: "sk-updated" },
        })
        fireEvent.click(within(dialog).getByRole("button", { name: /save settings/i }))

        await waitFor(() => {
            expect(mockUpdateSettings).toHaveBeenCalledWith({
                api_key: "sk-updated",
                agents_md: "Updated agents",
                skills_md: "Updated skills",
            })
        })
        await waitFor(() => {
            expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
        })

        fireEvent.click(screen.getByRole("button", { name: /studio settings/i }))

        const reopenedDialog = screen.getByRole("dialog")
        expect(within(reopenedDialog).getByLabelText(/openai api key/i)).toHaveValue("")
        expect(within(reopenedDialog).getByLabelText(/agents\.md/i)).toHaveValue("Studio agents")
    })
})

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
    useAIStudioDrafts: () => ({ data: { items: [] }, isLoading: false }),
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
        fireEvent.click(within(dialog).getByRole("button", { name: /save settings/i }))

        await waitFor(() => {
            expect(mockUpdateSettings).toHaveBeenCalledWith({
                agents_md: "Updated agents",
                skills_md: "Updated skills",
            })
        })
    })
})

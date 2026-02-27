"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2Icon, FileTextIcon } from "lucide-react"
import { ProfileCardProvider, useProfileCardData, useProfileCardEdits, useProfileCardMode, PROFILE_CUSTOM_QAS_KEY, renderProfileTemplate } from "./context"
import { Header } from "./Header"
import { Section } from "./Section"
import { FieldRow } from "./FieldRow"
import { SaveBar } from "./SaveBar"
import type { ProfileCustomQa } from "@/lib/api/profile"

function SectionCustomQas({ sectionKey }: { sectionKey: string }) {
    const { profile } = useProfileCardData()
    const { mode } = useProfileCardMode()
    const { editedFields, setFieldValue } = useProfileCardEdits()
    const isEditMode = mode.type === "edit"
    const raw = editedFields[PROFILE_CUSTOM_QAS_KEY]
    const qas: ProfileCustomQa[] = Array.isArray(raw) ? (raw as ProfileCustomQa[]) : []
    const sectionQas = qas
        .filter((qa) => qa.section_key === sectionKey)
        .sort((a, b) => a.order - b.order)

    const updateQas = (next: ProfileCustomQa[]) => setFieldValue(PROFILE_CUSTOM_QAS_KEY, next)

    const addQa = () => {
        const next = [...qas, {
            id: `qa_${Date.now()}`,
            section_key: sectionKey,
            question: "",
            answer: "",
            order: sectionQas.length,
        }]
        updateQas(next)
    }

    const updateQa = (qaId: string, patch: Partial<ProfileCustomQa>) => {
        updateQas(
            qas.map((qa) => {
                if (qa.id !== qaId) return qa
                return {
                    ...qa,
                    id: patch.id ?? qa.id,
                    section_key: patch.section_key ?? qa.section_key,
                    question: patch.question ?? qa.question,
                    answer: patch.answer ?? qa.answer,
                    order: patch.order ?? qa.order,
                }
            })
        )
    }

    const removeQa = (qaId: string) => {
        const next = qas.filter((qa) => qa.id !== qaId).map((qa, index) => ({ ...qa, order: index }))
        updateQas(next)
    }

    if (!isEditMode && sectionQas.length === 0) {
        return null
    }

    return (
        <div className="space-y-2 pt-2 border-t border-border/40">
            <div className="flex items-center justify-between">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Custom Q&A</p>
                {isEditMode ? (
                    <Button size="sm" variant="outline" className="h-7" onClick={addQa}>
                        Add
                    </Button>
                ) : null}
            </div>
            {sectionQas.map((qa) => (
                <div key={qa.id} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                    {isEditMode ? (
                        <>
                            <Input
                                value={qa.question}
                                onChange={(e) => updateQa(qa.id, { question: e.target.value })}
                                placeholder="Question"
                                className="h-8 text-sm"
                            />
                            <Input
                                value={qa.answer}
                                onChange={(e) => updateQa(qa.id, { answer: e.target.value })}
                                placeholder="Answer"
                                className="h-8 text-sm"
                            />
                            <Button
                                size="sm"
                                variant="ghost"
                                className="h-8"
                                onClick={() => removeQa(qa.id)}
                            >
                                Remove
                            </Button>
                        </>
                    ) : (
                        <div className="col-span-full flex items-center justify-between gap-3 py-1">
                            <span className="text-sm text-muted-foreground">{qa.question || "Question"}</span>
                            <span className="text-sm">
                                {qa.answer ? renderProfileTemplate(qa.answer, profile?.merged_view ?? {}) : "—"}
                            </span>
                        </div>
                    )}
                </div>
            ))}
        </div>
    )
}

// ============================================================================
// Content Component
// ============================================================================

function ProfileCardContent() {
    const { profile, isLoading, error } = useProfileCardData()

    // Loading state
    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-12">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading profile...</span>
                </CardContent>
            </Card>
        )
    }

    // Error state
    if (error) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                    <p className="text-sm text-muted-foreground">Unable to load profile card</p>
                </CardContent>
            </Card>
        )
    }

    // Empty state - no submission
    if (!profile?.base_submission_id) {
        return (
            <Card>
                <Header />
                <CardContent className="flex flex-col items-center justify-center py-8 text-center">
                    <FileTextIcon className="h-12 w-12 text-muted-foreground/50 mb-4" />
                    <p className="text-sm text-muted-foreground">
                        No application submitted yet
                    </p>
                </CardContent>
            </Card>
        )
    }

    const pages = profile.schema_snapshot?.pages || []

    return (
        <Card>
            <Header />
            <CardContent className="space-y-4">
                {pages.map((page, pageIndex) => (
                    <Section
                        key={pageIndex}
                        index={pageIndex}
                        title={page.title || `Section ${pageIndex + 1}`}
                    >
                        {page.fields
                            .filter((f) => f.type !== "file")
                            .map((field) => (
                                <FieldRow
                                    key={field.key}
                                    fieldKey={field.key}
                                    field={field}
                                    mergedValue={profile.merged_view[field.key]}
                                    baseValue={profile.base_answers[field.key]}
                                />
                            ))}
                        <SectionCustomQas sectionKey={`section_${pageIndex}`} />
                    </Section>
                ))}
                <SaveBar />
            </CardContent>
        </Card>
    )
}

// ============================================================================
// Main Export
// ============================================================================

interface ProfileCardProps {
    surrogateId: string
}

export function ProfileCard({ surrogateId }: ProfileCardProps) {
    return (
        <ProfileCardProvider surrogateId={surrogateId}>
            <ProfileCardContent />
        </ProfileCardProvider>
    )
}

// Re-exports
export {
    useProfileCard,
    useProfileCardData,
    useProfileCardMode,
    useProfileCardEdits,
    useProfileCardSections,
    useProfileCardActions,
    type CardMode,
} from "./context"
export type {
    ProfileCardContextValue,
    ProfileCardDataContextValue,
    ProfileCardModeContextValue,
    ProfileCardEditsContextValue,
    ProfileCardSectionsContextValue,
    ProfileCardActionsContextValue,
} from "./context"

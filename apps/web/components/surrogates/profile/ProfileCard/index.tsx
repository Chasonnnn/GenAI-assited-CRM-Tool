"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Loader2Icon, FileTextIcon } from "lucide-react"
import { ProfileCardProvider, useProfileCardData } from "./context"
import { Header } from "./Header"
import { Section } from "./Section"
import { FieldRow } from "./FieldRow"
import { SaveBar } from "./SaveBar"

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

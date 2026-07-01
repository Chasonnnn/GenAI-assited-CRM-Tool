import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { AutomationFormSettingsPanel } from "@/components/forms/builder/AutomationFormSettingsPanel"

describe("AutomationFormSettingsPanel accessibility", () => {
    it("labels the form logo upload input", () => {
        render(
            <AutomationFormSettingsPanel
                formName="Surrogate Application"
                formDescription="Application intake"
                formPurpose="surrogate_application"
                publicEyebrow="Apply"
                publicTitle="Become a surrogate"
                publicSubtitle="Tell us about yourself"
                logoUrl=""
                resolvedLogoUrl=""
                privacyNotice=""
                defaultTemplateId=""
                emailTemplates={[]}
                maxFileSizeMb={10}
                maxFileCount={3}
                allowedMimeTypesText="image/png,image/jpeg"
                useOrgLogo={false}
                orgLogoAvailable
                logoInputRef={React.createRef<HTMLInputElement>()}
                uploadLogoPending={false}
                isDefaultSurrogateApplication={false}
                setDefaultSurrogateApplicationPending={false}
                isPublished
                selectedQrLink={null}
                onFormNameChange={() => undefined}
                onFormDescriptionChange={() => undefined}
                onFormPurposeChange={() => undefined}
                onPublicEyebrowChange={() => undefined}
                onPublicTitleChange={() => undefined}
                onPublicSubtitleChange={() => undefined}
                onLogoUrlChange={() => undefined}
                onPrivacyNoticeChange={() => undefined}
                onDefaultTemplateChange={() => undefined}
                onUseOrgLogoChange={() => undefined}
                onLogoUploadClick={() => undefined}
                onLogoFileChange={vi.fn()}
                onSetDefaultSurrogateApplication={() => undefined}
                onOpenSharePrompt={() => undefined}
                onCopySharedLink={() => undefined}
                onDownloadQrSvg={() => undefined}
                onDownloadQrPng={() => undefined}
                onMaxFileSizeMbChange={() => undefined}
                onMaxFileCountChange={() => undefined}
                onAllowedMimeTypesTextChange={() => undefined}
            />,
        )

        expect(screen.getByLabelText("Upload form logo")).toHaveAttribute("name", "form_logo_upload")
    })
})

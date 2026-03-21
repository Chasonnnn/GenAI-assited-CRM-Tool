"use client"

import { MonitorIcon, SmartphoneIcon } from "lucide-react"

import { FormBuilderCanvasPreview } from "@/components/forms/builder/FormBuilderCanvasPreview"
import { Button } from "@/components/ui/button"
import type { BuilderFormPage } from "@/lib/forms/form-builder-document"

type FormBuilderPreviewPaneProps = {
    pages: BuilderFormPage[]
    activePage: number
    formName: string
    formDescription: string
    publicTitle: string
    resolvedLogoUrl: string
    privacyNotice: string
    previewDevice: "desktop" | "mobile"
    desktopCanvasWidthClass: string
    mobileCanvasWidthClass: string
    onSetActivePage: (pageId: number) => void
    onPreviewDeviceChange: (value: "desktop" | "mobile") => void
}

export function FormBuilderPreviewPane({
    pages,
    activePage,
    formName,
    formDescription,
    publicTitle,
    resolvedLogoUrl,
    privacyNotice,
    previewDevice,
    desktopCanvasWidthClass,
    mobileCanvasWidthClass,
    onSetActivePage,
    onPreviewDeviceChange,
}: FormBuilderPreviewPaneProps) {
    return (
        <div className="flex-1 overflow-y-auto bg-muted/20 p-4 sm:p-6 xl:p-8">
            <div className="mx-auto max-w-6xl space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-4 rounded-[24px] border border-border/70 bg-white/95 p-4">
                    <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                            Preview
                        </p>
                        <h2 className="mt-1 text-lg font-semibold tracking-tight text-foreground">Preview</h2>
                    </div>

                    <div className="flex items-center gap-2">
                        <Button
                            type="button"
                            variant={previewDevice === "desktop" ? "secondary" : "outline"}
                            onClick={() => onPreviewDeviceChange("desktop")}
                        >
                            <MonitorIcon className="mr-2 size-4" />
                            Desktop Preview
                        </Button>
                        <Button
                            type="button"
                            variant={previewDevice === "mobile" ? "secondary" : "outline"}
                            onClick={() => onPreviewDeviceChange("mobile")}
                        >
                            <SmartphoneIcon className="mr-2 size-4" />
                            Mobile Preview
                        </Button>
                    </div>
                </div>

                <FormBuilderCanvasPreview
                    pages={pages}
                    activePage={activePage}
                    formName={formName}
                    formDescription={formDescription}
                    publicTitle={publicTitle}
                    resolvedLogoUrl={resolvedLogoUrl}
                    privacyNotice={privacyNotice}
                    previewDevice={previewDevice}
                    desktopWidthClass={desktopCanvasWidthClass}
                    mobileWidthClass={mobileCanvasWidthClass}
                    onSetActivePage={onSetActivePage}
                />
            </div>
        </div>
    )
}

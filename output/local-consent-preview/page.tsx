"use client"

import { useState } from "react"
import { FormBuilderWorkspace } from "@/components/forms/builder/FormBuilderWorkspace"
import { PublicFormFieldRenderer, type PublicFormAnswerValue } from "@/components/forms/PublicFormFieldRenderer"
import { useFormBuilderDocument } from "@/lib/forms/use-form-builder-document"
import { buildFormSchema, createBuilderField, schemaToPages } from "@/lib/forms/form-builder-document"
import { PRESET_FIELD_GROUPS } from "@/lib/forms/form-builder-library"
import { Button } from "@/components/ui/button"

const preset = PRESET_FIELD_GROUPS.flatMap(group => group.fields).find(field => field.key === "opt_in_consent")!
const initialField = {
    ...createBuilderField(preset),
    id: "consent-preview",
    helperText: "Message frequency varies. Message and data rates may apply. Reply STOP to opt out or HELP for help. [Privacy Notice](https://www.ewisurrogacy.com/priacy-policy)",
}

export default function ConsentPreview() {
    const doc = useFormBuilderDocument([{ id: 1, name: "Consent", fields: [initialField] }])
    const [search, setSearch] = useState("consent")
    const [category, setCategory] = useState("all")
    const [preview, setPreview] = useState(true)
    const [answers, setAnswers] = useState<Record<string, PublicFormAnswerValue>>({})
    const [dates, setDates] = useState<Record<string, boolean>>({})
    const schema = buildFormSchema(doc.pages, { publicEyebrow: "", publicTitle: "Consent", publicSubtitle: "", logoUrl: "", privacyNotice: "" })

    return <main className="min-h-screen bg-background">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
            <h1 className="text-xl font-semibold">Local consent preview</h1>
            <div className="flex gap-2">
                {!preview && <Button variant="outline" onClick={() => doc.resetDocument(schemaToPages(JSON.parse(JSON.stringify(schema)), new Map()))}>Reload preview</Button>}
                <Button onClick={() => setPreview(!preview)}>{preview ? "Edit consent" : "Preview"}</Button>
            </div>
        </div>
        {preview ? <div className="mx-auto max-w-xl space-y-5 p-6">
            {schema.pages.flatMap(page => page.fields).map(field => <PublicFormFieldRenderer key={field.key} field={field} value={answers[field.key]} updateField={(key, value) => setAnswers({ ...answers, [key]: value })} datePickerOpen={dates} setDatePickerOpen={setDates}/>)}
        </div> : <FormBuilderWorkspace leadKind="surrogate" desktopCanvasWidthClass="max-w-3xl" canvasFrameClass="rounded-xl border bg-white p-5" mappingOptions={[]} publicEyebrow="" publicTitle="Consent" publicSubtitle="" fieldLibrarySearch={search} fieldLibraryCategory={category} onFieldLibrarySearchChange={setSearch} onFieldLibraryCategoryChange={setCategory} document={{...doc, requestDeletePage: () => undefined}}/>}
    </main>
}

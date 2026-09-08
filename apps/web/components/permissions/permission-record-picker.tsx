"use client"

import { useId, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { getSurrogates } from "@/lib/api/surrogates"
import { listDonors } from "@/lib/api/donors"
import { listIntendedParents } from "@/lib/api/intended-parents"
import type { RecordKind } from "@/lib/api/record-scopes"
import { ChoiceField, PermissionError } from "./permission-controls"

export interface SelectedPermissionRecord { kind: RecordKind; id: string; label: string }
const ENTITY_LABELS = { surrogate: "Surrogate", egg_donor: "Egg donor", sperm_donor: "Sperm donor", intended_parent: "Intended parent" }

export function PermissionRecordPicker({ value, onChange, collaboratorsOnly = false, disabled = false }: { value: SelectedPermissionRecord | null; onChange: (record: SelectedPermissionRecord | null) => void; collaboratorsOnly?: boolean; disabled?: boolean }) {
    const id = useId()
    const [entity, setEntity] = useState<keyof typeof ENTITY_LABELS>("surrogate")
    const [search, setSearch] = useState("")
    const records = useMutation({ mutationFn: async () => {
        if (entity === "surrogate") return (await getSurrogates({ q: search, per_page: 20, include_archived: true })).items.map((record) => ({ id: record.id, label: `${record.surrogate_number} · ${record.full_name}` }))
        if (entity === "intended_parent") return (await listIntendedParents({ q: search, per_page: 20, include_archived: true })).items.map((record) => ({ id: record.id, label: `${record.intended_parent_number} · ${record.full_name}` }))
        return (await listDonors({ donor_type: entity === "egg_donor" ? "egg" : "sperm", q: search, per_page: 20, include_archived: true })).items.map((record) => ({ id: record.id, label: `${record.donor_number} · ${record.full_name}` }))
    } })
    return <div className="space-y-4">
        <ChoiceField label="Record type" value={entity} options={collaboratorsOnly ? { surrogate: "Surrogate", egg_donor: "Egg donor", sperm_donor: "Sperm donor" } : ENTITY_LABELS} onChange={(next) => { setEntity(next); onChange(null); records.reset() }} disabled={disabled || records.isPending} />
        <div className="flex items-end gap-2"><div className="flex-1 space-y-2"><label htmlFor={id} className="text-sm font-medium">Record name or number</label><Input id={id} value={search} onChange={(event) => setSearch(event.target.value)} disabled={disabled} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); onChange(null); records.mutate() } }} /></div><Button variant="outline" disabled={disabled || records.isPending} onClick={() => { onChange(null); records.mutate() }}>{records.isPending ? "Searching…" : "Search"}</Button></div>
        {records.error && <PermissionError error={records.error} />}
        {records.data && (records.data.length ? <ChoiceField label="Record" value={value?.id ?? ""} options={Object.fromEntries(records.data.map((record) => [record.id, record.label]))} onChange={(recordId) => { const record = records.data.find((item) => item.id === recordId); if (record) onChange({ ...record, kind: entity.endsWith("donor") ? "donor" : entity as RecordKind }) }} disabled={disabled} /> : <p className="text-sm text-muted-foreground">No records found.</p>)}
    </div>
}

"use client"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { DonorFormValues } from "@/components/donors/donor-form-values"
import { US_STATES } from "@/lib/constants/us-states"

export function DonorFormFields({
    values,
    idPrefix,
    showDonorType = true,
    onChange,
}: {
    values: DonorFormValues
    idPrefix: string
    showDonorType?: boolean
    onChange: <K extends keyof DonorFormValues>(field: K, value: DonorFormValues[K]) => void
}) {
    return (
        <div className="grid gap-4 sm:grid-cols-2">
            {showDonorType ? (
                <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor={`${idPrefix}donor_type`}>Donor type</Label>
                    <Select
                        value={values.donor_type}
                        onValueChange={(value) => {
                            if (value === "egg" || value === "sperm") onChange("donor_type", value)
                        }}
                    >
                        <SelectTrigger id={`${idPrefix}donor_type`} className="w-full">
                            <SelectValue>
                                {(value: string | null) => value === "sperm" ? "Sperm Donor" : "Egg Donor"}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="egg">Egg Donor</SelectItem>
                            <SelectItem value="sperm">Sperm Donor</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            ) : null}
            <div className="space-y-2">
                <Label htmlFor={`${idPrefix}full_name`}>Full name</Label>
                <Input
                    id={`${idPrefix}full_name`}
                    autoFocus
                    required
                    value={values.full_name}
                    onChange={(event) => onChange("full_name", event.target.value)}
                />
            </div>
            <div className="space-y-2">
                <Label htmlFor={`${idPrefix}email`}>Email</Label>
                <Input
                    id={`${idPrefix}email`}
                    type="email"
                    required
                    value={values.email}
                    onChange={(event) => onChange("email", event.target.value)}
                />
            </div>
            <div className="space-y-2">
                <Label htmlFor={`${idPrefix}phone`}>Phone</Label>
                <Input
                    id={`${idPrefix}phone`}
                    type="tel"
                    value={values.phone}
                    onChange={(event) => onChange("phone", event.target.value)}
                />
            </div>
            <div className="space-y-2">
                <Label id={`${idPrefix}state_label`} htmlFor={`${idPrefix}state`}>State</Label>
                <Select
                    value={values.state || null}
                    onValueChange={(value) => onChange("state", value ?? "")}
                >
                    <SelectTrigger
                        id={`${idPrefix}state`}
                        aria-labelledby={`${idPrefix}state_label`}
                        className="w-full"
                    >
                        <SelectValue placeholder="Select a state">
                            {(value: string | null) => {
                                const state = US_STATES.find((option) => option.value === value)
                                return state ? `${state.label} (${state.value})` : "Select a state"
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">Select a state</SelectItem>
                        {US_STATES.map((state) => (
                            <SelectItem key={state.value} value={state.value}>
                                {state.label} ({state.value})
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>
            <div className="space-y-2 sm:col-span-2">
                <Label htmlFor={`${idPrefix}education`}>Education</Label>
                <Input
                    id={`${idPrefix}education`}
                    placeholder="Highest level, degree, or field of study"
                    value={values.education}
                    onChange={(event) => onChange("education", event.target.value)}
                />
            </div>
        </div>
    )
}

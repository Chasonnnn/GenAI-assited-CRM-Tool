"use client"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    useSurrogateDetailActions,
    useSurrogateDetailData,
    useSurrogateDetailDialogs,
} from "../context"

export function EditDialog() {
    const { surrogate } = useSurrogateDetailData()
    const { activeDialog, closeDialog } = useSurrogateDetailDialogs()
    const { updateSurrogate, isUpdatePending } = useSurrogateDetailActions()

    const isOpen = activeDialog.type === "edit_surrogate"

    if (!surrogate) return null

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && closeDialog()}>
            <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Edit Surrogate: #{surrogate.surrogate_number}</DialogTitle>
                </DialogHeader>
                <form
                    onSubmit={async (event: React.FormEvent<HTMLFormElement>) => {
                        event.preventDefault()
                        const form = event.currentTarget
                        const formData = new FormData(form)
                        const data: Record<string, unknown> = {}
                        const getString = (key: string) => {
                            const value = formData.get(key)
                            return typeof value === "string" ? value : ""
                        }

                        const fullName = getString("full_name")
                        if (fullName) data.full_name = fullName
                        const email = getString("email")
                        if (email) data.email = email
                        const phone = getString("phone")
                        data.phone = phone || null
                        const state = getString("state")
                        data.state = state || null
                        const dateOfBirth = getString("date_of_birth")
                        data.date_of_birth = dateOfBirth || null
                        const race = getString("race")
                        data.race = race || null

                        const heightFt = getString("height_ft")
                        data.height_ft = heightFt ? parseFloat(heightFt) : null
                        const weightLb = getString("weight_lb")
                        data.weight_lb = weightLb ? parseFloat(weightLb) : null
                        const numDeliveries = getString("num_deliveries")
                        data.num_deliveries = numDeliveries ? parseInt(numDeliveries, 10) : null
                        const numCsections = getString("num_csections")
                        data.num_csections = numCsections ? parseInt(numCsections, 10) : null

                        data.is_age_eligible = formData.get("is_age_eligible") === "on"
                        data.is_citizen_or_pr = formData.get("is_citizen_or_pr") === "on"
                        data.has_child = formData.get("has_child") === "on"
                        data.is_non_smoker = formData.get("is_non_smoker") === "on"
                        data.has_surrogate_experience = formData.get("has_surrogate_experience") === "on"
                        data.is_priority = formData.get("is_priority") === "on"

                        await updateSurrogate(data)
                    }}
                >
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="full_name">Full Name *</Label>
                                <Input id="full_name" name="full_name" defaultValue={surrogate.full_name} required />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="email">Email *</Label>
                                <Input id="email" name="email" type="email" defaultValue={surrogate.email} required />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="phone">Phone</Label>
                                <Input id="phone" name="phone" defaultValue={surrogate.phone ?? ""} />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="state">State</Label>
                                <Input id="state" name="state" defaultValue={surrogate.state ?? ""} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="date_of_birth">Date of Birth</Label>
                                <Input id="date_of_birth" name="date_of_birth" type="date" defaultValue={surrogate.date_of_birth ?? ""} />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="race">Race</Label>
                                <Input id="race" name="race" defaultValue={surrogate.race ?? ""} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="height_ft">Height (ft)</Label>
                                <Input id="height_ft" name="height_ft" type="number" step="0.1" defaultValue={surrogate.height_ft ?? ""} />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="weight_lb">Weight (lb)</Label>
                                <Input id="weight_lb" name="weight_lb" type="number" defaultValue={surrogate.weight_lb ?? ""} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="num_deliveries">Number of Deliveries</Label>
                                <Input id="num_deliveries" name="num_deliveries" type="number" min="0" max="20" defaultValue={surrogate.num_deliveries ?? ""} />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="num_csections">Number of C-Sections</Label>
                                <Input id="num_csections" name="num_csections" type="number" min="0" max="10" defaultValue={surrogate.num_csections ?? ""} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 pt-2">
                            <div className="flex items-center gap-2">
                                <Checkbox id="is_priority" name="is_priority" defaultChecked={surrogate.is_priority} />
                                <Label htmlFor="is_priority">Priority Surrogate</Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox id="is_age_eligible" name="is_age_eligible" defaultChecked={surrogate.is_age_eligible ?? false} />
                                <Label htmlFor="is_age_eligible">Age Eligible</Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox id="is_citizen_or_pr" name="is_citizen_or_pr" defaultChecked={surrogate.is_citizen_or_pr ?? false} />
                                <Label htmlFor="is_citizen_or_pr">US Citizen/PR</Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox id="has_child" name="has_child" defaultChecked={surrogate.has_child ?? false} />
                                <Label htmlFor="has_child">Has Child</Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox id="is_non_smoker" name="is_non_smoker" defaultChecked={surrogate.is_non_smoker ?? false} />
                                <Label htmlFor="is_non_smoker">Non-Smoker</Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox id="has_surrogate_experience" name="has_surrogate_experience" defaultChecked={surrogate.has_surrogate_experience ?? false} />
                                <Label htmlFor="has_surrogate_experience">Surrogate Experience</Label>
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
                        <Button type="submit" disabled={isUpdatePending}>
                            {isUpdatePending ? "Saving..." : "Save Changes"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}

"use client"

import { ShieldIcon } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InlineEditField } from "@/components/inline-edit-field"
import { InlineDateField } from "@/components/inline-date-field"
import { SurrogateRead } from "@/lib/types/surrogate"
import { SurrogateUpdatePayload } from "@/lib/api/surrogates"

interface InsuranceInfoCardProps {
    surrogateData: SurrogateRead
    onUpdate: (data: Partial<SurrogateUpdatePayload>) => Promise<void>
}

export function InsuranceInfoCard({ surrogateData, onUpdate }: InsuranceInfoCardProps) {
    const handleField = (field: string) => async (value: string | null) => {
        await onUpdate({ [field]: value })
    }

    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <ShieldIcon className="size-4" />
                    Insurance Information
                </CardTitle>
            </CardHeader>
            <CardContent className="px-4 space-y-3">
                {/* Company & Plan */}
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <span className="text-sm text-muted-foreground">Company:</span>
                        <InlineEditField
                            value={surrogateData.insurance_company}
                            onSave={handleField('insurance_company')}
                            placeholder="Insurance company"
                        />
                    </div>
                    <div>
                        <span className="text-sm text-muted-foreground">Plan:</span>
                        <InlineEditField
                            value={surrogateData.insurance_plan_name}
                            onSave={handleField('insurance_plan_name')}
                            placeholder="Plan name"
                        />
                    </div>
                </div>

                {/* Policy Details */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground shrink-0">Policy #:</span>
                        <InlineEditField
                            value={surrogateData.insurance_policy_number}
                            onSave={handleField('insurance_policy_number')}
                            placeholder="Policy number"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground shrink-0">Member ID:</span>
                        <InlineEditField
                            value={surrogateData.insurance_member_id}
                            onSave={handleField('insurance_member_id')}
                            placeholder="Member ID"
                        />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground shrink-0">Group #:</span>
                        <InlineEditField
                            value={surrogateData.insurance_group_number}
                            onSave={handleField('insurance_group_number')}
                            placeholder="Group number"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground shrink-0">Phone:</span>
                        <InlineEditField
                            value={surrogateData.insurance_phone}
                            onSave={handleField('insurance_phone')}
                            type="tel"
                            placeholder="Insurance phone"
                        />
                    </div>
                </div>

                {/* Subscriber Info */}
                <div className="border-t pt-3 mt-3">
                    <h4 className="text-sm font-medium mb-2">Subscriber</h4>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground shrink-0">Name:</span>
                            <InlineEditField
                                value={surrogateData.insurance_subscriber_name}
                                onSave={handleField('insurance_subscriber_name')}
                                placeholder="Subscriber name"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground shrink-0">DOB:</span>
                            <InlineDateField
                                value={surrogateData.insurance_subscriber_dob}
                                onSave={handleField('insurance_subscriber_dob')}
                                label="Subscriber date of birth"
                                placeholder="Set DOB"
                            />
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

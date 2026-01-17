"use client"

import { HospitalIcon, BuildingIcon, ActivityIcon, StethoscopeIcon } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MedicalContactSection } from "@/components/surrogates/MedicalContactSection"
import { SurrogateRead } from "@/lib/types/surrogate"
import { SurrogateUpdatePayload } from "@/lib/api/surrogates"

interface MedicalInfoCardProps {
    surrogateData: SurrogateRead
    onUpdate: (data: Partial<SurrogateUpdatePayload>) => Promise<void>
}

export function MedicalInfoCard({ surrogateData, onUpdate }: MedicalInfoCardProps) {
    const handleField = async (field: string, value: string | null) => {
        await onUpdate({ [field]: value })
    }

    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <HospitalIcon className="size-4" />
                    Medical Information
                </CardTitle>
            </CardHeader>
            <CardContent className="px-4">
                <div className="grid gap-4 md:grid-cols-2">
                    {/* IVF Clinic */}
                    <MedicalContactSection
                        title="IVF Clinic"
                        icon={<BuildingIcon className="size-4" />}
                        prefix="clinic"
                        data={surrogateData}
                        onUpdate={handleField}
                    />

                    {/* Monitoring Clinic */}
                    <MedicalContactSection
                        title="Monitoring Clinic"
                        icon={<ActivityIcon className="size-4" />}
                        prefix="monitoring_clinic"
                        data={surrogateData}
                        onUpdate={handleField}
                    />

                    {/* OB Provider */}
                    <MedicalContactSection
                        title="OB Provider"
                        icon={<StethoscopeIcon className="size-4" />}
                        prefix="ob"
                        data={surrogateData}
                        onUpdate={handleField}
                        showProviderName={true}
                        showClinicName={true}
                    />

                    {/* Delivery Hospital */}
                    <MedicalContactSection
                        title="Delivery Hospital"
                        icon={<HospitalIcon className="size-4" />}
                        prefix="delivery_hospital"
                        data={surrogateData}
                        onUpdate={handleField}
                    />
                </div>
            </CardContent>
        </Card>
    )
}

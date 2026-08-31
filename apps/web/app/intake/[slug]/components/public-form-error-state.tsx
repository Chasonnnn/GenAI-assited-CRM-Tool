import { AlertTriangleIcon } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { publicFormCardClassName, publicFormPageClassName } from "./public-form-styles"

export function PublicFormErrorState({ message }: { message: string }) {
    return (
        <div className={cn(publicFormPageClassName, "flex items-center justify-center p-4")}>
            <Card className={cn(publicFormCardClassName, "w-full max-w-md")}>
                <CardContent className="px-6 py-8 text-center">
                    <AlertTriangleIcon className="size-16 text-amber-500 mx-auto mb-4" />
                    <h1 className="text-xl font-semibold text-stone-900 mb-2">Form Not Available</h1>
                    <p className="text-stone-600">{message}</p>
                </CardContent>
            </Card>
        </div>
    )
}

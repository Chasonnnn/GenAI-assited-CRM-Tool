"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { useAuth } from "@/lib/auth-context"
import api from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"

const welcomeSchema = z.object({
    display_name: z
        .string()
        .min(2, "Name must be at least 2 characters")
        .max(100, "Name must be 100 characters or less"),
    title: z
        .string()
        .min(2, "Title must be at least 2 characters")
        .max(100, "Title must be 100 characters or less"),
    phone: z
        .string()
        .max(20, "Phone must be 20 characters or less")
        .optional()
        .or(z.literal("")),
})

type WelcomeFormData = z.infer<typeof welcomeSchema>

/**
 * Welcome/onboarding page for new users.
 *
 * Shown to users who haven't completed their profile (missing display_name or title).
 * After completing the form, redirects to the dashboard.
 */
export default function WelcomePage() {
    const router = useRouter()
    const { user, refetch } = useAuth()
    const [isSubmitting, setIsSubmitting] = useState(false)

    const {
        register,
        handleSubmit,
        reset,
        formState: { errors },
    } = useForm<WelcomeFormData>({
        resolver: zodResolver(welcomeSchema),
        defaultValues: {
            display_name: user?.display_name || "",
            title: user?.title || "",
            phone: user?.phone || "",
        },
    })

    const onSubmit = async (data: WelcomeFormData) => {
        setIsSubmitting(true)
        try {
            await api.patch("/auth/me", {
                display_name: data.display_name,
                title: data.title,
                phone: data.phone || null,
            })

            // Refetch user data to update profile_complete
            await refetch()

            toast.success("Profile completed successfully!")
            router.push("/dashboard")
        } catch (error) {
            toast.error(
                error instanceof Error ? error.message : "Failed to update profile"
            )
        } finally {
            setIsSubmitting(false)
        }
    }

    useEffect(() => {
        if (user?.profile_complete) {
            router.replace("/dashboard")
        }
    }, [user, router])

    useEffect(() => {
        if (user) {
            reset({
                display_name: user.display_name || "",
                title: user.title || "",
                phone: user.phone || "",
            })
        }
    }, [user, reset])

    if (user?.profile_complete) {
        return null
    }

    return (
        <div className="flex min-h-[80vh] items-center justify-center p-6">
            <Card className="w-full max-w-md">
                <CardHeader className="text-center">
                    <CardTitle className="text-2xl">Welcome to Surrogacy Force</CardTitle>
                    <CardDescription>
                        Complete your profile to get started
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="display_name">
                                Full Name <span className="text-destructive">*</span>
                            </Label>
                            <Input
                                id="display_name"
                                placeholder="Enter your full name"
                                {...register("display_name")}
                                aria-invalid={!!errors.display_name}
                            />
                            {errors.display_name && (
                                <p className="text-sm text-destructive">
                                    {errors.display_name.message}
                                </p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="title">
                                Job Title <span className="text-destructive">*</span>
                            </Label>
                            <Input
                                id="title"
                                placeholder="e.g., Case Manager, Intake Specialist"
                                {...register("title")}
                                aria-invalid={!!errors.title}
                            />
                            {errors.title && (
                                <p className="text-sm text-destructive">
                                    {errors.title.message}
                                </p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="phone">Phone (optional)</Label>
                            <Input
                                id="phone"
                                type="tel"
                                placeholder="(555) 123-4567"
                                {...register("phone")}
                                aria-invalid={!!errors.phone}
                            />
                            {errors.phone && (
                                <p className="text-sm text-destructive">
                                    {errors.phone.message}
                                </p>
                            )}
                        </div>

                        <Button
                            type="submit"
                            className="w-full"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? (
                                <>
                                    <Loader2 className="mr-2 size-4 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                "Complete Profile"
                            )}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    )
}

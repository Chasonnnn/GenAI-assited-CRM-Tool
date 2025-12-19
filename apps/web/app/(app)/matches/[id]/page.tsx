"use client"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { CheckIcon, XIcon, MapPinIcon, CakeIcon, HeartIcon, HomeIcon, BabyIcon, ArrowLeftIcon } from "lucide-react"
import Link from "next/link"

export default function MatchReviewPage({ params }: { params: { id: string } }) {
    // Sample match data
    const compatibilityScore = 92

    const matchCriteria = [
        { label: "State Preference", match: true, details: "Both located in California" },
        { label: "Age Range", match: true, details: "Surrogate age 28 within preferred range" },
        { label: "Previous Experience", match: true, details: "Surrogate has 1 prior successful journey" },
        { label: "Medical History", match: true, details: "All health screenings passed" },
        { label: "Availability Timeline", match: true, details: "Ready to begin within 2 months" },
        { label: "Communication Style", match: true, details: "Both prefer frequent updates" },
        { label: "Openness Level", match: false, details: "IPs prefer closed arrangement, surrogate prefers semi-open" },
        { label: "Compensation Agreement", match: true, details: "Within expected range" },
    ]

    return (
        <div className="flex flex-1 flex-col gap-6 p-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Link href="/matches">
                    <Button variant="ghost" size="icon">
                        <ArrowLeftIcon className="h-5 w-5" />
                    </Button>
                </Link>
                <div>
                    <h1 className="text-2xl font-bold">Match Review</h1>
                    <p className="text-sm text-muted-foreground">Proposed Match #{params.id}</p>
                </div>
            </div>

            {/* Profile Cards */}
            <div className="grid gap-6 md:grid-cols-2">
                {/* Surrogate Profile */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Surrogate</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-start gap-4">
                            <Avatar className="h-12 w-12">
                                <AvatarFallback className="text-lg">SJ</AvatarFallback>
                            </Avatar>
                            <div className="flex-1 space-y-1">
                                <h3 className="text-xl font-semibold">Sarah Johnson</h3>
                                <Badge className="bg-teal-500 hover:bg-teal-500/80">Active</Badge>
                            </div>
                        </div>

                        <div className="space-y-3 pt-2">
                            <div className="flex items-center gap-2 text-sm">
                                <MapPinIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Location:</span>
                                <span className="font-medium">San Diego, CA</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <CakeIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Age:</span>
                                <span className="font-medium">28 years old</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <BabyIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Experience:</span>
                                <span className="font-medium">1 successful journey</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <HomeIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Family:</span>
                                <span className="font-medium">Married, 2 children</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <HeartIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Openness:</span>
                                <span className="font-medium">Semi-open arrangement</span>
                            </div>
                        </div>

                        <div className="pt-2">
                            <Link href="/cases/42">
                                <Button variant="outline" size="sm" className="w-full bg-transparent">
                                    View Full Profile
                                </Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>

                {/* Intended Parent Profile */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Intended Parents</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-start gap-4">
                            <Avatar className="h-12 w-12">
                                <AvatarFallback className="text-lg">MC</AvatarFallback>
                            </Avatar>
                            <div className="flex-1 space-y-1">
                                <h3 className="text-xl font-semibold">Michael & Claire Thompson</h3>
                                <Badge className="bg-blue-500 hover:bg-blue-500/80">Active</Badge>
                            </div>
                        </div>

                        <div className="space-y-3 pt-2">
                            <div className="flex items-center gap-2 text-sm">
                                <MapPinIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Location:</span>
                                <span className="font-medium">Los Angeles, CA</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <CakeIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Ages:</span>
                                <span className="font-medium">35 & 33 years old</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <BabyIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Experience:</span>
                                <span className="font-medium">First-time IPs</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <HomeIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Family:</span>
                                <span className="font-medium">Married couple</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <HeartIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Openness:</span>
                                <span className="font-medium">Closed arrangement</span>
                            </div>
                        </div>

                        <div className="pt-2">
                            <Link href="/intended-parents/12">
                                <Button variant="outline" size="sm" className="w-full bg-transparent">
                                    View Full Profile
                                </Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Compatibility Section */}
            <Card>
                <CardHeader>
                    <CardTitle>Compatibility Analysis</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Circular Progress Score */}
                    <div className="flex flex-col items-center justify-center py-6">
                        <div className="relative flex h-32 w-32 items-center justify-center">
                            <svg className="h-32 w-32 -rotate-90 transform">
                                <circle
                                    cx="64"
                                    cy="64"
                                    r="56"
                                    stroke="currentColor"
                                    strokeWidth="8"
                                    fill="none"
                                    className="text-muted"
                                />
                                <circle
                                    cx="64"
                                    cy="64"
                                    r="56"
                                    stroke="currentColor"
                                    strokeWidth="8"
                                    fill="none"
                                    strokeDasharray={`${2 * Math.PI * 56}`}
                                    strokeDashoffset={`${2 * Math.PI * 56 * (1 - compatibilityScore / 100)}`}
                                    className="text-teal-500 transition-all duration-1000"
                                    strokeLinecap="round"
                                />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-3xl font-bold">{compatibilityScore}%</span>
                                <span className="text-xs text-muted-foreground">Match Score</span>
                            </div>
                        </div>
                        <p className="mt-4 text-center text-sm text-muted-foreground">
                            This is an excellent match with strong compatibility across most criteria
                        </p>
                    </div>

                    {/* Match Criteria Checklist */}
                    <div className="space-y-3">
                        <h3 className="font-semibold">Match Criteria</h3>
                        <div className="space-y-2">
                            {matchCriteria.map((criterion, index) => (
                                <div
                                    key={index}
                                    className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                                >
                                    <div
                                        className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded-full ${criterion.match ? "bg-green-500/10" : "bg-red-500/10"
                                            }`}
                                    >
                                        {criterion.match ? (
                                            <CheckIcon className="h-3 w-3 text-green-600" />
                                        ) : (
                                            <XIcon className="h-3 w-3 text-red-600" />
                                        )}
                                    </div>
                                    <div className="flex-1 space-y-1">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-medium">{criterion.label}</span>
                                            {criterion.match ? (
                                                <Badge variant="secondary" className="bg-green-500/10 text-green-700 hover:bg-green-500/20">
                                                    Match
                                                </Badge>
                                            ) : (
                                                <Badge variant="secondary" className="bg-red-500/10 text-red-700 hover:bg-red-500/20">
                                                    Mismatch
                                                </Badge>
                                            )}
                                        </div>
                                        <p className="text-xs text-muted-foreground">{criterion.details}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Notes Section */}
            <Card>
                <CardHeader>
                    <CardTitle>Coordinator Notes</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Textarea
                        placeholder="Add notes about this match, including any concerns or recommendations..."
                        className="min-h-32"
                        defaultValue="The openness preference difference may require discussion. Both parties are open to communication, so this can likely be addressed in the initial meeting. Overall, this appears to be a very strong match."
                    />
                    <p className="text-xs text-muted-foreground">
                        These notes will be visible to the matching team and can be referenced during the review process.
                    </p>
                </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <Button variant="outline" className="sm:order-1 bg-transparent">
                    Reject Match
                </Button>
                <Button variant="outline" className="sm:order-2 bg-transparent">
                    Request Changes
                </Button>
                <Button className="bg-teal-500 hover:bg-teal-600 sm:order-3">
                    <CheckIcon className="mr-2 h-4 w-4" />
                    Accept Match
                </Button>
            </div>
        </div>
    )
}

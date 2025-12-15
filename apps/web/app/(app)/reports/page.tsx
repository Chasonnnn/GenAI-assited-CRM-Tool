"use client"

import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { ChevronDownIcon, TrendingUpIcon, UsersIcon, CheckCircle2Icon, ClockIcon } from "lucide-react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, Line, LineChart, Pie, PieChart } from "recharts"
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    ChartLegend,
    ChartLegendContent,
} from "@/components/ui/chart"

// Chart data
const casesOverviewData = [
    { status: "New", cases: 24, fill: "hsl(var(--chart-1))" },
    { status: "Contacted", cases: 32, fill: "hsl(var(--chart-2))" },
    { status: "Qualified", cases: 18, fill: "hsl(var(--chart-3))" },
    { status: "In Process", cases: 28, fill: "hsl(var(--chart-4))" },
    { status: "Matched", cases: 15, fill: "hsl(var(--chart-5))" },
    { status: "On Hold", cases: 8, fill: "hsl(var(--chart-6))" },
]

const monthlyTrendsData = [
    { month: "Jan", newCases: 18, matched: 5 },
    { month: "Feb", newCases: 22, matched: 6 },
    { month: "Mar", newCases: 28, matched: 8 },
    { month: "Apr", newCases: 24, matched: 7 },
    { month: "May", newCases: 32, matched: 9 },
    { month: "Jun", newCases: 26, matched: 8 },
]

const casesBySourceData = [
    { source: "Meta", value: 58, fill: "hsl(var(--chart-1))" },
    { source: "Manual", value: 28, fill: "hsl(var(--chart-2))" },
    { source: "Import", value: 14, fill: "hsl(var(--chart-3))" },
]

const teamPerformanceData = [
    { member: "Emily Chen", cases: 38, fill: "hsl(var(--chart-1))" },
    { member: "John Smith", cases: 32, fill: "hsl(var(--chart-2))" },
    { member: "Sarah Davis", cases: 28, fill: "hsl(var(--chart-3))" },
    { member: "Mike Johnson", cases: 25, fill: "hsl(var(--chart-4))" },
]

const casesOverviewConfig = {
    cases: { label: "Cases" },
}

const monthlyTrendsConfig = {
    newCases: { label: "New Cases", color: "hsl(var(--chart-1))" },
    matched: { label: "Matched", color: "hsl(var(--chart-2))" },
}

const casesBySourceConfig = {
    value: { label: "Cases" },
}

const teamPerformanceConfig = {
    cases: { label: "Cases" },
}

export default function ReportsPage() {
    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Reports</h1>
                    <DropdownMenu>
                        <DropdownMenuTrigger className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                            Export
                            <ChevronDownIcon className="size-4" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem>Export PDF</DropdownMenuItem>
                            <DropdownMenuItem>Export CSV</DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                {/* Charts Grid - 2x2 layout */}
                <div className="grid gap-6 md:grid-cols-2">
                    {/* Card 1 - Cases Overview (Bar Chart) */}
                    <Card className="animate-in fade-in-50 duration-500">
                        <CardHeader>
                            <CardTitle>Cases Overview</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ChartContainer config={casesOverviewConfig} className="h-[300px] w-full">
                                <BarChart data={casesOverviewData}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="status" tickLine={false} axisLine={false} />
                                    <YAxis tickLine={false} axisLine={false} />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <ChartLegend content={<ChartLegendContent />} />
                                    <Bar dataKey="cases" radius={[8, 8, 0, 0]} />
                                </BarChart>
                            </ChartContainer>
                        </CardContent>
                        <CardFooter className="text-sm text-muted-foreground">Last 30 days</CardFooter>
                    </Card>

                    {/* Card 2 - Monthly Trends (Line Chart) */}
                    <Card className="animate-in fade-in-50 duration-500 delay-100">
                        <CardHeader>
                            <CardTitle>Monthly Trends</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ChartContainer config={monthlyTrendsConfig} className="h-[300px] w-full">
                                <LineChart data={monthlyTrendsData}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="month" tickLine={false} axisLine={false} />
                                    <YAxis tickLine={false} axisLine={false} />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <ChartLegend content={<ChartLegendContent />} />
                                    <Line
                                        type="monotone"
                                        dataKey="newCases"
                                        stroke="hsl(var(--chart-1))"
                                        strokeWidth={2}
                                        dot={{ r: 4 }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="matched"
                                        stroke="hsl(var(--chart-2))"
                                        strokeWidth={2}
                                        dot={{ r: 4 }}
                                    />
                                </LineChart>
                            </ChartContainer>
                        </CardContent>
                        <CardFooter className="text-sm text-muted-foreground">Last 6 months</CardFooter>
                    </Card>

                    {/* Card 3 - Cases by Source (Pie Chart) */}
                    <Card className="animate-in fade-in-50 duration-500 delay-200">
                        <CardHeader>
                            <CardTitle>Cases by Source</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ChartContainer config={casesBySourceConfig} className="h-[300px] w-full">
                                <PieChart>
                                    <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                                    <Pie
                                        data={casesBySourceData}
                                        dataKey="value"
                                        nameKey="source"
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={60}
                                        outerRadius={100}
                                        paddingAngle={2}
                                        label={({ name, value }) => `${name}: ${value}%`}
                                    />
                                    <ChartLegend content={<ChartLegendContent />} />
                                </PieChart>
                            </ChartContainer>
                        </CardContent>
                        <CardFooter className="text-sm text-muted-foreground">All time</CardFooter>
                    </Card>

                    {/* Card 4 - Team Performance (Horizontal Bar Chart) */}
                    <Card className="animate-in fade-in-50 duration-500 delay-300">
                        <CardHeader>
                            <CardTitle>Team Performance</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ChartContainer config={teamPerformanceConfig} className="h-[300px] w-full">
                                <BarChart data={teamPerformanceData} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                    <XAxis type="number" tickLine={false} axisLine={false} />
                                    <YAxis dataKey="member" type="category" tickLine={false} axisLine={false} width={100} />
                                    <ChartTooltip content={<ChartTooltipContent />} />
                                    <Bar dataKey="cases" radius={[0, 8, 8, 0]} />
                                </BarChart>
                            </ChartContainer>
                        </CardContent>
                        <CardFooter className="text-sm text-muted-foreground">Last 30 days</CardFooter>
                    </Card>
                </div>

                {/* Quick Stats Row */}
                <div className="grid gap-4 md:grid-cols-4">
                    <Card className="animate-in fade-in-50 duration-500 delay-400">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Total Cases</CardTitle>
                            <TrendingUpIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">156</div>
                            <p className="text-xs text-muted-foreground">+12% from last month</p>
                        </CardContent>
                    </Card>

                    <Card className="animate-in fade-in-50 duration-500 delay-500">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Active Cases</CardTitle>
                            <UsersIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">42</div>
                            <p className="text-xs text-muted-foreground">Currently in progress</p>
                        </CardContent>
                    </Card>

                    <Card className="animate-in fade-in-50 duration-500 delay-[600ms]">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Matched This Month</CardTitle>
                            <CheckCircle2Icon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">8</div>
                            <p className="text-xs text-muted-foreground">+2 from last month</p>
                        </CardContent>
                    </Card>

                    <Card className="animate-in fade-in-50 duration-500 delay-700">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Avg Days to Match</CardTitle>
                            <ClockIcon className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">45</div>
                            <p className="text-xs text-muted-foreground">-5 days improvement</p>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}

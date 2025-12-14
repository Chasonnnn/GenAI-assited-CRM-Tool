"use client"

import { useState } from "react"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { PlusIcon, MoreVerticalIcon, SearchIcon, XIcon } from "lucide-react"

// Sample data - TODO: Replace with API data
const cases = [
    {
        id: "00042",
        name: "Sarah Johnson",
        status: "In Process",
        source: "Meta",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        created: "2 days ago",
    },
    {
        id: "00041",
        name: "Michael Thompson",
        status: "Contacted",
        source: "Manual",
        assignee: { name: "John Smith", avatar: "/avatars/john.jpg", initials: "JS" },
        created: "3 days ago",
    },
    {
        id: "00040",
        name: "Amanda Rodriguez",
        status: "Matched",
        source: "Import",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        created: "5 days ago",
    },
    {
        id: "00039",
        name: "Jessica Williams",
        status: "Qualified",
        source: "Meta",
        assignee: { name: "Sarah Davis", avatar: "/avatars/sarah.jpg", initials: "SD" },
        created: "1 week ago",
    },
    {
        id: "00038",
        name: "David Martinez",
        status: "New",
        source: "Manual",
        assignee: { name: "John Smith", avatar: "/avatars/john.jpg", initials: "JS" },
        created: "1 week ago",
    },
    {
        id: "00037",
        name: "Jennifer Lee",
        status: "On Hold",
        source: "Import",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        created: "2 weeks ago",
    },
    {
        id: "00036",
        name: "Robert Anderson",
        status: "In Process",
        source: "Meta",
        assignee: { name: "Sarah Davis", avatar: "/avatars/sarah.jpg", initials: "SD" },
        created: "2 weeks ago",
    },
    {
        id: "00035",
        name: "Maria Garcia",
        status: "Contacted",
        source: "Manual",
        assignee: { name: "John Smith", avatar: "/avatars/john.jpg", initials: "JS" },
        created: "3 weeks ago",
    },
    {
        id: "00034",
        name: "Christopher Brown",
        status: "Archived",
        source: "Import",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        created: "1 month ago",
    },
    {
        id: "00033",
        name: "Lisa Taylor",
        status: "Qualified",
        source: "Meta",
        assignee: { name: "Sarah Davis", avatar: "/avatars/sarah.jpg", initials: "SD" },
        created: "1 month ago",
    },
]

const statusColors: Record<string, string> = {
    New: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    Contacted: "bg-teal-500/10 text-teal-500 border-teal-500/20",
    Qualified: "bg-green-500/10 text-green-500 border-green-500/20",
    "In Process": "bg-amber-500/10 text-amber-500 border-amber-500/20",
    Matched: "bg-purple-500/10 text-purple-500 border-purple-500/20",
    "On Hold": "bg-gray-500/10 text-gray-400 border-gray-500/20",
    Archived: "bg-slate-500/10 text-slate-400 border-slate-500/20",
}

export default function CasesPage() {
    const [statusFilter, setStatusFilter] = useState("all")
    const [sourceFilter, setSourceFilter] = useState("all")
    const [searchQuery, setSearchQuery] = useState("")

    const hasActiveFilters = statusFilter !== "all" || sourceFilter !== "all" || searchQuery !== ""

    const resetFilters = () => {
        setStatusFilter("all")
        setSourceFilter("all")
        setSearchQuery("")
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Cases</h1>
                    <Button>
                        <PlusIcon className="mr-2 size-4" />
                        New Case
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-4 p-6">
                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3">
                    <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value || "all")}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Statuses" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Statuses</SelectItem>
                            <SelectItem value="new">New</SelectItem>
                            <SelectItem value="contacted">Contacted</SelectItem>
                            <SelectItem value="qualified">Qualified</SelectItem>
                            <SelectItem value="in-process">In Process</SelectItem>
                            <SelectItem value="matched">Matched</SelectItem>
                            <SelectItem value="on-hold">On Hold</SelectItem>
                            <SelectItem value="archived">Archived</SelectItem>
                        </SelectContent>
                    </Select>

                    <Select value={sourceFilter} onValueChange={(value) => setSourceFilter(value || "all")}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Sources" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Sources</SelectItem>
                            <SelectItem value="manual">Manual</SelectItem>
                            <SelectItem value="meta">Meta</SelectItem>
                            <SelectItem value="import">Import</SelectItem>
                        </SelectContent>
                    </Select>

                    <div className="relative ml-auto w-full max-w-sm">
                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search cases..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-9"
                        />
                    </div>

                    {hasActiveFilters && (
                        <Button variant="ghost" onClick={resetFilters}>
                            <XIcon className="mr-2 size-4" />
                            Reset
                        </Button>
                    )}
                </div>

                {/* Table Card */}
                <Card className="overflow-hidden">
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Case #</TableHead>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Source</TableHead>
                                    <TableHead>Assignee</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead className="w-[50px]">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {cases.map((caseItem) => (
                                    <TableRow key={caseItem.id}>
                                        <TableCell>
                                            <Link href={`/cases/${caseItem.id}`} className="font-medium text-primary hover:underline">
                                                #{caseItem.id}
                                            </Link>
                                        </TableCell>
                                        <TableCell className="font-medium">{caseItem.name}</TableCell>
                                        <TableCell>
                                            <Badge variant="secondary" className={statusColors[caseItem.status]}>
                                                {caseItem.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="secondary">{caseItem.source}</Badge>
                                        </TableCell>
                                        <TableCell>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger>
                                                        <Avatar className="size-8">
                                                            <AvatarImage src={caseItem.assignee.avatar || "/placeholder.svg"} />
                                                            <AvatarFallback>{caseItem.assignee.initials}</AvatarFallback>
                                                        </Avatar>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>{caseItem.assignee.name}</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">{caseItem.created}</TableCell>
                                        <TableCell>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="sm" className="size-8 p-0">
                                                        <MoreVerticalIcon className="size-4" />
                                                        <span className="sr-only">Open menu</span>
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem asChild>
                                                        <Link href={`/cases/${caseItem.id}`}>View</Link>
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem>Edit</DropdownMenuItem>
                                                    <DropdownMenuItem>Archive</DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>

                    {/* Pagination */}
                    <div className="flex items-center justify-between border-t border-border px-6 py-4">
                        <div className="text-sm text-muted-foreground">Showing 1-10 of 156 cases</div>
                        <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm" disabled>
                                Previous
                            </Button>
                            <Button variant="outline" size="sm" className="bg-primary/10 text-primary">
                                1
                            </Button>
                            <Button variant="outline" size="sm">
                                2
                            </Button>
                            <Button variant="outline" size="sm">
                                3
                            </Button>
                            <Button variant="outline" size="sm">
                                Next
                            </Button>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    )
}

'use client';

import { useState } from 'react';
import { useCases } from '@/lib/hooks/use-cases';
import { STATUS_CONFIG, type CaseStatus } from '@/lib/types/case';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

export default function CasesPage() {
    const [search, setSearch] = useState('');
    const [page, setPage] = useState(1);
    const [debouncedSearch, setDebouncedSearch] = useState('');

    // Debounce search
    const handleSearch = (value: string) => {
        setSearch(value);
        // Simple debounce
        setTimeout(() => {
            setDebouncedSearch(value);
            setPage(1);
        }, 300);
    };

    const { data, isLoading, error } = useCases({
        page,
        per_page: 20,
        q: debouncedSearch || undefined,
    });

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
        });
    };

    const getStatusBadge = (status: CaseStatus) => {
        const config = STATUS_CONFIG[status] || { label: status, color: 'bg-gray-500' };
        return (
            <Badge className={`${config.color} text-white hover:${config.color}`}>
                {config.label}
            </Badge>
        );
    };

    if (error) {
        return (
            <div className="p-8">
                <div className="bg-red-50 text-red-700 p-4 rounded-lg">
                    <h2 className="font-semibold">Error loading cases</h2>
                    <p className="text-sm mt-1">
                        {error instanceof Error ? error.message : 'Unknown error'}
                    </p>
                    <p className="text-sm mt-2 text-red-600">
                        Make sure you're logged in and the API is running.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold">Cases</h1>
                    <p className="text-muted-foreground">
                        {data ? `${data.total} total cases` : 'Loading...'}
                    </p>
                </div>
                <Button>+ New Case</Button>
            </div>

            {/* Search */}
            <div className="relative mb-6">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="Search by name, email, phone, or case #..."
                    value={search}
                    onChange={(e) => handleSearch(e.target.value)}
                    className="pl-10 max-w-md"
                />
            </div>

            {/* Table */}
            <div className="border rounded-lg">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-24">Case #</TableHead>
                            <TableHead>Name</TableHead>
                            <TableHead>Email</TableHead>
                            <TableHead>Phone</TableHead>
                            <TableHead>State</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Assigned To</TableHead>
                            <TableHead>Created</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading ? (
                            <TableRow>
                                <TableCell colSpan={8} className="text-center py-8">
                                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                                </TableCell>
                            </TableRow>
                        ) : data?.items.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                                    No cases found
                                </TableCell>
                            </TableRow>
                        ) : (
                            data?.items.map((item) => (
                                <TableRow
                                    key={item.id}
                                    className="cursor-pointer hover:bg-muted/50"
                                >
                                    <TableCell className="font-mono font-medium">
                                        #{item.case_number}
                                    </TableCell>
                                    <TableCell className="font-medium">{item.full_name}</TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {item.email}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {item.phone || '—'}
                                    </TableCell>
                                    <TableCell>{item.state || '—'}</TableCell>
                                    <TableCell>{getStatusBadge(item.status)}</TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {item.assigned_to_name || '—'}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {formatDate(item.created_at)}
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination */}
            {data && data.pages > 1 && (
                <div className="flex items-center justify-between mt-4">
                    <p className="text-sm text-muted-foreground">
                        Page {data.page} of {data.pages}
                    </p>
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                        >
                            <ChevronLeft className="h-4 w-4" />
                            Previous
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage((p) => p + 1)}
                            disabled={page >= data.pages}
                        >
                            Next
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}

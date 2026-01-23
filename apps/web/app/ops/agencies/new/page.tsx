'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { createOrganization } from '@/lib/api/platform';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { ChevronRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const TIMEZONES = [
    { value: 'America/Los_Angeles', label: 'Pacific Time (US)' },
    { value: 'America/Denver', label: 'Mountain Time (US)' },
    { value: 'America/Chicago', label: 'Central Time (US)' },
    { value: 'America/New_York', label: 'Eastern Time (US)' },
    { value: 'America/Phoenix', label: 'Arizona Time (US)' },
    { value: 'America/Anchorage', label: 'Alaska Time (US)' },
    { value: 'Pacific/Honolulu', label: 'Hawaii Time (US)' },
    { value: 'UTC', label: 'UTC' },
];

export default function NewAgencyPage() {
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [form, setForm] = useState({
        name: '',
        slug: '',
        timezone: 'America/Los_Angeles',
        admin_email: '',
    });
    const [errors, setErrors] = useState<Record<string, string>>({});

    const generateSlug = (name: string) => {
        return name
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .substring(0, 50);
    };

    const handleNameChange = (value: string) => {
        setForm((prev) => ({
            ...prev,
            name: value,
            slug: generateSlug(value),
        }));
    };

    const validate = () => {
        const newErrors: Record<string, string> = {};

        if (!form.name.trim()) {
            newErrors.name = 'Name is required';
        }

        if (!form.slug.trim()) {
            newErrors.slug = 'Slug is required';
        } else if (!/^[a-z0-9-]+$/.test(form.slug)) {
            newErrors.slug = 'Slug must contain only lowercase letters, numbers, and hyphens';
        } else if (form.slug.length < 3) {
            newErrors.slug = 'Slug must be at least 3 characters';
        }

        if (!form.admin_email.trim()) {
            newErrors.admin_email = 'Admin email is required';
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.admin_email)) {
            newErrors.admin_email = 'Invalid email address';
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!validate()) return;

        setIsSubmitting(true);
        try {
            const org = await createOrganization({
                name: form.name.trim(),
                slug: form.slug.trim(),
                timezone: form.timezone,
                admin_email: form.admin_email.trim().toLowerCase(),
            });
            toast.success('Agency created successfully');
            router.push(`/ops/agencies/${org.id}`);
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : 'Failed to create agency';
            toast.error(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="p-6 max-w-2xl mx-auto">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm text-stone-500 dark:text-stone-400 mb-6">
                <Link
                    href="/ops/agencies"
                    className="hover:text-stone-900 dark:hover:text-stone-100"
                >
                    Agencies
                </Link>
                <ChevronRight className="size-4" />
                <span className="text-stone-900 dark:text-stone-100">Create New Agency</span>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Create New Agency</CardTitle>
                    <CardDescription>
                        Create a new agency and send an invitation to their first administrator.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-6">
                        {/* Name */}
                        <div className="space-y-2">
                            <Label htmlFor="name">Agency Name</Label>
                            <Input
                                id="name"
                                value={form.name}
                                onChange={(e) => handleNameChange(e.target.value)}
                                placeholder="Acme Surrogacy Agency"
                                className={errors.name ? 'border-red-500' : ''}
                            />
                            {errors.name && (
                                <p className="text-sm text-red-500">{errors.name}</p>
                            )}
                        </div>

                        {/* Slug */}
                        <div className="space-y-2">
                            <Label htmlFor="slug">Slug</Label>
                            <Input
                                id="slug"
                                value={form.slug}
                                onChange={(e) =>
                                    setForm((prev) => ({ ...prev, slug: e.target.value }))
                                }
                                placeholder="acme-surrogacy"
                                className={`font-mono ${errors.slug ? 'border-red-500' : ''}`}
                            />
                            <p className="text-xs text-muted-foreground">
                                Used in URLs. Lowercase letters, numbers, and hyphens only.
                            </p>
                            {errors.slug && (
                                <p className="text-sm text-red-500">{errors.slug}</p>
                            )}
                        </div>

                        {/* Timezone */}
                        <div className="space-y-2">
                            <Label htmlFor="timezone">Timezone</Label>
                            <Select
                                value={form.timezone}
                                onValueChange={(value) => {
                                    if (value) setForm((prev) => ({ ...prev, timezone: value }));
                                }}
                            >
                                <SelectTrigger id="timezone">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {TIMEZONES.map((tz) => (
                                        <SelectItem key={tz.value} value={tz.value}>
                                            {tz.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Admin Email */}
                        <div className="space-y-2">
                            <Label htmlFor="admin_email">First Admin Email</Label>
                            <Input
                                id="admin_email"
                                type="email"
                                value={form.admin_email}
                                onChange={(e) =>
                                    setForm((prev) => ({ ...prev, admin_email: e.target.value }))
                                }
                                placeholder="admin@agency.com"
                                className={errors.admin_email ? 'border-red-500' : ''}
                            />
                            <p className="text-xs text-muted-foreground">
                                An invitation will be sent to this email address.
                            </p>
                            {errors.admin_email && (
                                <p className="text-sm text-red-500">{errors.admin_email}</p>
                            )}
                        </div>

                        {/* Actions */}
                        <div className="flex gap-3 pt-4">
                            <Button type="submit" disabled={isSubmitting}>
                                {isSubmitting && (
                                    <Loader2 className="mr-2 size-4 animate-spin" />
                                )}
                                Create Agency
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => router.push('/ops/agencies')}
                            >
                                Cancel
                            </Button>
                        </div>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}

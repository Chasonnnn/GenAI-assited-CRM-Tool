'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { createOrganization } from '@/lib/api/platform';
import { ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card';
import { ValidatedField } from '@/components/ui/field';
import { PageHeader } from '@/components/page-header';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Loader2 } from 'lucide-react';
import { toast } from '@/components/ui/toast';
import { useFormValidation, type FormFieldErrors } from '@/lib/forms/use-form-validation';
import { validateEmail, validateRequired } from '@/lib/forms/validators';
import { createSelectLabelGetter } from '@/lib/select-labels';

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

const getTimezoneLabel = createSelectLabelGetter(TIMEZONES, {
    emptyLabel: 'Select timezone',
    unknownLabel: 'Unknown timezone',
});

const SLUG_PATTERN = /^[a-z0-9-]+$/;

type NewAgencyForm = {
    name: string;
    slug: string;
    timezone: string;
    admin_email: string;
};

function validateNewAgency(values: NewAgencyForm): FormFieldErrors<NewAgencyForm> {
    const slug = values.slug.trim();
    return {
        name: validateRequired(values.name, 'Enter an agency name.'),
        slug: !slug
            ? 'Enter a slug.'
            : !SLUG_PATTERN.test(slug)
                ? 'Use only lowercase letters, numbers, and hyphens.'
                : slug.length < 3
                    ? 'Use at least 3 characters.'
                    : undefined,
        admin_email: validateEmail(values.admin_email, { requiredMessage: 'Enter the first admin email.' }),
    };
}

function getBadRequestField(message: string): 'slug' | 'admin_email' | null {
    if (/slug/i.test(message)) return 'slug';
    if (/admin email/i.test(message)) return 'admin_email';
    return null;
}

function generateSlug(name: string) {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-')
        .substring(0, 50);
}

export default function NewAgencyPage() {
    const { push } = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [form, setForm] = useState<NewAgencyForm>({
        name: '',
        slug: '',
        timezone: 'America/Los_Angeles',
        admin_email: '',
    });
    const validation = useFormValidation({ values: form, validate: validateNewAgency });

    const handleNameChange = (value: string) => {
        setForm((prev) => ({
            ...prev,
            name: value,
            slug: generateSlug(value),
        }));
    };

    const createAgency = async (values: NewAgencyForm) => {
        setIsSubmitting(true);
        const result = await createOrganization({
            name: values.name.trim(),
            slug: values.slug.trim(),
            timezone: values.timezone,
            admin_email: values.admin_email.trim().toLowerCase(),
        }).then((org) => ({
            status: 'success' as const,
            org,
        })).catch((error: unknown) => ({
            status: 'error' as const,
            error,
        }));

        setIsSubmitting(false);
        if (result.status === 'success') {
            toast.success('Agency created successfully');
            push(`/ops/agencies/${result.org.id}`);
            return;
        }
        // platform_service.create_organization raises its own slug and admin email messages as 400s.
        const badRequestField =
            result.error instanceof ApiError && result.error.status === 400
                ? getBadRequestField(result.error.message)
                : null;
        if (badRequestField && result.error instanceof Error) {
            validation.setServerErrors({ [badRequestField]: result.error.message });
            return;
        }
        const message = validation.applyApiError(result.error, {
            fields: ['name', 'slug', 'timezone', 'admin_email'],
            fallback: "Couldn't create agency.",
        });
        if (message) toast.error(message);
    };

    return (
        <div>
            <PageHeader
                title="Create Agency"
                back={{ href: '/ops/agencies', label: 'Back to Agencies' }}
            />
            <div className="p-6 max-w-2xl mx-auto">
            <Card>
                <CardHeader>
                    <CardDescription>
                        Create a new agency and send an invitation to their first administrator.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form noValidate onSubmit={validation.handleSubmit(createAgency)} className="space-y-6">
                        <ValidatedField id="name" label="Agency Name" error={validation.errorFor('name')}>
                            {(control) => (
                                <Input
                                    {...control}
                                    value={form.name}
                                    onChange={(e) => handleNameChange(e.target.value)}
                                    onBlur={() => validation.touch('name')}
                                    placeholder="Acme Surrogacy Agency"
                                />
                            )}
                        </ValidatedField>

                        <ValidatedField
                            id="slug"
                            label="Slug"
                            description="Lowercase letters, numbers, and hyphens."
                            error={validation.errorFor('slug')}
                        >
                            {(control) => (
                                <Input
                                    {...control}
                                    value={form.slug}
                                    onChange={(e) =>
                                        setForm((prev) => ({ ...prev, slug: e.target.value }))
                                    }
                                    onBlur={() => validation.touch('slug')}
                                    placeholder="acme-surrogacy"
                                    className="font-mono"
                                />
                            )}
                        </ValidatedField>

                        <div className="space-y-2">
                            <Label htmlFor="timezone">Timezone</Label>
                            <Select
                                value={form.timezone}
                                onValueChange={(value) => {
                                    if (value) setForm((prev) => ({ ...prev, timezone: value }));
                                }}
                            >
                                <SelectTrigger id="timezone" className="w-full">
                                    <SelectValue>{getTimezoneLabel}</SelectValue>
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

                        <ValidatedField
                            id="admin_email"
                            label="First Admin Email"
                            description="An invitation is sent to this address."
                            error={validation.errorFor('admin_email')}
                        >
                            {(control) => (
                                <Input
                                    {...control}
                                    type="email"
                                    value={form.admin_email}
                                    onChange={(e) =>
                                        setForm((prev) => ({ ...prev, admin_email: e.target.value }))
                                    }
                                    onBlur={() => validation.touch('admin_email')}
                                    placeholder="admin@agency.com"
                                />
                            )}
                        </ValidatedField>

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
                                onClick={() => push('/ops/agencies')}
                            >
                                Cancel
                            </Button>
                        </div>
                    </form>
                </CardContent>
            </Card>
            </div>
        </div>
    );
}

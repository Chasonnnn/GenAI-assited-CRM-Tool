/**
 * MSW Request Handlers for Integration Tests
 * 
 * Define mock API responses for each endpoint.
 * These handlers intercept network requests during tests.
 */

import { http, HttpResponse } from 'msw'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

// Sample data factories
export const mockSurrogate = (overrides = {}) => ({
    id: '550e8400-e29b-41d4-a716-446655440001',
    surrogate_number: 'S10001',
    full_name: 'Jane Doe',
    email: 'jane@example.com',
    phone: '555-123-4567',
    stage_id: '550e8400-e29b-41d4-a716-446655440010',
    stage_slug: 'new_unread',
    status_label: 'New Unread',
    source: 'website',
    is_priority: false,
    is_archived: false,
    owner_type: 'user',
    owner_id: '550e8400-e29b-41d4-a716-446655440020',
    owner_name: 'John Smith',
    created_at: new Date().toISOString(),
    ...overrides,
})

export const mockUser = (overrides = {}) => ({
    user_id: '550e8400-e29b-41d4-a716-446655440020',
    email: 'test@example.com',
    display_name: 'Test User',
    avatar_url: null,
    role: 'admin',
    org_id: '550e8400-e29b-41d4-a716-446655440030',
    org_name: 'Test Organization',
    org_display_name: 'Test Organization',
    org_slug: 'test-org',
    org_timezone: 'America/Los_Angeles',
    ai_enabled: true,
    mfa_enabled: true,
    mfa_required: false,
    mfa_verified: true,
    ...overrides,
})

export const mockPermission = (overrides = {}) => ({
    key: 'view_surrogates',
    label: 'View Surrogates',
    description: 'View surrogate list and details',
    category: 'Surrogates',
    developer_only: false,
    ...overrides,
})

// Default handlers
export const handlers = [
    // Auth
    http.get(`${API_BASE}/auth/me`, () => {
        return HttpResponse.json(mockUser())
    }),

    // Surrogates
    http.get(`${API_BASE}/surrogates`, () => {
        return HttpResponse.json({
            items: [mockSurrogate(), mockSurrogate({ id: '550e8400-e29b-41d4-a716-446655440002', surrogate_number: 'S10002' })],
            total: 2,
            page: 1,
            per_page: 25,
            pages: 1,
        })
    }),

    http.get(`${API_BASE}/surrogates/:id`, ({ params }) => {
        return HttpResponse.json(mockSurrogate({ id: params.id }))
    }),

    // Permissions
    http.get(`${API_BASE}/settings/permissions/available`, () => {
        return HttpResponse.json([
            mockPermission(),
            mockPermission({ key: 'edit_surrogates', label: 'Edit Surrogates' }),
            mockPermission({ key: 'view_tasks', label: 'View Tasks', category: 'Tasks' }),
        ])
    }),

    http.get(`${API_BASE}/settings/permissions/members`, () => {
        return HttpResponse.json([
            {
                id: '550e8400-e29b-41d4-a716-446655440040',
                user_id: mockUser().user_id,
                email: mockUser().email,
                display_name: mockUser().display_name,
                role: 'admin',
                last_login_at: new Date().toISOString(),
                created_at: new Date().toISOString(),
            },
        ])
    }),

    // Dashboard
    http.get(`${API_BASE}/dashboard/summary`, () => {
        return HttpResponse.json({
            surrogates: { total: 42, this_week: 5, change_pct: 12.5 },
            tasks: { pending: 8, overdue: 2 },
            matches: { active: 3 },
        })
    }),

    // Pipelines (for stages)
    http.get(`${API_BASE}/settings/pipelines`, () => {
        return HttpResponse.json([
            {
                id: '550e8400-e29b-41d4-a716-446655440050',
                name: 'Surrogacy Intake',
                is_default: true,
                stages: [
                    { id: '550e8400-e29b-41d4-a716-446655440010', slug: 'new_lead', label: 'New Lead', order: 1 },
                    { id: '550e8400-e29b-41d4-a716-446655440011', slug: 'contacted', label: 'Contacted', order: 2 },
                ],
            },
        ])
    }),
]

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AppSidebar } from '@/components/app-sidebar'

// Mock dependencies
const mockUseRouter = {
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
}
const mockUsePathname = vi.fn()
const mockUseSearchParams = vi.fn()
const mockUseIsMobile = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => mockUseRouter,
    usePathname: () => mockUsePathname(),
    useSearchParams: () => mockUseSearchParams(),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({
        user: {
            display_name: 'Test User',
            email: 'test@example.com',
            role: 'manager',
            org_name: 'Test Org',
        },
    }),
}))

vi.mock('@/hooks/use-mobile', () => ({
    useIsMobile: () => mockUseIsMobile(),
}))

// Mock UI components that have side effects or are complex
vi.mock('@/components/notification-bell', () => ({
    NotificationBell: () => <div data-testid="notification-bell">NotificationBell</div>,
}))

vi.mock('@/components/theme-toggle', () => ({
    ThemeToggle: () => <div data-testid="theme-toggle">ThemeToggle</div>,
}))

vi.mock('@/components/search-command', () => ({
    SearchCommandDialog: () => null,
    useSearchHotkey: vi.fn(),
}))

vi.mock('@/lib/csrf', () => ({
    getCsrfHeaders: () => ({}),
}))

describe('AppSidebar Accessibility', () => {
    beforeEach(() => {
        mockUsePathname.mockReturnValue('/dashboard')
        mockUseSearchParams.mockReturnValue(new URLSearchParams())
        mockUseIsMobile.mockReturnValue(false)
    })

    it('renders user menu trigger with accessible label', () => {
        render(
            <AppSidebar>
                <div>Content</div>
            </AppSidebar>
        )

        // Find the user menu trigger button
        // Initially, we can only find it by content. After fix, we can find it by label.
        // We'll try to find it by label "User menu" and expect it to be there.
        const userMenuButton = screen.getByLabelText('User menu')
        expect(userMenuButton).toBeInTheDocument()
    })

    it('renders collapsible navigation items with aria-expanded attribute', () => {
        render(
            <AppSidebar>
                <div>Content</div>
            </AppSidebar>
        )

        // Find the "Tasks & Scheduling" button
        const tasksButton = screen.getByText('Tasks & Scheduling').closest('button')
        expect(tasksButton).toHaveAttribute('aria-expanded', 'false')

        // Find the "Automation" button
        const automationButton = screen.getByText('Automation').closest('button')
        expect(automationButton).toHaveAttribute('aria-expanded', 'false')

        // Find the "Settings" button
        const settingsButton = screen.getByText('Settings').closest('button')
        expect(settingsButton).toHaveAttribute('aria-expanded', 'false')

        // Click to expand and check attribute change
        fireEvent.click(tasksButton!)
        expect(tasksButton).toHaveAttribute('aria-expanded', 'true')
    })
})

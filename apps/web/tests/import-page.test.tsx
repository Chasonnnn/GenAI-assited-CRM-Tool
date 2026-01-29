import type { ReactNode, ButtonHTMLAttributes } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CSVImportPage from '../app/(app)/surrogates/import/page'

const mockUseImports = vi.fn()
const mockUseImportDetails = vi.fn()
const mockCancelImport = vi.fn()
const mockRetryImport = vi.fn()
const mockRunInlineImport = vi.fn()

vi.mock('@/components/import/CSVUpload', () => ({
    CSVUpload: () => <div>CSV Upload</div>,
}))

// Simplify Base UI dropdowns/dialogs to avoid portal/focus issues in tests.
vi.mock('@/components/ui/dropdown-menu', () => ({
    DropdownMenu: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({
        children,
        render,
        ...props
    }: { children?: ReactNode; render?: (props: ButtonHTMLAttributes<HTMLButtonElement>) => ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) => {
        if (render) {
            return <>{render({ ...props })}</>
        }
        return (
            <button type="button" {...props}>
                {children}
            </button>
        )
    },
    DropdownMenuContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({
        children,
        onClick,
        onSelect,
        ...props
    }: {
        children?: ReactNode
        onClick?: () => void
        onSelect?: () => void
    }) => (
        <button
            type="button"
            onClick={() => {
                onClick?.()
                onSelect?.()
            }}
            {...props}
        >
            {children}
        </button>
    ),
}))

vi.mock('@/components/ui/dialog', () => ({
    Dialog: ({ open, children }: { open?: boolean; children?: ReactNode }) =>
        open ? <div>{children}</div> : null,
    DialogContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'admin', user_id: 'u1' } }),
}))

vi.mock('@/lib/hooks/use-import', () => ({
    useImports: () => mockUseImports(),
    useImportDetails: (importId: string | null) => mockUseImportDetails(importId),
    useCancelImport: () => ({ mutateAsync: mockCancelImport, isPending: false }),
    useRetryImport: () => ({ mutateAsync: mockRetryImport, isPending: false }),
    useRunImportInline: () => ({ mutateAsync: mockRunInlineImport, isPending: false }),
}))

describe('CSVImportPage', () => {
    const baseImport = {
        id: 'import-1',
        filename: 'surrogates.csv',
        status: 'completed',
        total_rows: 10,
        imported_count: 8,
        skipped_count: 0,
        error_count: 2,
        created_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
    }

    beforeEach(() => {
        mockUseImports.mockReturnValue({
            data: [baseImport],
            isLoading: false,
            refetch: vi.fn(),
        })
        mockUseImportDetails.mockImplementation((importId: string | null) => ({
            data: importId
                ? {
                    ...baseImport,
                    errors: [
                        { row: 3, errors: ['Email is required'] },
                        { row: 5, errors: ['Invalid phone number'] },
                    ],
                }
                : undefined,
            isLoading: false,
            isError: false,
        }))
        mockCancelImport.mockReset()
        mockRetryImport.mockReset()
        mockRunInlineImport.mockReset()
    })

    it('shows errored rows and reasons when viewing errors', () => {
        render(<CSVImportPage />)

        fireEvent.click(screen.getByRole('button', { name: /view errors/i }))

        expect(screen.getByText('Import errors')).toBeInTheDocument()
        expect(screen.getByText('Row 3')).toBeInTheDocument()
        expect(screen.getByText('Email is required')).toBeInTheDocument()
        expect(screen.getByText('Row 5')).toBeInTheDocument()
        expect(screen.getByText('Invalid phone number')).toBeInTheDocument()
    })
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VersionHistoryModal } from '../components/version-history-modal'

vi.mock('@/components/ui/dialog', () => ({
    Dialog: ({ open, children }: any) => (open ? <div>{children}</div> : null),
    DialogContent: ({ children }: any) => <div>{children}</div>,
    DialogDescription: ({ children }: any) => <div>{children}</div>,
    DialogHeader: ({ children }: any) => <div>{children}</div>,
    DialogTitle: ({ children }: any) => <h2>{children}</h2>,
}))

vi.mock('@/components/ui/alert-dialog', () => ({
    AlertDialog: ({ children }: any) => <div>{children}</div>,
    AlertDialogTrigger: ({ children }: any) => <div>{children}</div>,
    AlertDialogContent: ({ children }: any) => <div>{children}</div>,
    AlertDialogHeader: ({ children }: any) => <div>{children}</div>,
    AlertDialogTitle: ({ children }: any) => <div>{children}</div>,
    AlertDialogDescription: ({ children }: any) => <div>{children}</div>,
    AlertDialogFooter: ({ children }: any) => <div>{children}</div>,
    AlertDialogCancel: ({ children }: any) => <button type="button">{children}</button>,
    AlertDialogAction: ({ children, onClick, disabled }: any) => (
        <button type="button" onClick={onClick} disabled={disabled}>
            {children}
        </button>
    ),
}))

describe('VersionHistoryModal', () => {
    it('shows rollback affordance only when allowed', () => {
        const onRollback = vi.fn()

        render(
            <VersionHistoryModal
                open
                onOpenChange={() => {}}
                title="Default Pipeline"
                entityType="pipeline"
                currentVersion={2}
                canRollback
                onRollback={onRollback}
                versions={[
                    {
                        id: 'v1',
                        version: 1,
                        payload: { stages: [{ label: 'New' }, { label: 'Contacted' }] },
                        comment: 'init',
                        created_by_user_id: null,
                        created_at: new Date().toISOString(),
                    },
                    {
                        id: 'v2',
                        version: 2,
                        payload: { stages: [{ label: 'New' }] },
                        comment: null,
                        created_by_user_id: null,
                        created_at: new Date().toISOString(),
                    },
                ]}
            />
        )

        expect(screen.getByText(/Current version: 2/i)).toBeInTheDocument()
        expect(screen.getAllByText(/rollback/i).length).toBeGreaterThan(0)

        fireEvent.click(screen.getByRole('button', { name: /confirm rollback/i }))
        expect(onRollback).toHaveBeenCalledWith(1)
    })

    it('hides rollback when canRollback is false', () => {
        render(
            <VersionHistoryModal
                open
                onOpenChange={() => {}}
                title="Template"
                entityType="email_template"
                currentVersion={1}
                canRollback={false}
                versions={[
                    {
                        id: 'v1',
                        version: 1,
                        payload: { subject: 'Hi' },
                        comment: null,
                        created_by_user_id: null,
                        created_at: new Date().toISOString(),
                    },
                ]}
            />
        )

        expect(screen.queryByText(/rollback/i)).not.toBeInTheDocument()
    })
})


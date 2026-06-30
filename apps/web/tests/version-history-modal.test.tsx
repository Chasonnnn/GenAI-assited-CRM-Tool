import type { PropsWithChildren } from "react"
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VersionHistoryModal } from '../components/version-history-modal'

const FIXED_CREATED_AT = "2026-01-01T00:00:00.000Z"

vi.mock('@/components/ui/dialog', () => ({
    Dialog: ({ open, children }: PropsWithChildren<{ open?: boolean }>) => (open ? <div>{children}</div> : null),
    DialogContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogDescription: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogHeader: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogTitle: ({ children }: PropsWithChildren) => <h2>{children}</h2>,
}))

vi.mock('@/components/ui/alert-dialog', () => ({
    AlertDialog: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AlertDialogTrigger: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AlertDialogContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AlertDialogHeader: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AlertDialogTitle: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AlertDialogDescription: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AlertDialogFooter: ({ children }: PropsWithChildren) => <div>{children}</div>,
    AlertDialogCancel: ({ children }: PropsWithChildren) => <button type="button">{children}</button>,
    AlertDialogAction: ({ children, onClick, disabled }: PropsWithChildren<{ onClick?: () => void; disabled?: boolean }>) => (
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
                        created_at: FIXED_CREATED_AT,
                    },
                    {
                        id: 'v2',
                        version: 2,
                        payload: { stages: [{ label: 'New' }] },
                        comment: null,
                        created_by_user_id: null,
                        created_at: FIXED_CREATED_AT,
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
                        created_at: FIXED_CREATED_AT,
                    },
                ]}
            />
        )

        expect(screen.queryByText(/rollback/i)).not.toBeInTheDocument()
    })

    it('labels expandable version details and exposes expanded state', () => {
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
                        created_at: FIXED_CREATED_AT,
                    },
                ]}
            />
        )

        const expandButton = screen.getByRole('button', { name: /expand details/i })
        expect(expandButton).toHaveAttribute('aria-expanded', 'false')
        expect(expandButton.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')

        fireEvent.click(expandButton)

        const collapseButton = screen.getByRole('button', { name: /collapse details/i })
        expect(collapseButton).toHaveAttribute('aria-expanded', 'true')
        expect(collapseButton.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    })
})

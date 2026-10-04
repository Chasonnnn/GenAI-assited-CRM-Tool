import type { PropsWithChildren, ReactNode } from "react"
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import WorkflowEditorPageClient from '../app/(app)/automation/workflows/[id]/page.client'
import { ApiError } from '@/lib/api'
import { getApplicantTypeLabel } from '@/components/automation/workflow-editor/shared'
import { getWorkflowEditorPreset } from '@/lib/workflows/workflow-editor-state'

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/hooks/use-permissions', () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }))
vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: vi.fn(() => null),
    }),
    usePathname: () => '/automation/workflows/new',
    useRouter: () => ({
        push: mockPush,
        replace: vi.fn(),
        back: vi.fn(),
        prefetch: vi.fn(),
    }),
}))

vi.mock('@/hooks/use-media-query', () => ({
    useMediaQuery: () => false,
}))

// Render tooltip content inline so a disabled save button's reason is assertable.
vi.mock('@/components/ui/tooltip', async () => {
    const React = await import('react')
    return {
        Tooltip: ({ children }: PropsWithChildren) => <>{children}</>,
        TooltipTrigger: ({ render, children }: { render?: ReactNode; children?: ReactNode }) =>
            React.isValidElement(render)
                ? React.cloneElement(render as React.ReactElement<{ children?: ReactNode }>, {}, children)
                : <>{children}</>,
        TooltipContent: ({ children }: PropsWithChildren) => <span data-testid="tooltip">{children}</span>,
    }
})

// Simplify Base UI pickers for deterministic tests: native select, radios, and buttons.
vi.mock('@/components/ui/select', () => ({
    Select: ({
        value,
        onValueChange,
        children,
        disabled,
        "aria-label": ariaLabel,
    }: PropsWithChildren<{
        value?: string
        onValueChange: (value: string) => void
        disabled?: boolean
        "aria-label"?: string
    }>) => (
        <select
            data-testid="select"
            value={value ?? ''}
            onChange={(e) => onValueChange(e.target.value)}
            disabled={disabled}
            aria-label={ariaLabel}
        >
            <option value="">Select</option>
            {children}
        </select>
    ),
    SelectTrigger: () => null,
    SelectValue: () => null,
    SelectContent: ({ children }: PropsWithChildren) => <>{children}</>,
    SelectItem: ({ value, children }: PropsWithChildren<{ value: string }>) => <option value={value}>{children}</option>,
}))

vi.mock('@/components/ui/radio-group', async () => {
    const React = await import('react')
    const RadioContext = React.createContext<{
        value?: string | undefined
        onValueChange?: ((value: string) => void) | undefined
        disabled?: boolean | undefined
    }>({})
    return {
        RadioGroup: ({
            value,
            onValueChange,
            children,
            disabled,
            "aria-label": ariaLabel,
        }: PropsWithChildren<{
            value?: string
            onValueChange?: (value: string) => void
            disabled?: boolean
            "aria-label"?: string
        }>) => (
            <RadioContext.Provider value={{ value, onValueChange, disabled }}>
                <div role="radiogroup" aria-label={ariaLabel} aria-disabled={disabled || undefined}>{children}</div>
            </RadioContext.Provider>
        ),
        RadioGroupItem: ({ value, "aria-label": ariaLabel }: { value: string; "aria-label"?: string }) => {
            const context = React.useContext(RadioContext)
            return (
                <input
                    type="radio"
                    aria-label={ariaLabel}
                    value={value}
                    checked={context.value === value}
                    disabled={context.disabled}
                    onChange={() => context.onValueChange?.(value)}
                />
            )
        },
    }
})

vi.mock('@/components/ui/toggle-group', async () => {
    const React = await import('react')
    const ToggleContext = React.createContext<{ value?: string[] | undefined; onValueChange?: ((value: string[]) => void) | undefined }>({})
    return {
        ToggleGroup: ({
            value,
            onValueChange,
            children,
            "aria-label": ariaLabel,
        }: PropsWithChildren<{ value?: string[]; onValueChange?: (value: string[]) => void; "aria-label"?: string }>) => (
            <ToggleContext.Provider value={{ value, onValueChange }}>
                <div role="group" aria-label={ariaLabel}>{children}</div>
            </ToggleContext.Provider>
        ),
        ToggleGroupItem: ({
            value,
            children,
            "aria-label": ariaLabel,
        }: PropsWithChildren<{ value: string; "aria-label"?: string }>) => {
            const context = React.useContext(ToggleContext)
            return (
                <button
                    type="button"
                    aria-label={ariaLabel}
                    aria-pressed={context.value?.includes(value) ?? false}
                    onClick={() => context.onValueChange?.([value])}
                >
                    {children}
                </button>
            )
        },
    }
})

const mockUseWorkflow = vi.fn()
const mockUseWorkflowOptions = vi.fn()
const mockCreateWorkflow = { mutate: vi.fn(), isPending: false }
const mockUpdateWorkflow = { mutate: vi.fn(), isPending: false }

vi.mock('@/lib/hooks/use-workflows', () => ({
    useWorkflow: (...args: unknown[]) => mockUseWorkflow(...args),
    useWorkflowOptions: (...args: unknown[]) => mockUseWorkflowOptions(...args),
    useCreateWorkflow: () => mockCreateWorkflow,
    useUpdateWorkflow: () => mockUpdateWorkflow,
}))

function getFirstElement<T>(items: T[], message: string): T {
    const item = items[0]
    if (!item) {
        throw new Error(message)
    }
    return item
}

const DEFAULT_OPTIONS = {
    trigger_types: [
        { value: 'surrogate_created', label: 'Surrogate Created', description: '' },
        { value: 'scheduled', label: 'Scheduled', description: '' },
        { value: 'task_due', label: 'Task Due', description: '' },
    ],
    action_types: [
        { value: 'add_note', label: 'Add Note', description: '' },
    ],
    action_types_by_trigger: {
        surrogate_created: ['add_note'],
        scheduled: ['add_note'],
        task_due: ['add_note'],
    },
    trigger_entity_types: {
        surrogate_created: 'surrogate',
        scheduled: 'surrogate',
        task_due: 'task',
    },
    condition_fields: [],
    condition_operators: [],
    update_fields: [],
    email_variables: [],
    email_templates: [],
    users: [],
    queues: [],
    statuses: [],
}

function renderNewWorkflow(scope: 'personal' | 'org' = 'personal') {
    return render(<WorkflowEditorPageClient workflowId={null} initialScope={scope} />)
}

function renderExistingWorkflow(workflowId: string) {
    return render(<WorkflowEditorPageClient workflowId={workflowId} initialScope="personal" />)
}

const nameInput = () => screen.getByRole('textbox', { name: 'Workflow name' })
const triggerSelect = () => screen.getByRole('combobox', { name: 'Trigger type' })
const launchButton = () => screen.getByRole('button', { name: 'Launch workflow' })
const saveChangesButton = () => screen.getByRole('button', { name: 'Save changes' })

const chooseRecordType = (label: string) => {
    fireEvent.click(screen.getByRole('radio', { name: label }))
}

const radioLabels = (groupName: string) =>
    Array.from(screen.getByRole('radiogroup', { name: groupName }).querySelectorAll('label')).map(
        (label) => label.textContent,
    )

const formSelect = (formId: string) =>
    getFirstElement(
        screen.getAllByTestId('select').filter((select) =>
            select.querySelector(`option[value="${formId}"]`),
        ),
        'Expected a form select',
    )

const optionLabels = (select: HTMLElement) =>
    Array.from(select.querySelectorAll('option'))
        .filter((option) => option.value)
        .map((option) => option.textContent)

/** Adds a blank action from the canvas and picks its type in the inspector. */
const addActionOfType = (actionType: string, position = 1) => {
    fireEvent.click(screen.getByRole('button', { name: 'Add action' }))
    fireEvent.change(screen.getByRole('combobox', { name: `Action type ${position}` }), {
        target: { value: actionType },
    })
}

const addNoteAction = (content: string) => {
    addActionOfType('add_note')
    fireEvent.change(screen.getByRole('textbox', { name: 'Note content' }), { target: { value: content } })
}

describe('WorkflowEditorPage', () => {
    beforeEach(() => {
        mockUseAuth.mockReturnValue({ user: { role: 'admin' } })
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: [] } })
        mockUseWorkflow.mockReset()
        mockUseWorkflow.mockReturnValue({ data: null, isLoading: false })
        mockUseWorkflowOptions.mockReset()
        mockUseWorkflowOptions.mockReturnValue({ data: DEFAULT_OPTIONS, isLoading: false })
        mockPush.mockReset()
        mockCreateWorkflow.mutate.mockReset()
        mockUpdateWorkflow.mutate.mockReset()
    })

    it('renders the trigger and exit nodes with the trigger panel and build palette', () => {
        renderNewWorkflow()

        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Every matching record')
        expect(screen.getByText('Exit')).toBeInTheDocument()
        expect(radioLabels('Trigger kind')).toEqual(['Trigger event', 'Date or scheduled'])
        expect(screen.getByRole('button', { name: 'Add filter' })).toBeInTheDocument()
        expect(screen.getByTestId('workflow-build-panel')).toHaveTextContent('Add Note')
        expect(screen.getByText('Draft')).toBeInTheDocument()
    })

    it('adds a typed action from the build palette and selects it', () => {
        renderNewWorkflow()

        fireEvent.click(screen.getByRole('button', { name: 'Add Note' }))

        expect(screen.getByRole('combobox', { name: 'Action type 1' })).toHaveValue('add_note')
        expect(screen.getByRole('button', { name: 'Action 1: Add Note' })).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveAttribute('aria-pressed', 'false')
    })

    it('labels every Create Task field visibly', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                action_types: [{ value: 'create_task', label: 'Create Task', description: '' }],
                action_types_by_trigger: { surrogate_created: ['create_task'] },
            },
            isLoading: false,
        })

        renderNewWorkflow()
        fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
        fireEvent.click(screen.getByRole('button', { name: 'Create Task' }))

        const settings = screen.getByRole('complementary', { name: 'Action settings' })
        for (const label of ['Task title', 'Task description', 'Due in days', 'Assignee']) {
            expect(within(settings).getByText(label, { selector: 'label' })).toBeInTheDocument()
        }
        expect(screen.getByRole('spinbutton', { name: 'Due in days' })).toHaveValue(1)
    })

    it('blocks launching an incomplete workflow and names the reason', () => {
        renderNewWorkflow()

        expect(launchButton()).toHaveAttribute('aria-disabled', 'true')
        expect(screen.getAllByTestId('tooltip').map((tip) => tip.textContent)).toEqual([
            'Workflow name is required.',
            'Workflow name is required.',
        ])
        fireEvent.click(launchButton())
        expect(mockCreateWorkflow.mutate).not.toHaveBeenCalled()

        fireEvent.change(nameInput(), { target: { value: 'Named' } })
        expect(screen.getAllByTestId('tooltip').map((tip) => tip.textContent)).toEqual([
            'Trigger type is required.',
            'Trigger type is required.',
        ])
    })

    it('shows server validation errors', () => {
        mockCreateWorkflow.mutate.mockImplementation((_data: unknown, opts?: { onError?: (err: Error) => void }) => {
            opts?.onError?.(
                new ApiError(422, 'Unprocessable Entity', 'Action 1: title is required; Action 1: assignee is required'),
            )
        })

        renderNewWorkflow()

        fireEvent.change(nameInput(), { target: { value: 'Test Workflow' } })
        fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
        addNoteAction('Test note')
        fireEvent.click(launchButton())

        expect(screen.getByText(/fix these errors/i)).toBeInTheDocument()
        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()
        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({ is_enabled: true, scope: 'personal' }),
            expect.any(Object),
        )
    })

    it('saves a draft with the workflow disabled', () => {
        renderNewWorkflow()

        fireEvent.change(nameInput(), { target: { value: 'Draft Workflow' } })
        fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
        addNoteAction('Draft note')
        fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({ name: 'Draft Workflow', is_enabled: false }),
            expect.any(Object),
        )
    })

    it('shows one plain message when saving an org workflow is forbidden', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_automation'] },
        })
        mockCreateWorkflow.mutate.mockImplementation((_data: unknown, opts?: { onError?: (err: Error) => void }) => {
            opts?.onError?.(
                new ApiError(403, 'Forbidden', 'Cannot create org workflows without manage_automation permission'),
            )
        })

        renderNewWorkflow('org')

        expect(screen.getByRole('link', { name: 'Org Workflows' })).toBeInTheDocument()
        fireEvent.change(nameInput(), { target: { value: 'Org Workflow' } })
        fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
        addNoteAction('Note')
        fireEvent.click(launchButton())

        expect(
            screen.getByText("You don't have permission to create organization workflows"),
        ).toBeInTheDocument()
        expect(screen.queryByText(/manage_automation/)).not.toBeInTheDocument()
        expect(screen.queryByText(/fix these errors/i)).not.toBeInTheDocument()
    })

    it('denies org workflow creation without manage_automation', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: [] } })

        renderNewWorkflow('org')

        expect(screen.getByText('No access to this workflow')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Launch workflow' })).not.toBeInTheDocument()
    })

    it('clears server validation errors when condition logic changes', () => {
        mockCreateWorkflow.mutate.mockImplementation(
            (_data: unknown, opts?: { onError?: (err: Error) => void }) => {
                opts?.onError?.(
                    new Error('Action 1: title is required; Action 1: assignee is required'),
                )
            },
        )

        renderNewWorkflow()

        fireEvent.change(nameInput(), { target: { value: 'Conditional Workflow' } })
        fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })

        fireEvent.click(screen.getByRole('button', { name: 'Add filter' }))
        fireEvent.click(screen.getByRole('button', { name: 'Add filter' }))
        expect(screen.getAllByRole('button', { name: 'Remove condition' })).toHaveLength(2)
        expect(screen.getByRole('radio', { name: 'All filters match' })).toBeChecked()

        addNoteAction('Record the condition result')
        fireEvent.click(launchButton())
        expect(mockCreateWorkflow.mutate).toHaveBeenCalledTimes(1)
        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Trigger step' }))
        fireEvent.click(screen.getByRole('radio', { name: 'Any filter matches' }))

        expect(screen.queryByText(/Action 1: title is required/i)).not.toBeInTheDocument()
        expect(screen.getByRole('radio', { name: 'Any filter matches' })).toBeChecked()
    })

    it('preserves server errors when late status options only normalize legacy config', () => {
        const initialOptions = {
            ...DEFAULT_OPTIONS,
            trigger_types: [
                { value: 'status_changed', label: 'Status Changed', description: '' },
            ],
            action_types_by_trigger: {
                status_changed: ['add_note'],
            },
            trigger_entity_types: {
                status_changed: 'surrogate',
            },
        }
        mockUseWorkflowOptions.mockReturnValue({
            data: initialOptions,
            isLoading: false,
        })
        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-legacy',
                name: 'Legacy Status Workflow',
                description: null,
                scope: 'personal',
                trigger_type: 'status_changed',
                trigger_config: { to_status: 'qualified' },
                conditions: [],
                condition_logic: 'AND',
                actions: [
                    {
                        action_type: 'add_note',
                        content: 'Record status change',
                    },
                ],
            },
            isLoading: false,
        })
        mockUpdateWorkflow.mutate.mockImplementation(
            (_data: unknown, opts?: { onError?: (err: Error) => void }) => {
                opts?.onError?.(
                    new Error('Action 1: title is required; Action 1: assignee is required'),
                )
            },
        )

        const view = renderExistingWorkflow('workflow-legacy')

        expect(screen.getByDisplayValue('Legacy Status Workflow')).toBeInTheDocument()
        fireEvent.click(saveChangesButton())
        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()

        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...initialOptions,
                statuses: [
                    {
                        id: 'stage-qualified',
                        value: 'qualified',
                        label: 'Qualified',
                    },
                ],
            },
            isLoading: false,
        })
        view.rerender(<WorkflowEditorPageClient workflowId="workflow-legacy" initialScope="personal" />)

        expect(screen.getByText(/Action 1: title is required/i)).toBeInTheDocument()
    })

    it('waits for the selected workflow response before hydrating the edit draft', () => {
        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-a',
                name: 'Stale Workflow A',
                description: null,
                scope: 'personal',
                trigger_type: 'surrogate_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [],
            },
            isLoading: false,
        })

        const view = renderExistingWorkflow('workflow-b')

        expect(screen.getByRole('status')).toHaveTextContent('Loading workflow')
        expect(screen.queryByDisplayValue('Stale Workflow A')).not.toBeInTheDocument()

        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-b',
                name: 'Selected Workflow B',
                description: null,
                scope: 'personal',
                trigger_type: 'surrogate_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [],
            },
            isLoading: false,
        })
        view.rerender(<WorkflowEditorPageClient workflowId="workflow-b" initialScope="personal" />)

        expect(screen.getByDisplayValue('Selected Workflow B')).toBeInTheDocument()
        expect(screen.queryByDisplayValue('Stale Workflow A')).not.toBeInTheDocument()
    })

    it('denies editing a workflow the viewer cannot change', () => {
        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-locked',
                name: 'Locked workflow',
                description: null,
                scope: 'org',
                trigger_type: 'surrogate_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [],
                can_edit: false,
            },
            isLoading: false,
        })

        renderExistingWorkflow('workflow-locked')

        expect(screen.getByText('No access to this workflow')).toBeInTheDocument()
        expect(screen.queryByDisplayValue('Locked workflow')).not.toBeInTheDocument()
    })

    it('submits only the configuration for the selected trigger type', () => {
        renderNewWorkflow()

        fireEvent.change(nameInput(), { target: { value: 'Task Due Reminder' } })

        expect(optionLabels(triggerSelect())).toEqual(['Surrogate Created'])
        fireEvent.click(screen.getByRole('radio', { name: 'Date or scheduled' }))
        expect(optionLabels(triggerSelect())).toEqual(['Scheduled', 'Task Due'])

        fireEvent.change(triggerSelect(), { target: { value: 'scheduled' } })
        fireEvent.click(screen.getByRole('radio', { name: 'Custom cron' }))
        fireEvent.change(screen.getByPlaceholderText('0 9 * * 1'), {
            target: { value: '0 8 * * *' },
        })
        fireEvent.change(screen.getByPlaceholderText('America/Los_Angeles'), {
            target: { value: 'America/New_York' },
        })
        expect(screen.getByRole('radio', { name: 'Custom cron' })).toBeChecked()
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Every day at 08:00')

        fireEvent.change(triggerSelect(), { target: { value: 'task_due' } })
        fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '48' } })
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('48 hours before due')

        addNoteAction('Task is due soon')
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                trigger_type: 'task_due',
                trigger_config: { hours_before: 48 },
            }),
            expect.any(Object),
        )
    })

    it.each([
        { policyVersion: 1, permissions: [], labels: ['Surrogate'] },
        { policyVersion: 1, permissions: ['view_donors'], labels: ['Surrogate'] },
        {
            policyVersion: 1,
            permissions: ['view_donors', 'edit_donors'],
            labels: ['Surrogate', 'Egg Donor', 'Sperm Donor'],
        },
        { policyVersion: 2, permissions: ['manage_automation'], labels: ['Surrogate'] },
        {
            policyVersion: 2,
            permissions: ['manage_automation', 'view_donors'],
            labels: ['Surrogate', 'Egg Donor', 'Sperm Donor'],
        },
    ])('offers donor record types only with the donor create permission (v$policyVersion, $permissions)', ({ policyVersion, permissions, labels }) => {
        mockUseEffectivePermissions.mockReturnValue({ data: { policy_version: policyVersion, permissions } })

        renderNewWorkflow()

        expect(radioLabels('Record type')).toEqual(labels)
    })

    it('creates an egg donor workflow from subject-specific options', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: subjectType === 'egg_donor'
                    ? {
                        ...DEFAULT_OPTIONS,
                        trigger_types: [
                            { value: 'donor_created', label: 'Donor Created', description: '' },
                        ],
                        action_types_by_trigger: { donor_created: ['add_note'] },
                        trigger_entity_types: { donor_created: 'egg_donor' },
                        condition_fields: ['education'],
                        update_fields: ['education'],
                    }
                    : {
                        ...DEFAULT_OPTIONS,
                        trigger_types: [
                            { value: 'surrogate_created', label: 'Surrogate Created', description: '' },
                        ],
                        action_types_by_trigger: { surrogate_created: ['add_note'] },
                        trigger_entity_types: { surrogate_created: 'surrogate' },
                    },
                isLoading: false,
            }),
        )

        renderNewWorkflow()

        chooseRecordType('Egg Donor')
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Runs for egg donors')
        fireEvent.change(nameInput(), { target: { value: 'Egg donor welcome' } })
        fireEvent.change(triggerSelect(), { target: { value: 'donor_created' } })
        addNoteAction('Welcome call requested')
        fireEvent.click(launchButton())

        expect(mockUseWorkflowOptions).toHaveBeenCalledWith('personal', 'egg_donor')
        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                trigger_type: 'donor_created',
            }),
            expect.any(Object),
        )
    })

    it('offers only canonical donor sources for an Update Field source action', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['view_donors', 'edit_donors'] },
        })
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [
                    { value: 'donor_created', label: 'Donor Created', description: '' },
                ],
                action_types: [
                    { value: 'update_field', label: 'Update Field', description: '' },
                ],
                action_types_by_trigger: { donor_created: ['update_field'] },
                trigger_entity_types: { donor_created: 'egg_donor' },
                update_fields: ['source', 'education'],
            },
            isLoading: false,
        })

        renderNewWorkflow()
        chooseRecordType('Egg Donor')
        fireEvent.change(nameInput(), { target: { value: 'Set donor source' } })
        fireEvent.change(triggerSelect(), { target: { value: 'donor_created' } })
        fireEvent.click(screen.getByRole('button', { name: 'Update Field' }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Field to update 1' }), {
            target: { value: 'source' },
        })

        expect(screen.queryByRole('textbox', { name: 'Value' })).not.toBeInTheDocument()
        const sourceSelect = screen.getByRole('combobox', { name: 'Source value 1' })
        const sourceOptions = Array.from(sourceSelect.querySelectorAll('option'))
            .filter((option) => option.value)
            .map((option) => [option.value, option.textContent])
        expect(sourceOptions).toEqual([
            ['manual', 'Manual'],
            ['meta', 'Meta'],
            ['tiktok', 'TikTok'],
            ['google', 'Google'],
            ['website', 'Website'],
            ['referral', 'Referral'],
            ['agency', 'Agency'],
            ['import', 'Import'],
            ['other', 'Other'],
        ])
        fireEvent.change(sourceSelect, { target: { value: 'tiktok' } })
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                actions: [expect.objectContaining({
                    action_type: 'update_field',
                    field: 'source',
                    value: 'tiktok',
                })],
            }),
            expect.any(Object),
        )
    })

    it('keeps an existing donor workflow subject visible and immutable', () => {
        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-egg',
                name: 'Egg donor follow-up',
                description: null,
                scope: 'personal',
                subject_type: 'egg_donor',
                trigger_type: 'donor_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [{ action_type: 'add_note', content: 'Call donor' }],
                is_enabled: true,
            },
            isLoading: false,
        })

        renderExistingWorkflow('workflow-egg')

        expect(screen.getByDisplayValue('Egg donor follow-up')).toBeInTheDocument()
        expect(radioLabels('Record type')).toEqual(['Egg Donor'])
        expect(screen.getByRole('radio', { name: 'Egg Donor' })).toBeDisabled()
        expect(screen.getByText('Enabled')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Runs for egg donors')
    })

    it('configures the returned assign-donor action without surrogate controls', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: {
                    ...DEFAULT_OPTIONS,
                    trigger_types: subjectType === 'sperm_donor'
                        ? [{ value: 'donor_created', label: 'Donor Created', description: '' }]
                        : [{ value: 'surrogate_created', label: 'Surrogate Created', description: '' }],
                    action_types: subjectType === 'sperm_donor'
                        ? [{ value: 'assign_donor', label: 'Assign Donor', description: '' }]
                        : [{ value: 'assign_surrogate', label: 'Assign Surrogate', description: '' }],
                    action_types_by_trigger: subjectType === 'sperm_donor'
                        ? { donor_created: ['assign_donor'] }
                        : { surrogate_created: ['assign_surrogate'] },
                    trigger_entity_types: subjectType === 'sperm_donor'
                        ? { donor_created: 'sperm_donor' }
                        : { surrogate_created: 'surrogate' },
                    users: [{ id: 'user-1', display_name: 'Alex Owner' }],
                },
                isLoading: false,
            }),
        )

        renderNewWorkflow()
        chooseRecordType('Sperm Donor')
        fireEvent.change(nameInput(), { target: { value: 'Assign sperm donor' } })
        fireEvent.change(triggerSelect(), { target: { value: 'donor_created' } })
        expect(screen.getByTestId('workflow-build-panel')).toHaveTextContent('Assign Donor')
        expect(screen.getByTestId('workflow-build-panel')).not.toHaveTextContent('Assign Surrogate')
        addActionOfType('assign_donor')

        expect(screen.getByRole('option', { name: 'Assign Donor' })).toBeInTheDocument()
        expect(screen.queryByRole('option', { name: 'Assign Surrogate' })).not.toBeInTheDocument()
        fireEvent.change(screen.getByRole('combobox', { name: 'Assignment owner type' }), {
            target: { value: 'user' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Assignment owner' }), {
            target: { value: 'user-1' },
        })
        expect(screen.getByRole('button', { name: 'Action 1: Assign Donor' })).toHaveTextContent('Alex Owner')
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'sperm_donor',
                actions: [{
                    action_type: 'assign_donor',
                    owner_type: 'user',
                    owner_id: 'user-1',
                }],
            }),
            expect.any(Object),
        )
    })

    it('configures a returned donor messaging action with mandatory approval', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: {
                    ...DEFAULT_OPTIONS,
                    trigger_types: subjectType === 'egg_donor'
                        ? [{ value: 'donor_created', label: 'Donor Created', description: '' }]
                        : [{ value: 'surrogate_created', label: 'Surrogate Created', description: '' }],
                    action_types: [{ value: 'send_message', label: 'Send SMS/MMS', description: '' }],
                    action_types_by_trigger: subjectType === 'egg_donor'
                        ? { donor_created: ['send_message'] }
                        : { surrogate_created: ['send_message'] },
                    trigger_entity_types: subjectType === 'egg_donor'
                        ? { donor_created: 'egg_donor' }
                        : { surrogate_created: 'surrogate' },
                    message_templates: [{
                        id: 'message-template-1',
                        name: 'Screening reminder',
                        purpose: 'operational',
                        version: 2,
                    }],
                },
                isLoading: false,
            }),
        )

        renderNewWorkflow()
        chooseRecordType('Egg Donor')
        fireEvent.change(nameInput(), { target: { value: 'Egg donor SMS reminder' } })
        fireEvent.change(triggerSelect(), { target: { value: 'donor_created' } })
        fireEvent.click(screen.getByRole('button', { name: 'Send SMS/MMS' }))
        fireEvent.change(screen.getByRole('combobox', { name: 'Message purpose' }), {
            target: { value: 'operational' },
        })
        fireEvent.change(screen.getByRole('combobox', { name: 'Message template' }), {
            target: { value: 'message-template-1' },
        })
        expect(screen.getByRole('switch', { name: 'Requires Approval' }))
            .toHaveAttribute('aria-disabled', 'true')
        expect(screen.getByRole('button', { name: 'Action 1: Send SMS/MMS' })).toHaveTextContent('Requires approval')
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                actions: [{
                    action_type: 'send_message',
                    purpose: 'operational',
                    message_template_version_id: 'message-template-1',
                    requires_approval: true,
                }],
            }),
            expect.any(Object),
        )
    })

    it('saves an appointment workflow for donor-linked bookings of chosen types', () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ['manage_automation', 'view_donors', 'edit_donors'] },
        })
        mockUseWorkflowOptions.mockImplementation((_scope: string, subjectType: string) => ({
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [
                    { value: 'appointment_scheduled', label: 'Appointment Scheduled', description: '' },
                ],
                action_types: [
                    { value: 'send_message', label: 'Send SMS/MMS', description: '' },
                    { value: 'send_notification', label: 'Send Notification', description: '' },
                ],
                action_types_by_trigger: { appointment_scheduled: ['send_message', 'send_notification'] },
                trigger_entity_types: { appointment_scheduled: 'appointment' },
                appointment_type_names: subjectType === 'egg_donor' ? [] : ['Consultation', 'Medical Screening'],
            },
            isLoading: false,
        }))

        renderNewWorkflow('org')
        fireEvent.change(nameInput(), { target: { value: 'Donor consult booked' } })
        fireEvent.change(triggerSelect(), { target: { value: 'appointment_scheduled' } })

        expect(radioLabels('Linked record')).toEqual(['Surrogate', 'Egg Donor', 'Sperm Donor'])
        expect(screen.getByRole('radio', { name: 'Surrogate' })).toBeChecked()
        expect(screen.getByTestId('workflow-build-panel')).toHaveTextContent('Send SMS/MMS')

        fireEvent.click(screen.getByRole('radio', { name: 'Egg Donor' }))
        expect(mockUseWorkflowOptions).toHaveBeenCalledWith('org', 'egg_donor')
        expect(screen.getByTestId('workflow-build-panel')).not.toHaveTextContent('Send SMS/MMS')
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Runs on linked egg donors')

        const typeSelect = screen.getByRole('combobox', { name: 'Appointment types' })
        fireEvent.change(typeSelect, { target: { value: 'Consultation' } })
        expect(optionLabels(typeSelect)).toEqual(['Medical Screening'])
        expect(screen.getByRole('button', { name: 'Remove Consultation' })).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Send Notification' }))
        fireEvent.change(screen.getByRole('textbox', { name: 'Notification title' }), {
            target: { value: 'Consult booked' },
        })
        const recipientSelect = getFirstElement(
            screen.getAllByTestId('select').filter((select) => select.querySelector('option[value="host"]')),
            'Expected a notification recipient select',
        )
        expect(optionLabels(recipientSelect)).toContain('Appointment Host')
        fireEvent.change(recipientSelect, { target: { value: 'host' } })
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'appointment',
                trigger_type: 'appointment_scheduled',
                trigger_config: { record_type: 'egg_donor', appointment_type_names: ['Consultation'] },
                actions: [expect.objectContaining({ action_type: 'send_notification', recipients: 'host' })],
            }),
            expect.any(Object),
        )
    })

    it('starts on the appointment trigger and type named in the link', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [
                    { value: 'appointment_scheduled', label: 'Appointment Scheduled', description: '' },
                ],
                action_types_by_trigger: { appointment_scheduled: ['add_note'] },
                trigger_entity_types: { appointment_scheduled: 'appointment' },
                appointment_type_names: ['Initial Consultation'],
            },
            isLoading: false,
        })
        const preset = getWorkflowEditorPreset({
            trigger: 'appointment_scheduled',
            appointment_type: ' Initial Consultation ',
        })
        expect(getWorkflowEditorPreset({ trigger: 'surrogate_created', appointment_type: 'X' })).toBeNull()

        render(<WorkflowEditorPageClient workflowId={null} initialScope="personal" initialPreset={preset} />)

        expect(triggerSelect()).toHaveValue('appointment_scheduled')
        expect(screen.getByRole('button', { name: 'Remove Initial Consultation' })).toBeInTheDocument()
        expect(radioLabels('Linked record')).toEqual(['Surrogate'])
    })

    it('saves a timing workflow for hours after an appointment ends', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [
                    ...DEFAULT_OPTIONS.trigger_types,
                    { value: 'appointment_time', label: 'Before or After Appointment', description: '' },
                ],
                action_types_by_trigger: { appointment_time: ['add_note'] },
                trigger_entity_types: { appointment_time: 'appointment' },
                appointment_type_names: ['Initial Consultation'],
            },
            isLoading: false,
        })

        renderNewWorkflow()
        fireEvent.change(nameInput(), { target: { value: 'Consult follow-up' } })
        fireEvent.click(screen.getByRole('radio', { name: 'Date or scheduled' }))
        expect(optionLabels(triggerSelect())).toContain('Before or After Appointment')
        fireEvent.change(triggerSelect(), { target: { value: 'appointment_time' } })
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('24 hours before start')

        fireEvent.change(screen.getByRole('combobox', { name: 'When' }), { target: { value: 'after_end' } })
        fireEvent.change(screen.getByRole('spinbutton', { name: 'Hours' }), { target: { value: '2' } })
        fireEvent.change(screen.getByRole('combobox', { name: 'Appointment types' }), {
            target: { value: 'Initial Consultation' },
        })
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('2 hours after end')
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Types: Initial Consultation')
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Runs on linked surrogates')

        addNoteAction('Send the consult summary')
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'appointment',
                trigger_type: 'appointment_time',
                trigger_config: { when: 'after_end', hours: 2, appointment_type_names: ['Initial Consultation'] },
            }),
            expect.any(Object),
        )
    })

    it('blocks a timing workflow with hours out of range', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [{ value: 'appointment_time', label: 'Before or After Appointment', description: '' }],
                action_types_by_trigger: { appointment_time: ['add_note'] },
            },
            isLoading: false,
        })

        renderNewWorkflow()
        fireEvent.change(nameInput(), { target: { value: 'Too late' } })
        fireEvent.click(screen.getByRole('radio', { name: 'Date or scheduled' }))
        fireEvent.change(triggerSelect(), { target: { value: 'appointment_time' } })
        fireEvent.change(screen.getByRole('spinbutton', { name: 'Hours' }), { target: { value: '200' } })
        addNoteAction('Follow up')

        expect(launchButton()).toHaveAttribute('aria-disabled', 'true')
        expect(screen.getAllByTestId('tooltip').map((tip) => tip.textContent)).toContain(
            'Hours must be a whole number from 1 to 168.',
        )
        fireEvent.click(launchButton())
        expect(mockCreateWorkflow.mutate).not.toHaveBeenCalled()
    })

    it('offers the appointment host only to appointment workflows', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                action_types: [{ value: 'send_notification', label: 'Send Notification', description: '' }],
                action_types_by_trigger: { surrogate_created: ['send_notification'] },
            },
            isLoading: false,
        })

        renderNewWorkflow()
        fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
        fireEvent.click(screen.getByRole('button', { name: 'Send Notification' }))

        expect(screen.queryByRole('option', { name: 'Appointment Host' })).not.toBeInTheDocument()
        expect(screen.queryByRole('radiogroup', { name: 'Linked record' })).not.toBeInTheDocument()
    })

    it('saves a form-submitted workflow with the form submission subject', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [
                    { value: 'form_submitted', label: 'Application Submitted', description: '' },
                ],
                action_types: [
                    { value: 'add_note', label: 'Add Note', description: '' },
                ],
                action_types_by_trigger: { form_submitted: ['add_note'] },
                trigger_entity_types: { form_submitted: 'form_submission' },
                forms: [{ id: 'form-surrogate', name: 'Surrogate Application', lead_kind: 'surrogate' }],
            },
            isLoading: false,
        })

        renderNewWorkflow()
        fireEvent.change(nameInput(), { target: { value: 'Route applications' } })
        fireEvent.change(triggerSelect(), { target: { value: 'form_submitted' } })
        fireEvent.change(formSelect('form-surrogate'), { target: { value: 'form-surrogate' } })
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveTextContent('Form: Surrogate Application')
        expect(radioLabels('Record type')).toEqual(['Form Submission'])
        expect(screen.getByRole('radio', { name: 'Form Submission' })).toBeDisabled()
        addNoteAction('Review application')
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'form_submission',
                trigger_type: 'form_submitted',
                trigger_config: { form_id: 'form-surrogate' },
                actions: [expect.objectContaining({ action_type: 'add_note', content: 'Review application' })],
            }),
            expect.any(Object),
        )
    })

    describe('form routing handoff', () => {
        const formOptions = {
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [
                    ...DEFAULT_OPTIONS.trigger_types,
                    { value: 'form_submitted', label: 'Application Submitted', description: '' },
                    { value: 'form_submission_approved', label: 'Application Approved', description: '' },
                ],
                action_types_by_trigger: {
                    ...DEFAULT_OPTIONS.action_types_by_trigger,
                    form_submitted: ['add_note'],
                    form_submission_approved: ['add_note'],
                },
                trigger_entity_types: {
                    ...DEFAULT_OPTIONS.trigger_entity_types,
                    form_submitted: 'form_submission',
                    form_submission_approved: 'form_submission',
                },
                forms: [
                    { id: 'form-surrogate', name: 'Surrogate Application', lead_kind: 'surrogate' },
                    { id: 'form-egg-donor', name: 'Egg Donor Application', lead_kind: 'egg_donor' },
                ],
            },
            isLoading: false,
        }

        beforeEach(() => {
            mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['manage_automation'] } })
            mockUseWorkflowOptions.mockReturnValue(formOptions)
        })

        it('prefills the trigger and form for a new workflow and links to the form routing tab', () => {
            render(
                <WorkflowEditorPageClient
                    workflowId={null}
                    initialScope="org"
                    initialPreset={getWorkflowEditorPreset({ trigger: 'form_submission_approved', form_id: 'form-egg-donor' })}
                />,
            )

            expect(triggerSelect()).toHaveValue('form_submission_approved')
            expect(formSelect('form-egg-donor')).toHaveValue('form-egg-donor')
            const routingLink = screen.getByRole('link', { name: 'Matching and lead creation: Routing tab' })
            expect(routingLink).toHaveAttribute('href', '/automation/forms/form-egg-donor?tab=routing')
            // The arrow stays on the line of its last words.
            const arrow = routingLink.querySelector('[aria-hidden="true"]')
            expect(arrow?.textContent).toBe('\u00a0→')
            expect(arrow?.parentElement).toHaveClass('whitespace-nowrap')
            expect(arrow?.parentElement?.textContent).toBe('Routing tab\u00a0→')

            fireEvent.change(nameInput(), { target: { value: 'Approved donors' } })
            addNoteAction('Approved')
            fireEvent.click(launchButton())

            expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    scope: 'org',
                    trigger_type: 'form_submission_approved',
                    trigger_config: { form_id: 'form-egg-donor' },
                }),
                expect.any(Object),
            )
        })

        it('hides the routing link until a form is selected', () => {
            render(
                <WorkflowEditorPageClient
                    workflowId={null}
                    initialScope="org"
                    initialPreset={getWorkflowEditorPreset({ trigger: 'form_submitted' })}
                />,
            )

            expect(triggerSelect()).toHaveValue('form_submitted')
            expect(screen.queryByRole('link', { name: /Routing tab/ })).not.toBeInTheDocument()

            fireEvent.change(formSelect('form-surrogate'), { target: { value: 'form-surrogate' } })
            expect(screen.getByRole('link', { name: /Routing tab/ })).toHaveAttribute(
                'href',
                '/automation/forms/form-surrogate?tab=routing',
            )
        })

        it('ignores an unknown trigger and a form id without a form trigger', () => {
            expect(getWorkflowEditorPreset({ trigger: 'not_a_trigger', form_id: 'form-surrogate' })).toBeNull()
            expect(getWorkflowEditorPreset({ trigger: 'surrogate_created', form_id: 'form-surrogate' })).toBeNull()
            expect(getWorkflowEditorPreset({ trigger: 'form_submitted', form_id: ' form-surrogate ' })).toEqual({
                triggerType: 'form_submitted',
                triggerConfig: { form_id: 'form-surrogate' },
            })
        })
    })

    describe('Application Submitted stage updates', () => {
        const intakeOptions = (subjectType: string) => {
            const isEggDonor = subjectType === 'egg_donor'
            const isDonor = isEggDonor || subjectType === 'sperm_donor'
            const donorStatuses = {
                egg_donor: [{ id: 'egg-contacted', value: 'contacted', label: 'Egg Donor Contacted', is_active: true }],
                sperm_donor: [{ id: 'sperm-contacted', value: 'contacted', label: 'Sperm Donor Contacted', is_active: true }],
            }
            return {
                data: {
                    trigger_types: [
                        { value: 'form_submitted', label: 'Application Submitted', description: '' },
                        { value: 'intake_lead_created', label: 'Intake Lead Created', description: '' },
                    ],
                    action_types: [
                        { value: 'update_field', label: 'Update Field', description: '' },
                        { value: 'add_note', label: 'Add Note', description: '' },
                    ],
                    action_types_by_trigger: {
                        form_submitted: ['update_field'],
                        intake_lead_created: ['update_field', 'add_note'],
                    },
                    trigger_entity_types: { form_submitted: 'form_submission', intake_lead_created: 'intake_lead' },
                    condition_fields: ['stage_id', 'lead_kind'],
                    condition_operators: [{ value: 'in', label: 'Is one of' }],
                    update_fields: isDonor
                        ? ['stage_id', 'education', 'source']
                        : ['stage_id', 'is_priority'],
                    email_variables: [],
                    email_templates: [],
                    users: [],
                    queues: [],
                    statuses: isDonor
                        ? donorStatuses[subjectType as keyof typeof donorStatuses]
                        : [{ id: 'surrogate-contacted', value: 'contacted', label: 'Surrogate Contacted', is_active: true }],
                    forms: [
                        { id: 'form-surrogate', name: 'Surrogate Application', lead_kind: 'surrogate' },
                        { id: 'form-egg-donor', name: 'Egg Donor Application', lead_kind: 'egg_donor' },
                        {
                            id: 'form-shared-donor',
                            name: 'Donor Application',
                            lead_kind: 'egg_donor',
                            lead_kinds: ['egg_donor', 'sperm_donor'],
                        },
                    ],
                },
                isLoading: false,
            }
        }

        const FIXED_SUBJECTS: Record<string, string> = {
            form_submitted: 'form_submission',
            intake_lead_created: 'intake_lead',
        }

        const startIntakeWorkflow = (triggerType: string, formId: string) => {
            renderNewWorkflow()
            fireEvent.change(nameInput(), { target: { value: 'Donor applicants' } })
            fireEvent.change(triggerSelect(), { target: { value: triggerType } })
            fireEvent.change(formSelect(formId), { target: { value: formId } })
        }

        const createStageUpdate = (formId: string) => {
            startIntakeWorkflow('form_submitted', formId)
            fireEvent.click(screen.getByRole('button', { name: 'Update Field' }))
        }

        beforeEach(() => {
            mockUseEffectivePermissions.mockReturnValue({
                data: { permissions: ['view_donors', 'edit_donors'] },
            })
            mockUseWorkflowOptions.mockImplementation(
                (_scope: string, subjectType: string) => intakeOptions(subjectType),
            )
        })

        it.each([
            {
                formId: 'form-surrogate',
                fields: ['Stage', 'Is Priority'],
                stages: ['Surrogate Contacted'],
                stageId: 'surrogate-contacted',
            },
            {
                formId: 'form-egg-donor',
                fields: ['Stage', 'Education', 'Source'],
                stages: ['Egg Donor Contacted'],
                stageId: 'egg-contacted',
            },
        ])('offers the $formId record fields and stages and saves the stage', ({ formId, fields, stages, stageId }) => {
            createStageUpdate(formId)

            expect(optionLabels(screen.getByRole('combobox', { name: 'Field to update 1' }))).toEqual(fields)
            fireEvent.change(screen.getByRole('combobox', { name: 'Field to update 1' }), {
                target: { value: 'stage_id' },
            })
            const stageSelect = screen.getByRole('combobox', { name: 'Stage value 1' })
            expect(optionLabels(stageSelect)).toEqual(stages)
            fireEvent.change(stageSelect, { target: { value: stageId } })
            fireEvent.click(launchButton())

            expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    trigger_config: { form_id: formId },
                    actions: [expect.objectContaining({
                        action_type: 'update_field',
                        field: 'stage_id',
                        value: stageId,
                    })],
                }),
                expect.any(Object),
            )
        })

        it('offers no stage references for a form shared by both donor types', () => {
            startIntakeWorkflow('form_submitted', 'form-shared-donor')

            fireEvent.click(screen.getByRole('button', { name: 'Add filter' }))
            const conditionFieldSelect = getFirstElement(
                screen.getAllByTestId('select').filter((select) =>
                    select.querySelector('option[value="lead_kind"]'),
                ),
                'Expected a condition field select',
            )
            expect(optionLabels(conditionFieldSelect)).toEqual(['Applicant Type'])

            fireEvent.click(screen.getByRole('button', { name: 'Update Field' }))
            expect(optionLabels(screen.getByRole('combobox', { name: 'Field to update 1' }))).toEqual([
                'Education',
                'Source',
            ])
        })

        it('blocks saving an existing shared donor form workflow that references a stage', () => {
            mockUseWorkflow.mockReturnValue({
                data: {
                    id: 'workflow-shared-application',
                    name: 'Shared donor applications',
                    description: null,
                    scope: 'personal',
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    trigger_config: { form_id: 'form-shared-donor' },
                    conditions: [{ field: 'stage_id', operator: 'in', value: [] }],
                    condition_logic: 'AND',
                    actions: [{ action_type: 'add_note', content: 'Review' }],
                },
                isLoading: false,
            })

            renderExistingWorkflow('workflow-shared-application')
            expect(saveChangesButton()).toHaveAttribute('aria-disabled', 'true')
            fireEvent.click(saveChangesButton())

            expect(screen.getByText('Stage references need a form for one donor type.')).toBeInTheDocument()
            expect(mockUpdateWorkflow.mutate).not.toHaveBeenCalled()
        })

        it.each(['form_submitted', 'intake_lead_created'])(
            'offers an applicant type only for a %s form shared by both donor types',
            (triggerType) => {
                startIntakeWorkflow(triggerType, 'form-egg-donor')
                expect(screen.queryByRole('combobox', { name: 'Applicant Type' })).not.toBeInTheDocument()

                fireEvent.change(formSelect('form-shared-donor'), { target: { value: 'form-shared-donor' } })
                const applicantTypeSelect = screen.getByRole('combobox', { name: 'Applicant Type' })
                expect(applicantTypeSelect).toHaveValue('both')
                expect(optionLabels(applicantTypeSelect)).toEqual(['Egg Donor', 'Sperm Donor', 'Both'])
            },
        )

        it('maps every applicant type value to its label', () => {
            expect(getApplicantTypeLabel('egg_donor')).toBe('Egg Donor')
            expect(getApplicantTypeLabel('sperm_donor')).toBe('Sperm Donor')
            expect(getApplicantTypeLabel('both')).toBe('Both')
            expect(getApplicantTypeLabel(null)).toBe('Both')
            expect(getApplicantTypeLabel('surrogate')).toBe('Unknown applicant type')
        })

        it.each([
            {
                triggerType: 'form_submitted',
                key: 'lead_kind',
                leadKind: 'egg_donor',
                stages: ['Egg Donor Contacted'],
                stageId: 'egg-contacted',
            },
            {
                triggerType: 'intake_lead_created',
                key: 'lead_type',
                leadKind: 'sperm_donor',
                stages: ['Sperm Donor Contacted'],
                stageId: 'sperm-contacted',
            },
        ])(
            'saves $leadKind as the $triggerType $key and offers its stages',
            ({ triggerType, key, leadKind, stages, stageId }) => {
                startIntakeWorkflow(triggerType, 'form-shared-donor')
                fireEvent.change(screen.getByRole('combobox', { name: 'Applicant Type' }), {
                    target: { value: leadKind },
                })
                fireEvent.click(screen.getByRole('button', { name: 'Update Field' }))
                fireEvent.change(screen.getByRole('combobox', { name: 'Field to update 1' }), {
                    target: { value: 'stage_id' },
                })
                const stageSelect = screen.getByRole('combobox', { name: 'Stage value 1' })
                expect(optionLabels(stageSelect)).toEqual(stages)
                fireEvent.change(stageSelect, { target: { value: stageId } })
                fireEvent.click(launchButton())

                expect(mockUseWorkflowOptions).toHaveBeenCalledWith('personal', leadKind)
                expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
                    expect.objectContaining({
                        trigger_type: triggerType,
                        trigger_config: { form_id: 'form-shared-donor', [key]: leadKind },
                        actions: [expect.objectContaining({ field: 'stage_id', value: stageId })],
                    }),
                    expect.any(Object),
                )
            },
        )

        it('saves no applicant type when Both is selected', () => {
            startIntakeWorkflow('form_submitted', 'form-shared-donor')
            const applicantTypeSelect = screen.getByRole('combobox', { name: 'Applicant Type' })
            fireEvent.change(applicantTypeSelect, { target: { value: 'egg_donor' } })
            fireEvent.change(applicantTypeSelect, { target: { value: 'both' } })
            fireEvent.click(screen.getByRole('button', { name: 'Update Field' }))
            const fieldSelect = screen.getByRole('combobox', { name: 'Field to update 1' })
            expect(optionLabels(fieldSelect)).toEqual(['Education', 'Source'])
            fireEvent.change(fieldSelect, { target: { value: 'education' } })
            fireEvent.change(screen.getByRole('textbox', { name: 'Value' }), { target: { value: 'Bachelor' } })
            fireEvent.click(launchButton())

            expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({ trigger_config: { form_id: 'form-shared-donor' } }),
                expect.any(Object),
            )
        })

        it('resets the applicant type when the trigger form changes', () => {
            startIntakeWorkflow('form_submitted', 'form-shared-donor')
            fireEvent.change(screen.getByRole('combobox', { name: 'Applicant Type' }), {
                target: { value: 'egg_donor' },
            })
            fireEvent.change(formSelect('form-egg-donor'), { target: { value: 'form-egg-donor' } })
            fireEvent.change(formSelect('form-shared-donor'), { target: { value: 'form-shared-donor' } })

            expect(screen.getByRole('combobox', { name: 'Applicant Type' })).toHaveValue('both')
        })

        it.each([
            { triggerType: 'form_submitted', key: 'lead_kind' },
            { triggerType: 'intake_lead_created', key: 'lead_type' },
        ])('clears the $key applicant type when the $triggerType form changes', ({ triggerType, key }) => {
            mockUseWorkflow.mockReturnValue({
                data: {
                    id: 'workflow-egg-intake',
                    name: 'Egg donor intake',
                    description: null,
                    scope: 'personal',
                    subject_type: FIXED_SUBJECTS[triggerType],
                    trigger_type: triggerType,
                    trigger_config: { form_id: 'form-egg-donor', [key]: 'egg_donor' },
                    conditions: [],
                    condition_logic: 'AND',
                    actions: [{ action_type: 'update_field', field: 'is_priority', value: true }],
                },
                isLoading: false,
            })

            renderExistingWorkflow('workflow-egg-intake')
            fireEvent.change(formSelect('form-surrogate'), { target: { value: 'form-surrogate' } })
            fireEvent.click(saveChangesButton())

            expect(mockUpdateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    id: 'workflow-egg-intake',
                    data: expect.objectContaining({ trigger_config: { form_id: 'form-surrogate' } }),
                }),
                expect.any(Object),
            )
        })

        it('keeps stage conditions when an existing donor application workflow is saved', () => {
            mockUseWorkflow.mockReturnValue({
                data: {
                    id: 'workflow-egg-application',
                    name: 'Egg donor applications',
                    description: null,
                    scope: 'personal',
                    subject_type: 'form_submission',
                    trigger_type: 'form_submitted',
                    trigger_config: { form_id: 'form-egg-donor', lead_kind: 'egg_donor' },
                    conditions: [
                        { field: 'stage_id', operator: 'in', value: ['egg-contacted'], stage_keys: ['contacted'] },
                    ],
                    condition_logic: 'AND',
                    actions: [
                        { action_type: 'update_field', field: 'stage_id', value: 'egg-contacted', value_stage_key: 'contacted' },
                    ],
                },
                isLoading: false,
            })

            renderExistingWorkflow('workflow-egg-application')
            fireEvent.click(screen.getByRole('button', { name: 'Action 1: Update Field' }))
            expect(optionLabels(screen.getByRole('combobox', { name: 'Stage value 1' }))).toEqual([
                'Egg Donor Contacted',
            ])
            fireEvent.click(saveChangesButton())

            expect(mockUseWorkflowOptions).toHaveBeenCalledWith('personal', 'egg_donor')
            expect(mockUpdateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    id: 'workflow-egg-application',
                    data: expect.objectContaining({
                        conditions: [
                            expect.objectContaining({ field: 'stage_id', operator: 'in', value: ['egg-contacted'] }),
                        ],
                        actions: [expect.objectContaining({ field: 'stage_id', value: 'egg-contacted' })],
                    }),
                }),
                expect.any(Object),
            )
        })
    })

    it('drops surrogate-only promotion options for donor intake forms', () => {
        mockUseWorkflowOptions.mockReturnValue({
            data: {
                ...DEFAULT_OPTIONS,
                trigger_types: [
                    { value: 'intake_lead_created', label: 'Intake Lead Created', description: '' },
                ],
                action_types: [
                    { value: 'promote_intake_lead', label: 'Promote Intake Lead', description: '' },
                ],
                action_types_by_trigger: { intake_lead_created: ['promote_intake_lead'] },
                trigger_entity_types: { intake_lead_created: 'intake_lead' },
                forms: [
                    { id: 'form-surrogate', name: 'Surrogate Application', lead_kind: 'surrogate' },
                    { id: 'form-egg-donor', name: 'Egg Donor Application', lead_kind: 'egg_donor' },
                ],
            },
            isLoading: false,
        })
        const promotionSwitch = (label: string) => {
            const promotionSwitchElement = screen.getByText(label).parentElement?.querySelector('[role="switch"]')
            if (!promotionSwitchElement) throw new Error(`Expected the ${label} switch`)
            return promotionSwitchElement
        }

        renderNewWorkflow()
        fireEvent.change(nameInput(), { target: { value: 'Promote leads' } })
        fireEvent.change(triggerSelect(), { target: { value: 'intake_lead_created' } })
        fireEvent.change(formSelect('form-surrogate'), { target: { value: 'form-surrogate' } })
        fireEvent.click(screen.getByRole('button', { name: 'Promote Intake Lead' }))
        fireEvent.click(promotionSwitch('Mark as priority'))
        fireEvent.click(promotionSwitch('Assign to workflow owner if available'))

        fireEvent.click(screen.getByRole('button', { name: 'Trigger step' }))
        fireEvent.change(formSelect('form-egg-donor'), { target: { value: 'form-egg-donor' } })
        fireEvent.click(screen.getByRole('button', { name: 'Action 1: Promote Intake Lead' }))
        expect(screen.queryByText('Mark as priority')).not.toBeInTheDocument()
        expect(screen.queryByText('Assign to workflow owner if available')).not.toBeInTheDocument()
        fireEvent.click(launchButton())

        const payload = mockCreateWorkflow.mutate.mock.calls.at(-1)?.[0]
        expect(payload).toMatchObject({
            subject_type: 'intake_lead',
            trigger_type: 'intake_lead_created',
            trigger_config: { form_id: 'form-egg-donor' },
        })
        expect(payload.actions).toHaveLength(1)
        expect(payload.actions[0].action_type).toBe('promote_intake_lead')
        expect(payload.actions[0]).not.toHaveProperty('is_priority')
        expect(payload.actions[0]).not.toHaveProperty('assign_to_user')
    })

    it('keeps approval optional for donor email actions', () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ['view_donors', 'edit_donors'] } })
        mockUseWorkflowOptions.mockImplementation(
            (_scope: string, subjectType: string) => ({
                data: {
                    ...DEFAULT_OPTIONS,
                    trigger_types: subjectType === 'egg_donor'
                        ? [{ value: 'donor_created', label: 'Donor Created', description: '' }]
                        : [{ value: 'surrogate_created', label: 'Surrogate Created', description: '' }],
                    action_types: [{ value: 'send_email', label: 'Send Email', description: '' }],
                    action_types_by_trigger: subjectType === 'egg_donor'
                        ? { donor_created: ['send_email'] }
                        : { surrogate_created: ['send_email'] },
                    trigger_entity_types: subjectType === 'egg_donor'
                        ? { donor_created: 'egg_donor' }
                        : { surrogate_created: 'surrogate' },
                    email_templates: [{ id: 'email-template-1', name: 'Donor welcome' }],
                },
                isLoading: false,
            }),
        )

        renderNewWorkflow()
        chooseRecordType('Egg Donor')
        fireEvent.change(nameInput(), { target: { value: 'Egg donor welcome email' } })
        fireEvent.change(triggerSelect(), { target: { value: 'donor_created' } })
        fireEvent.click(screen.getByRole('button', { name: 'Send Email' }))
        const templateSelect = getFirstElement(
            screen.getAllByTestId('select').filter((select) =>
                select.querySelector('option[value="email-template-1"]'),
            ),
            'Expected an email template select',
        )
        fireEvent.change(templateSelect, { target: { value: 'email-template-1' } })
        const approval = screen.getByRole('switch', { name: 'Requires Approval' })
        expect(approval).not.toHaveAttribute('aria-disabled', 'true')
        expect(approval).toHaveAttribute('aria-checked', 'false')
        expect(screen.getByRole('button', { name: 'Action 1: Send Email' })).toHaveTextContent('Donor welcome to Donor')
        fireEvent.click(launchButton())

        expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                subject_type: 'egg_donor',
                actions: [{
                    action_type: 'send_email',
                    template_id: 'email-template-1',
                    recipients: 'donor',
                }],
            }),
            expect.any(Object),
        )
    })

    it('reorders and removes actions from the inspector', () => {
        renderNewWorkflow()
        fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
        addNoteAction('First')
        fireEvent.click(screen.getByRole('button', { name: 'Add Note' }))
        fireEvent.change(screen.getByRole('textbox', { name: 'Note content' }), { target: { value: 'Second' } })

        fireEvent.click(screen.getByRole('button', { name: 'Move action up' }))
        expect(screen.getByRole('button', { name: 'Action 1: Add Note' })).toHaveTextContent('Second')
        expect(screen.getByRole('button', { name: 'Action 2: Add Note' })).toHaveTextContent('First')

        fireEvent.click(screen.getByRole('button', { name: 'Remove action' }))
        expect(screen.queryByRole('button', { name: 'Action 2: Add Note' })).not.toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Action 1: Add Note' })).toHaveTextContent('First')
        expect(screen.getByRole('button', { name: 'Trigger step' })).toHaveAttribute('aria-pressed', 'true')
    })

    it('returns to the scoped list after saving changes', () => {
        mockUseWorkflow.mockReturnValue({
            data: {
                id: 'workflow-org',
                name: 'Org workflow',
                description: null,
                scope: 'org',
                subject_type: 'surrogate',
                trigger_type: 'surrogate_created',
                trigger_config: {},
                conditions: [],
                condition_logic: 'AND',
                actions: [{ action_type: 'add_note', content: 'Hello' }],
            },
            isLoading: false,
        })
        mockUpdateWorkflow.mutate.mockImplementation(
            (_data: unknown, opts?: { onSuccess?: () => void }) => {
                opts?.onSuccess?.()
            },
        )

        renderExistingWorkflow('workflow-org')
        fireEvent.click(saveChangesButton())

        expect(mockUpdateWorkflow.mutate).toHaveBeenCalledWith(
            expect.objectContaining({
                id: 'workflow-org',
                data: expect.not.objectContaining({ subject_type: expect.anything() }),
            }),
            expect.any(Object),
        )
        expect(mockPush).toHaveBeenCalledWith('/automation?tab=workflows&scope=org')
    })

    describe('staff email recipients and per-trigger fields', () => {
        const EMAIL_OPTIONS = {
            ...DEFAULT_OPTIONS,
            trigger_types: [
                ...DEFAULT_OPTIONS.trigger_types,
                { value: 'intake_lead_created', label: 'Intake Lead Created', description: '' },
            ],
            action_types: [{ value: 'send_email', label: 'Send Email', description: '' }],
            action_types_by_trigger: { surrogate_created: ['send_email'], intake_lead_created: ['send_email'] },
            trigger_entity_types: { ...DEFAULT_OPTIONS.trigger_entity_types, intake_lead_created: 'intake_lead' },
            email_templates: [{ id: 'template-1', name: 'Staff Alert' }],
            queues: [{ id: 'queue-1', name: 'Intake Queue' }],
            forms: [{ id: 'form-1', name: 'Application', lead_kind: 'surrogate' }],
        }
        const selectWith = (value: string) =>
            getFirstElement(
                screen.getAllByTestId('select').filter((select) => select.querySelector(`option[value="${value}"]`)),
                `Expected a select offering ${value}`,
            )

        it('saves a Send Email action addressed to a queue', () => {
            mockUseWorkflowOptions.mockReturnValue({ data: EMAIL_OPTIONS, isLoading: false })
            renderNewWorkflow()

            fireEvent.change(nameInput(), { target: { value: 'Queue alert' } })
            fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
            fireEvent.click(screen.getByRole('button', { name: 'Send Email' }))
            fireEvent.change(selectWith('template-1'), { target: { value: 'template-1' } })
            fireEvent.change(selectWith('queue'), { target: { value: 'queue' } })

            expect(launchButton()).toHaveAttribute('aria-disabled', 'true')
            fireEvent.change(selectWith('queue-1'), { target: { value: 'queue-1' } })
            fireEvent.click(launchButton())

            expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    actions: [
                        expect.objectContaining({
                            action_type: 'send_email',
                            template_id: 'template-1',
                            recipients: 'queue',
                            recipient_queue_id: 'queue-1',
                            recipient_role: null,
                            recipient_emails: null,
                        }),
                    ],
                }),
                expect.any(Object),
            )
        })

        it('requires valid custom email addresses', () => {
            mockUseWorkflowOptions.mockReturnValue({ data: EMAIL_OPTIONS, isLoading: false })
            renderNewWorkflow()

            fireEvent.change(nameInput(), { target: { value: 'Address alert' } })
            fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
            fireEvent.click(screen.getByRole('button', { name: 'Send Email' }))
            fireEvent.change(selectWith('template-1'), { target: { value: 'template-1' } })
            fireEvent.change(selectWith('custom'), { target: { value: 'custom' } })
            const addresses = screen.getByRole('textbox', { name: 'Email addresses' })
            fireEvent.change(addresses, { target: { value: 'intake@agency.test, ' } })
            expect(addresses).toHaveValue('intake@agency.test, ')

            fireEvent.change(addresses, { target: { value: 'intake@agency.test, not-an-address' } })
            expect(screen.getAllByTestId('tooltip')[0]).toHaveTextContent('Enter valid email addresses.')

            fireEvent.change(addresses, { target: { value: 'intake@agency.test, ops@agency.test' } })
            fireEvent.click(launchButton())
            expect(mockCreateWorkflow.mutate).toHaveBeenCalledWith(
                expect.objectContaining({
                    actions: [
                        expect.objectContaining({
                            recipients: 'custom',
                            recipient_emails: ['intake@agency.test', 'ops@agency.test'],
                        }),
                    ],
                }),
                expect.any(Object),
            )
        })

        it('offers only staff recipients for intake lead emails', () => {
            mockUseWorkflowOptions.mockReturnValue({ data: EMAIL_OPTIONS, isLoading: false })
            renderNewWorkflow()

            fireEvent.change(triggerSelect(), { target: { value: 'intake_lead_created' } })
            fireEvent.click(screen.getByRole('button', { name: 'Send Email' }))

            const recipients = selectWith('all_admins')
            expect(recipients).toHaveValue('all_admins')
            expect(optionLabels(recipients)).not.toContain('Surrogate')
            expect(optionLabels(recipients)).toContain('Queue')
        })

        it('lists the condition fields of the selected trigger with their values', () => {
            mockUseWorkflowOptions.mockReturnValue({
                data: {
                    ...DEFAULT_OPTIONS,
                    condition_fields: ['state'],
                    condition_fields_by_trigger: { surrogate_created: ['contact_status', 'is_archived'] },
                },
                isLoading: false,
            })
            renderNewWorkflow()

            fireEvent.change(triggerSelect(), { target: { value: 'surrogate_created' } })
            fireEvent.click(screen.getByRole('button', { name: 'Add filter' }))
            const field = selectWith('contact_status')
            expect(optionLabels(field)).toEqual(['Contact Status', 'Is Archived'])

            fireEvent.change(field, { target: { value: 'contact_status' } })
            expect(optionLabels(selectWith('reached'))).toEqual(['Unreached', 'Reached'])
        })
    })
})

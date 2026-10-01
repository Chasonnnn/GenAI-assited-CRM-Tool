"use client"

import { useEffect, useReducer, useRef, useState } from "react"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { FORM_LEAD_KIND_OPTIONS } from "@/lib/forms/form-lead-kind"
import type {
    ActionConfig,
    Condition,
    WorkflowCreate,
    WorkflowOptions,
    WorkflowScope,
    WorkflowSubjectType,
} from "@/lib/api/workflows"
import { useAuth } from "@/lib/auth-context"
import { US_STATES } from "@/lib/constants/us-states"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import { useCreateWorkflow, useUpdateWorkflow, useWorkflow, useWorkflowOptions } from "@/lib/hooks/use-workflows"
import type { JsonObject } from "@/lib/types/json"
import { completeWorkflowSetup, startWorkflowSetup } from "@/lib/workflow-metrics"
import { toast } from "@/components/ui/toast"
import {
    EMAIL_RECIPIENT_OPTIONS,
    FORM_MATCH_STATUS_OPTIONS,
    FORM_SOURCE_MODE_OPTIONS,
    INTAKE_LEAD_KIND_CONFIG_KEYS,
    OWNER_TYPE_OPTIONS,
    SOURCE_OPTIONS,
    areJsonObjectsEqual,
    createClientRowId,
    isDonorIntakeWorkflow,
    isDonorLeadKind,
    normalizeEditableActionsForSave,
    normalizeEditableConditionsForSave,
    stripDonorPromotionOptions,
    type SelectOption,
} from "@/components/automation/workflow-editor/shared"
import {
    CREATE_WORKFLOW_SUBJECT_OPTIONS,
    DONOR_TYPE_OPTIONS,
    FIXED_TRIGGER_SUBJECT_TYPES,
    SHARED_DONOR_STAGE_ERROR,
    buildTriggerConfigForSave,
    createInitialWorkflowBuilderState,
    getActionsValidationError,
    getTriggerConfigValidationError,
    isDonorSubject,
    normalizeTriggerConfigForUi,
    parseServerErrors,
    workflowBuilderReducer,
    type StateUpdate,
    type StatusOption,
} from "@/lib/workflows/workflow-editor-state"

const EMPTY_STATUS_OPTIONS: StatusOption[] = []

export type WorkflowEditorSelection =
    | { kind: "trigger" }
    | { kind: "conditions" }
    | { kind: "action"; clientId: string }

export type WorkflowEditorAccess =
    | { status: "loading" }
    | { status: "error"; retry: () => void; isRetrying: boolean }
    | { status: "denied" }
    | { status: "not_found" }
    | { status: "ok" }

export type WorkflowEditorController = ReturnType<typeof useWorkflowEditor>

export function useWorkflowEditor({
    workflowId,
    initialScope,
}: {
    /** Null creates a new workflow. */
    workflowId: string | null
    initialScope: WorkflowScope
}) {
    const { push } = useRouter()
    const { user } = useAuth()
    const permissionCheck = usePermissionCheck()
    const { can, policyVersion } = permissionCheck
    const canUseAI = Boolean(user?.ai_enabled) && can("use_ai_assistant")
    const canManageAutomation = can("manage_automation")
    const policyV2 = (policyVersion ?? 1) >= 2
    const canManageOrgWorkflows = canManageAutomation && (!policyV2 || can("manage_org_workflows"))
    // Mirrors the create route: v1 also requires edit_donors for donor workflows.
    const canCreateDonorWorkflows = can("view_donors") && (policyV2 || can("edit_donors"))
    const createWorkflowSubjectOptions = CREATE_WORKFLOW_SUBJECT_OPTIONS.filter(
        (option) => canCreateDonorWorkflows || !isDonorSubject(option.value),
    )
    // Mirrors workflow_access.can_create: org workflows need manage_automation (plus
    // manage_org_workflows under policy v2); personal workflows are open under v1 and need
    // manage_automation under v2.
    const canCreatePersonal = !policyV2 || canManageAutomation

    const isEditing = workflowId !== null
    const [state, dispatch] = useReducer(
        workflowBuilderReducer,
        initialScope,
        createInitialWorkflowBuilderState,
    )
    const [selection, setSelection] = useState<WorkflowEditorSelection>({ kind: "trigger" })
    const {
        hydratedWorkflowId,
        validationError,
        serverErrors,
        workflowName,
        workflowDescription,
        workflowScope,
        subjectType,
        triggerType,
        triggerConfig,
        conditions,
        conditionLogic,
        actions,
    } = state
    const savedSubjectType = FIXED_TRIGGER_SUBJECT_TYPES[triggerType] ?? subjectType

    const setupSessionIdRef = useRef<string | null>(null)
    useEffect(() => {
        // Setup telemetry opens one session per new-workflow visit.
        if (isEditing || setupSessionIdRef.current !== null) return
        setupSessionIdRef.current = startWorkflowSetup(initialScope)
    }, [isEditing, initialScope])

    const workflowQuery = useWorkflow(workflowId ?? "")
    const editingWorkflow = workflowQuery.data

    const { data: options } = useWorkflowOptions(workflowScope, subjectType)
    const formOptions: SelectOption[] = (options?.forms ?? []).map((form) => ({ value: form.id, label: form.name }))
    const triggerForm = options?.forms?.find((form) => form.id === triggerConfig.form_id)
    const isDonorIntakeTrigger = isDonorIntakeWorkflow({ triggerConfig, formLeadKind: triggerForm?.lead_kind })
    // Intake workflows update the linked surrogate or donor, so their stage and update-field
    // options come from the pipeline of the trigger form's lead kind (mirrors
    // workflow_service.resolve_workflow_record_type).
    const intakeLeadKindKey = INTAKE_LEAD_KIND_CONFIG_KEYS[triggerType]
    const configuredIntakeLeadKind = intakeLeadKindKey ? triggerConfig[intakeLeadKindKey] : undefined
    const intakeLeadKind =
        isDonorLeadKind(triggerForm?.lead_kind) && isDonorLeadKind(configuredIntakeLeadKind)
            ? configuredIntakeLeadKind
            : triggerForm?.lead_kind ?? configuredIntakeLeadKind
    const recordSubjectType: WorkflowSubjectType =
        intakeLeadKindKey && !isDonorSubject(subjectType) && isDonorLeadKind(intakeLeadKind)
            ? intakeLeadKind
            : subjectType
    const isSharedDonorTriggerForm =
        Boolean(intakeLeadKindKey) && (triggerForm?.lead_kinds?.filter(isDonorLeadKind).length ?? 0) > 1
    // A form shared by both donor types has no single pipeline, so its workflows cannot
    // reference stages unless the trigger names one donor type.
    const hasSharedDonorRecord = isSharedDonorTriggerForm && !isDonorLeadKind(configuredIntakeLeadKind)

    const { data: recordOptions } = useWorkflowOptions(workflowScope, recordSubjectType)
    const statusOptions = recordOptions?.statuses ?? EMPTY_STATUS_OPTIONS
    const activeStatusOptions = statusOptions.filter((status) => status.is_active !== false)
    const recordUpdateFields = recordOptions?.update_fields ?? []
    const updateFields = hasSharedDonorRecord
        ? recordUpdateFields.filter((field) => field !== "stage_id")
        : recordUpdateFields
    const actionTypeOptions = options?.action_types ?? []
    const actionTypeValuesForTrigger = triggerType && options?.action_types_by_trigger?.[triggerType]
        ? new Set(options.action_types_by_trigger[triggerType])
        : null
    const filteredActionTypes = actionTypeValuesForTrigger
        ? actionTypeOptions.filter((action) => actionTypeValuesForTrigger.has(action.value))
        : actionTypeOptions
    const userOptions = options?.users ?? []
    const queueOptions = options?.queues ?? []
    const messageTemplates = options?.message_templates ?? []
    const emailTemplates = options?.email_templates ?? []
    const emailRecipientOptions: SelectOption[] = isDonorSubject(subjectType)
        ? [
            { value: "donor", label: "Donor" },
            ...EMAIL_RECIPIENT_OPTIONS.flatMap((option) => {
                if (option.value === "surrogate") return []
                return [option.value === "owner" ? { ...option, label: "Donor Owner" } : option]
            }),
        ]
        : EMAIL_RECIPIENT_OPTIONS
    const conditionOperators = options?.condition_operators ?? []
    const triggerTypeOptions: WorkflowOptions["trigger_types"] = options?.trigger_types ?? []

    const stageIdOptions: SelectOption[] = statusOptions.map((status) => ({
        value: status.id ?? status.value,
        label: status.label,
    }))
    const stageLabelOptions: SelectOption[] = statusOptions.map((status) => ({
        value: status.label,
        label: status.label,
    }))
    const ownerOptions: SelectOption[] = [
        ...userOptions.map((option) => ({ value: option.id, label: option.display_name })),
        ...queueOptions.map((queue) => ({ value: queue.id, label: `Queue: ${queue.name}` })),
    ]
    const stateOptions: SelectOption[] = US_STATES.map((item) => ({ value: item.value, label: item.label }))

    const selectedTriggerFields = Array.isArray(triggerConfig.fields)
        ? triggerConfig.fields.filter((field): field is string => typeof field === "string")
        : []
    const optionConditionFields = options?.condition_fields ?? []
    const availableConditionFields = hasSharedDonorRecord
        ? optionConditionFields.filter((field) => field !== "stage_id")
        : optionConditionFields

    const createWorkflow = useCreateWorkflow()
    const updateWorkflow = useUpdateWorkflow()

    // Hydrate once the selected workflow has loaded (render-time derived dispatch keeps the
    // draft in sync without an effect).
    if (
        editingWorkflow &&
        workflowId &&
        editingWorkflow.id === workflowId &&
        hydratedWorkflowId !== workflowId
    ) {
        dispatch({
            type: "hydrateWorkflow",
            workflow: editingWorkflow as WorkflowCreate & { scope: WorkflowScope },
            workflowId,
            statusOptions,
        })
    }

    if (
        (triggerType === "status_changed" || triggerType === "donor_stage_changed") &&
        statusOptions.length > 0
    ) {
        const normalized = normalizeTriggerConfigForUi(triggerType, triggerConfig, statusOptions)
        if (!areJsonObjectsEqual(normalized, triggerConfig)) {
            dispatch({ type: "normalizeTriggerConfig", value: normalized })
        }
    }

    const selectedActionIndex =
        selection.kind === "action"
            ? actions.findIndex((action) => action.clientId === selection.clientId)
            : -1
    // Removed actions fall back to the trigger panel.
    const effectiveSelection: WorkflowEditorSelection =
        selection.kind === "action" && selectedActionIndex < 0 ? { kind: "trigger" } : selection

    const getConditionOptions = (field: string): SelectOption[] | null => {
        if (field === "stage_id") return stageIdOptions
        if (field === "status_label") return stageLabelOptions
        if (field === "owner_type") return OWNER_TYPE_OPTIONS
        if (field === "owner_id") return ownerOptions
        if (field === "state") return stateOptions
        if (field === "source") return SOURCE_OPTIONS
        if (field === "lead_kind") return FORM_LEAD_KIND_OPTIONS
        if (field === "source_mode") return FORM_SOURCE_MODE_OPTIONS
        if (field === "match_status") return FORM_MATCH_STATUS_OPTIONS
        if (field === "donor_type") return DONOR_TYPE_OPTIONS
        return null
    }

    const getStageValidationError = (): string | null => {
        if (!hasSharedDonorRecord) return null
        if (conditions.some((condition) => condition.field === "stage_id")) return SHARED_DONOR_STAGE_ERROR
        if (actions.some((action) => action.action_type === "update_field" && action.field === "stage_id")) {
            return SHARED_DONOR_STAGE_ERROR
        }
        return null
    }

    const getWorkflowValidationError = (): string | null => {
        if (!workflowName.trim()) return "Workflow name is required."
        if (!triggerType) return "Trigger type is required."
        const triggerError = getTriggerConfigValidationError(triggerType, triggerConfig)
        if (triggerError) return triggerError
        const stageError = getStageValidationError()
        if (stageError) return stageError
        return getActionsValidationError(triggerType, actions)
    }

    const workflowValidationError = getWorkflowValidationError()
    const hasServerErrors = serverErrors.length > 0
    const isSaving = createWorkflow.isPending || updateWorkflow.isPending
    const listHref: Route = `/automation?tab=workflows&scope=${workflowScope}`

    const setWorkflowName = (value: string) => dispatch({ type: "setWorkflowName", value })
    const setWorkflowDescription = (value: string) => dispatch({ type: "setWorkflowDescription", value })
    const setSubjectType = (value: WorkflowSubjectType) => {
        dispatch({ type: "setSubjectType", value })
        setSelection({ kind: "trigger" })
    }
    const setTriggerType = (value: string) => dispatch({ type: "setTriggerType", value })
    const setTriggerConfig = (value: StateUpdate<JsonObject>) => dispatch({ type: "setTriggerConfig", value })
    const setConditionLogic = (value: "AND" | "OR") => dispatch({ type: "setConditionLogic", value })
    const setIntakeApplicantType = (value: string | null) => {
        if (!intakeLeadKindKey) return
        setTriggerConfig((currentConfig) => {
            const nextConfig: JsonObject = { ...currentConfig }
            if (isDonorLeadKind(value)) nextConfig[intakeLeadKindKey] = value
            else delete nextConfig[intakeLeadKindKey]
            return nextConfig
        })
    }
    const addCondition = () => dispatch({ type: "addCondition" })
    const removeCondition = (index: number) => dispatch({ type: "removeCondition", index })
    const updateCondition = (index: number, updates: Partial<Condition>) =>
        dispatch({ type: "updateCondition", index, updates })

    const buildNewAction = (actionType: string): Partial<ActionConfig> => ({
        action_type: actionType,
        ...(isDonorSubject(subjectType) && actionType === "send_message" ? { requires_approval: true } : {}),
    })
    const addAction = (actionType = "") => {
        const clientId = createClientRowId()
        dispatch({ type: "addAction", clientId, action: actionType ? buildNewAction(actionType) : {} })
        setSelection({ kind: "action", clientId })
    }
    const removeAction = (index: number) => {
        dispatch({ type: "removeAction", index })
        setSelection({ kind: "trigger" })
    }
    const moveAction = (index: number, direction: -1 | 1) => dispatch({ type: "moveAction", index, direction })
    const updateAction = (index: number, updates: Partial<ActionConfig>) =>
        dispatch({ type: "updateAction", index, updates })
    const updateActionType = (index: number, actionType: string) => updateAction(index, buildNewAction(actionType))

    const saveWorkflow = ({ isEnabled }: { isEnabled: boolean }) => {
        const error = getWorkflowValidationError()
        if (error) {
            dispatch({ type: "setValidationError", value: error })
            return
        }
        dispatch({ type: "setValidationError", value: null })

        const normalizedActions = normalizeEditableActionsForSave(actions).map((action) => {
            if (
                isDonorSubject(subjectType) &&
                action.action_type === "send_email" &&
                (action.recipients === undefined || action.recipients === "surrogate")
            ) {
                return { ...action, recipients: "donor" }
            }
            return isDonorIntakeTrigger ? stripDonorPromotionOptions(action) : action
        })

        const data: WorkflowCreate = {
            name: workflowName,
            subject_type: savedSubjectType,
            trigger_type: triggerType,
            trigger_config: buildTriggerConfigForSave(triggerType, triggerConfig),
            conditions: normalizeEditableConditionsForSave(conditions),
            condition_logic: conditionLogic,
            actions: normalizedActions,
            is_enabled: isEnabled,
            scope: workflowScope,
            ...(workflowDescription ? { description: workflowDescription } : {}),
        }

        if (workflowId) {
            const { subject_type: _subjectType, scope: _scope, is_enabled: _isEnabled, ...updateData } = data
            void _subjectType
            void _scope
            void _isEnabled
            updateWorkflow.mutate(
                { id: workflowId, data: updateData },
                {
                    onSuccess: () => {
                        toast.success("Workflow saved")
                        push(listHref)
                    },
                    onError: (mutationError) =>
                        dispatch({
                            type: "setServerErrors",
                            value: parseServerErrors(mutationError, {
                                forbiddenMessage: "You don't have permission to change this workflow",
                            }),
                        }),
                },
            )
            return
        }

        createWorkflow.mutate(data, {
            onSuccess: () => {
                completeWorkflowSetup(setupSessionIdRef.current, workflowScope)
                toast.success(isEnabled ? "Workflow launched" : "Workflow saved as draft")
                push(listHref)
            },
            onError: (mutationError) =>
                dispatch({
                    type: "setServerErrors",
                    value: parseServerErrors(mutationError, {
                        forbiddenMessage:
                            workflowScope === "org"
                                ? "You don't have permission to create organization workflows"
                                : "You don't have permission to create workflows",
                    }),
                }),
        })
    }

    const access: WorkflowEditorAccess = (() => {
        if (permissionCheck.isLoading) return { status: "loading" }
        if (permissionCheck.isError) {
            return { status: "error", retry: permissionCheck.retry, isRetrying: permissionCheck.isRetrying }
        }
        if (isEditing) {
            if (workflowQuery.isLoading) return { status: "loading" }
            if (workflowQuery.isError) {
                return {
                    status: "error",
                    retry: () => {
                        void workflowQuery.refetch()
                    },
                    isRetrying: workflowQuery.isFetching,
                }
            }
            if (!editingWorkflow) return { status: "not_found" }
            if (editingWorkflow.can_edit === false) return { status: "denied" }
            if (hydratedWorkflowId !== workflowId) return { status: "loading" }
            return { status: "ok" }
        }
        const canCreate = initialScope === "org" ? canManageOrgWorkflows : canCreatePersonal
        return canCreate ? { status: "ok" } : { status: "denied" }
    })()

    return {
        access,
        isEditing,
        workflowId,
        editingWorkflow,
        listHref,
        canUseAI,
        createWorkflowSubjectOptions,
        selection: effectiveSelection,
        selectedActionIndex,
        setSelection,
        state: {
            validationError,
            serverErrors,
            hasServerErrors,
            workflowValidationError,
            workflowName,
            workflowDescription,
            workflowScope,
            subjectType,
            savedSubjectType,
            triggerType,
            triggerConfig,
            conditions,
            conditionLogic,
            actions,
            isSaving,
        },
        options: {
            triggerTypeOptions,
            actionTypeOptions,
            filteredActionTypes,
            formOptions,
            statusOptions,
            activeStatusOptions,
            updateFields,
            userOptions,
            queueOptions,
            messageTemplates,
            emailTemplates,
            emailRecipientOptions,
            conditionOperators,
            availableConditionFields,
            selectedTriggerFields,
            isSharedDonorTriggerForm,
            configuredIntakeLeadKind,
            isDonorIntakeTrigger,
            getConditionOptions,
        },
        handlers: {
            setWorkflowName,
            setWorkflowDescription,
            setSubjectType,
            setTriggerType,
            setTriggerConfig,
            setIntakeApplicantType,
            setConditionLogic,
            addCondition,
            removeCondition,
            updateCondition,
            addAction,
            removeAction,
            moveAction,
            updateAction,
            updateActionType,
            saveWorkflow,
        },
    }
}

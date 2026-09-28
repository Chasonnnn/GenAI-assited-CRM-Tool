"use client"

import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { EmptyState } from "@/components/empty-state"
import { LoadErrorState } from "@/components/error-state"
import { LightbulbIcon, Loader2Icon, MoreVerticalIcon, PencilIcon, PlusIcon, TrashIcon } from "lucide-react"
import { toast } from "@/components/ui/toast"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { createSelectLabelGetter } from "@/lib/select-labels"
import { usePipelines } from "@/lib/hooks/use-pipelines"
import {
  createIntelligentSuggestionRule,
  deleteIntelligentSuggestionRule,
  getIntelligentSuggestionRules,
  getIntelligentSuggestionSettings,
  getIntelligentSuggestionTemplates,
  updateIntelligentSuggestionRule,
  updateIntelligentSuggestionSettings,
  type IntelligentSuggestionRule,
  type IntelligentSuggestionSettings,
  type IntelligentSuggestionTemplate,
} from "@/lib/api/settings"

type StageOption = {
  value: string
  slug: string
  stageKey: string
  label: string
}

type IntelligentSuggestionRuleDraft = {
  template_key: string
  name: string
  stage_slug: string
  business_days: number
  enabled: boolean
  sort_order: number
}

type IntelligentSuggestionsState = {
  settings: IntelligentSuggestionSettings | null
  rules: IntelligentSuggestionRule[] | null
  newRuleDraft: IntelligentSuggestionRuleDraft | null
  editingRuleId: string | null
  editingRuleDraft: IntelligentSuggestionRuleDraft | null
  saving: boolean
  ruleSaving: boolean
  error: string | null
}

type PipelineStageLike = {
  slug?: string
  status?: string
  stage_key?: string
  label?: string
  is_active?: boolean
  order?: number
}

type PipelineLike = {
  stages?: ReadonlyArray<PipelineStageLike | Record<string, unknown>> | null
}

const INTELLIGENT_SUGGESTION_SETTINGS_QUERY_KEY = ["settings", "intelligent-suggestions"] as const
const INTELLIGENT_SUGGESTION_TEMPLATES_QUERY_KEY = ["settings", "intelligent-suggestions", "templates"] as const
const INTELLIGENT_SUGGESTION_RULES_QUERY_KEY = ["settings", "intelligent-suggestions", "rules"] as const
const INTELLIGENT_SUGGESTIONS_STALE_TIME_MS = 30_000

function resolveStateUpdate<T>(updater: React.SetStateAction<T>, current: T): T {
  return typeof updater === "function"
    ? (updater as (previous: T) => T)(current)
    : updater
}

const DUPLICATE_RULE_MESSAGE = "A rule with this template, stage and threshold already exists."

const DIGEST_HOUR_LABELS: Record<string, string> = Object.fromEntries(
  Array.from({ length: 24 }, (_, hour) => {
    const suffix = hour < 12 ? "AM" : "PM"
    const displayHour = hour % 12 === 0 ? 12 : hour % 12
    return [String(hour), `${displayHour}:00 ${suffix}`]
  }),
)
const getDigestHourLabel = createSelectLabelGetter(DIGEST_HOUR_LABELS, {
  emptyLabel: "Select hour",
  unknownLabel: "Unknown hour",
})

/** Stages in pipeline order (the order the pipeline editor shows), first pipeline first. */
function buildStageOptions(pipelines: ReadonlyArray<PipelineLike> | null | undefined): StageOption[] {
  const byValue = new Map<string, StageOption>()
  for (const pipeline of pipelines ?? []) {
    const orderedStages = [...(pipeline.stages ?? [])]
      .map((rawStage, index) => ({ stage: rawStage as PipelineStageLike, index }))
      .sort(
        (left, right) =>
          (left.stage.order ?? left.index) - (right.stage.order ?? right.index) || left.index - right.index,
      )
    for (const { stage } of orderedStages) {
      const slug = stage.slug ?? stage.status
      const stageKey = stage.stage_key ?? slug
      if (!slug || !stageKey || stage.is_active === false) continue
      if (!byValue.has(stageKey)) {
        byValue.set(stageKey, {
          value: stageKey,
          slug,
          stageKey,
          label: stage.label ?? stageKey,
        })
      }
    }
  }
  return Array.from(byValue.values())
}

/** The stage a rule targets, as a stage key, so key and slug references compare equal. */
function resolveRuleStageKey(
  stageRef: string | null | undefined,
  stageOptions: StageOption[],
): string | null {
  const normalized = (stageRef ?? "").trim()
  if (!normalized) return null
  const option = stageOptions.find((candidate) => candidate.value === normalized || candidate.slug === normalized)
  return option?.stageKey ?? normalized
}

/** Mirrors the API check: one rule per template, stage and business-day threshold. */
function findDuplicateRule(
  rules: IntelligentSuggestionRule[],
  draft: IntelligentSuggestionRuleDraft,
  stageOptions: StageOption[],
  excludeRuleId?: string,
): IntelligentSuggestionRule | undefined {
  const draftStage = resolveRuleStageKey(draft.stage_slug, stageOptions)
  return rules.find(
    (rule) =>
      rule.id !== excludeRuleId &&
      rule.template_key === draft.template_key &&
      rule.business_days === draft.business_days &&
      resolveRuleStageKey(rule.stage_key ?? rule.stage_slug, stageOptions) === draftStage,
  )
}

function buildStageLabelByRef(stageOptions: StageOption[]): Map<string, string> {
  return new Map(
    stageOptions.flatMap((option) => [
      [option.value, option.label] as const,
      [option.slug, option.label] as const,
    ]),
  )
}

function buildStageOptionByValue(stageOptions: StageOption[]): Map<string, StageOption> {
  return new Map(stageOptions.map((option) => [option.value, option]))
}

function buildTemplateByKey(
  templates: IntelligentSuggestionTemplate[],
): Map<string, IntelligentSuggestionTemplate> {
  return new Map(templates.map((template) => [template.template_key, template]))
}

function requiresStageSelection(template: IntelligentSuggestionTemplate | undefined): boolean {
  if (!template) return false
  return template.rule_kind === "stage_inactivity" && template.template_key !== "preapproval_stuck"
}

function resolveStageSlug(
  template: IntelligentSuggestionTemplate | undefined,
  stageSlug: string | null | undefined,
  stageOptions: StageOption[],
): string {
  if (!template || !requiresStageSelection(template)) return ""
  const normalized = (stageSlug ?? "").trim()
  if (normalized) {
    const matchingOption = stageOptions.find(
      (option) => option.value === normalized || option.slug === normalized,
    )
    if (matchingOption) {
      return matchingOption.value
    }
  }
  const defaultStage = (template.default_stage_key ?? template.default_stage_slug ?? "").trim()
  if (defaultStage) {
    const matchingDefault = stageOptions.find(
      (option) => option.value === defaultStage || option.slug === defaultStage,
    )
    if (matchingDefault) {
      return matchingDefault.value
    }
  }
  return stageOptions[0]?.value ?? defaultStage
}

function buildRuleDraft(
  template: IntelligentSuggestionTemplate | undefined,
  sortOrder: number,
  stageOptions: StageOption[],
  overrides: Partial<IntelligentSuggestionRuleDraft> = {},
): IntelligentSuggestionRuleDraft | null {
  if (!template) return null
  return {
    template_key: template.template_key,
    name: overrides.name ?? template.name,
    stage_slug: resolveStageSlug(
      template,
      overrides.stage_slug ?? template.default_stage_key ?? template.default_stage_slug,
      stageOptions,
    ),
    business_days: overrides.business_days ?? template.default_business_days,
    enabled: overrides.enabled ?? true,
    sort_order: overrides.sort_order ?? sortOrder,
  }
}

function formatStageLabel(stageLabelByRef: Map<string, string>, stageRef: string | null | undefined): string {
  if (!stageRef) return "N/A"
  return stageLabelByRef.get(stageRef) ?? "Unknown stage"
}

function SuggestionStageInput({
  id,
  value,
  onChange,
  disabled = false,
  stageOptions,
  stageLabelByRef,
}: {
  id: string
  value: string
  onChange: (nextValue: string | null) => void
  disabled?: boolean
  stageOptions: StageOption[]
  stageLabelByRef: Map<string, string>
}) {
  if (stageOptions.length > 0) {
    return (
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger id={id}>
          <SelectValue placeholder="Select stage">
            {(selected: string | null) => {
              if (!selected) return "Select stage"
              return stageLabelByRef.get(selected) ?? "Unknown stage"
            }}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {stageOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }

  return (
    <Input
      id={id}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      placeholder="Stage key (for example: new_unread)"
    />
  )
}

function WorkflowRuleComposer({
  templates,
  templateByKey,
  newRuleDraft,
  newRuleTemplate,
  newRuleNeedsStage,
  ruleSaving,
  duplicateError,
  stageOptions,
  stageLabelByRef,
  onTemplateChange,
  onAddRule,
  onDraftChange,
}: {
  templates: IntelligentSuggestionTemplate[]
  templateByKey: Map<string, IntelligentSuggestionTemplate>
  newRuleDraft: IntelligentSuggestionRuleDraft | null
  newRuleTemplate: IntelligentSuggestionTemplate | undefined
  newRuleNeedsStage: boolean
  ruleSaving: boolean
  duplicateError: string | null
  stageOptions: StageOption[]
  stageLabelByRef: Map<string, string>
  onTemplateChange: (templateKey: string | null) => void
  onAddRule: () => Promise<void>
  onDraftChange: (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => void
}) {
  // The default draft often matches an existing rule (on load and right after an add), so the
  // duplicate error waits until the user edits the draft or clicks Add Rule.
  const [duplicateVisible, setDuplicateVisible] = useState(false)
  const visibleDuplicateError = duplicateVisible ? duplicateError : null
  const handleTemplateChange = (templateKey: string | null) => {
    setDuplicateVisible(true)
    onTemplateChange(templateKey)
  }
  const handleDraftChange = (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => {
    setDuplicateVisible(true)
    onDraftChange(updater)
  }
  const handleAddRule = async () => {
    if (duplicateError) {
      setDuplicateVisible(true)
      return
    }
    await onAddRule()
    setDuplicateVisible(false)
  }

  return (
    <div className="rounded-lg border border-border p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="font-medium">Add Workflow Rule</p>
        <Button
          variant="outline"
          onClick={() => void handleAddRule()}
          disabled={ruleSaving || !newRuleDraft || templates.length === 0 || visibleDuplicateError !== null}
        >
          <PlusIcon className="mr-2 size-4" aria-hidden="true" />
          Add Rule
        </Button>
      </div>

      {newRuleDraft ? (
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="new-rule-template">Template</Label>
            <Select
              value={newRuleDraft.template_key}
              onValueChange={handleTemplateChange}
              disabled={ruleSaving || templates.length === 0}
            >
              <SelectTrigger id="new-rule-template">
                <SelectValue placeholder="Select template">
                  {(selected: string | null) => {
                    if (!selected) return "Select template"
                    return templateByKey.get(selected)?.name ?? "Unknown template"
                  }}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {templates.map((template) => (
                  <SelectItem key={template.template_key} value={template.template_key}>
                    {template.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {newRuleTemplate && (
              <p className="text-xs text-muted-foreground">{newRuleTemplate.description}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-rule-name">Rule name</Label>
            <Input
              id="new-rule-name"
              value={newRuleDraft.name}
              disabled={ruleSaving}
              onChange={(event) =>
                handleDraftChange((previous) => (previous ? { ...previous, name: event.target.value } : previous))
              }
            />
          </div>

          {newRuleNeedsStage && (
            <div className="space-y-2">
              <Label htmlFor="new-rule-stage">Stage</Label>
              <SuggestionStageInput
                id="new-rule-stage"
                value={newRuleDraft.stage_slug}
                onChange={(nextStage) =>
                  handleDraftChange((previous) =>
                    nextStage && previous ? { ...previous, stage_slug: nextStage } : previous,
                  )
                }
                disabled={ruleSaving}
                stageOptions={stageOptions}
                stageLabelByRef={stageLabelByRef}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="new-rule-days">Business days</Label>
            <Input
              id="new-rule-days"
              type="number"
              min={1}
              max={60}
              disabled={ruleSaving}
              value={newRuleDraft.business_days}
              onChange={(event) => {
                const parsed = Number.parseInt(event.target.value, 10)
                const normalized = Number.isFinite(parsed) ? parsed : newRuleDraft.business_days
                handleDraftChange((previous) =>
                  previous ? { ...previous, business_days: Math.max(1, Math.min(60, normalized)) } : previous,
                )
              }}
            />
          </div>

          {visibleDuplicateError ? (
            <p role="alert" className="text-sm text-destructive md:col-span-2">
              {visibleDuplicateError}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No templates available. Reload to retry.</p>
      )}
    </div>
  )
}

function WorkflowRulesTable({
  rules,
  templateByKey,
  ruleSaving,
  getRuleStageLabel,
  onToggleEnabled,
  onStartEdit,
  onRequestDelete,
}: {
  rules: IntelligentSuggestionRule[]
  templateByKey: Map<string, IntelligentSuggestionTemplate>
  ruleSaving: boolean
  getRuleStageLabel: (rule: IntelligentSuggestionRule) => string
  onToggleEnabled: (rule: IntelligentSuggestionRule) => Promise<void>
  onStartEdit: (rule: IntelligentSuggestionRule) => void
  onRequestDelete: (rule: IntelligentSuggestionRule) => void
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Rule</TableHead>
          <TableHead>Template</TableHead>
          <TableHead>Stage</TableHead>
          <TableHead className="text-right">Business days</TableHead>
          <TableHead className="text-right">Priority</TableHead>
          <TableHead>Enabled</TableHead>
          <TableHead className="w-12">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rules.map((rule) => (
          <TableRow key={rule.id}>
            <TableCell className="font-medium">{rule.name}</TableCell>
            <TableCell>{templateByKey.get(rule.template_key)?.name ?? "Unknown template"}</TableCell>
            <TableCell>{getRuleStageLabel(rule)}</TableCell>
            <TableCell className="text-right tabular-nums">{rule.business_days}</TableCell>
            <TableCell className="text-right tabular-nums">{rule.sort_order}</TableCell>
            <TableCell>
              <Switch
                checked={rule.enabled}
                disabled={ruleSaving}
                onCheckedChange={() => void onToggleEnabled(rule)}
                aria-label={`Enable ${rule.name}`}
              />
            </TableCell>
            <TableCell>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={<Button variant="ghost" size="icon-sm" disabled={ruleSaving} />}
                  aria-label={`Actions for ${rule.name}`}
                >
                  <MoreVerticalIcon aria-hidden="true" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onStartEdit(rule)}>
                    <PencilIcon aria-hidden="true" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem variant="destructive" onClick={() => onRequestDelete(rule)}>
                    <TrashIcon aria-hidden="true" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function EditRuleDialog({
  rule,
  editingRuleDraft,
  editingNeedsStage,
  duplicateError,
  ruleSaving,
  stageOptions,
  stageLabelByRef,
  onEditingDraftChange,
  onSaveEdit,
  onCancelEdit,
}: {
  rule: IntelligentSuggestionRule | undefined
  editingRuleDraft: IntelligentSuggestionRuleDraft | null
  editingNeedsStage: boolean
  duplicateError: string | null
  ruleSaving: boolean
  stageOptions: StageOption[]
  stageLabelByRef: Map<string, string>
  onEditingDraftChange: (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => void
  onSaveEdit: () => Promise<void>
  onCancelEdit: () => void
}) {
  const open = Boolean(rule && editingRuleDraft)
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !ruleSaving) onCancelEdit()
      }}
    >
      <DialogContent>
      {rule && editingRuleDraft ? (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void onSaveEdit()
          }}
          noValidate
        >
          <DialogHeader>
            <DialogTitle>Edit {rule.name}</DialogTitle>
          </DialogHeader>
          <DialogBody>
          <div className="grid gap-3 py-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor={`edit-rule-name-${rule.id}`}>Rule name</Label>
              <Input
                id={`edit-rule-name-${rule.id}`}
                value={editingRuleDraft.name}
                disabled={ruleSaving}
                onChange={(event) =>
                  onEditingDraftChange((previous) =>
                    previous ? { ...previous, name: event.target.value } : previous,
                  )
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor={`edit-rule-days-${rule.id}`}>Business days</Label>
              <Input
                id={`edit-rule-days-${rule.id}`}
                type="number"
                min={1}
                max={60}
                disabled={ruleSaving}
                value={editingRuleDraft.business_days}
                onChange={(event) => {
                  const parsed = Number.parseInt(event.target.value, 10)
                  const normalized = Number.isFinite(parsed) ? parsed : editingRuleDraft.business_days
                  onEditingDraftChange((previous) =>
                    previous
                      ? { ...previous, business_days: Math.max(1, Math.min(60, normalized)) }
                      : previous,
                  )
                }}
              />
            </div>

            {editingNeedsStage && (
              <div className="space-y-2">
                <Label htmlFor={`edit-rule-stage-${rule.id}`}>Stage</Label>
                <SuggestionStageInput
                  id={`edit-rule-stage-${rule.id}`}
                  value={editingRuleDraft.stage_slug}
                  onChange={(nextStage) =>
                    onEditingDraftChange((previous) =>
                      nextStage && previous ? { ...previous, stage_slug: nextStage } : previous,
                    )
                  }
                  disabled={ruleSaving}
                  stageOptions={stageOptions}
                  stageLabelByRef={stageLabelByRef}
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor={`edit-rule-priority-${rule.id}`}>Priority</Label>
              <Input
                id={`edit-rule-priority-${rule.id}`}
                type="number"
                min={0}
                disabled={ruleSaving}
                value={editingRuleDraft.sort_order}
                onChange={(event) => {
                  const parsed = Number.parseInt(event.target.value, 10)
                  const normalized = Number.isFinite(parsed) ? parsed : editingRuleDraft.sort_order
                  onEditingDraftChange((previous) =>
                    previous ? { ...previous, sort_order: Math.max(0, normalized) } : previous,
                  )
                }}
              />
            </div>

            {duplicateError ? (
              <p role="alert" className="text-sm text-destructive md:col-span-2">
                {duplicateError}
              </p>
            ) : null}
          </div>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={ruleSaving} onClick={onCancelEdit}>
              Cancel
            </Button>
            <Button type="submit" disabled={ruleSaving || duplicateError !== null}>
              {ruleSaving ? (
                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
              ) : null}
              Save Rule
            </Button>
          </DialogFooter>
        </form>
      ) : null}
      </DialogContent>
    </Dialog>
  )
}

function DailyDigestSettingsCard({
  settings,
  saving,
  onSettingsPatch,
}: {
  settings: IntelligentSuggestionSettings
  saving: boolean
  onSettingsPatch: (patch: Partial<IntelligentSuggestionSettings>, successMessage: string) => Promise<void>
}) {
  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Label htmlFor="daily-digest-enabled" className="font-medium">Daily digest notifications</Label>
        <Switch
          id="daily-digest-enabled"
          disabled={!settings.enabled || saving}
          checked={settings.daily_digest_enabled}
          onCheckedChange={(checked) =>
            void onSettingsPatch(
              { daily_digest_enabled: checked },
              checked ? "Daily digest turned on" : "Daily digest turned off",
            )
          }
        />
      </div>
      <div className="space-y-2 max-w-xs">
        <Label htmlFor="digest-hour">Digest hour (organization time)</Label>
        <Select
          value={String(settings.digest_hour_local)}
          onValueChange={(value) => {
            if (value === null || value === String(settings.digest_hour_local)) return
            void onSettingsPatch(
              { digest_hour_local: Number(value) },
              `Digest time set to ${getDigestHourLabel(value)}`,
            )
          }}
          disabled={!settings.enabled || !settings.daily_digest_enabled || saving}
        >
          <SelectTrigger id="digest-hour" className="w-40">
            <SelectValue placeholder="Select hour">{getDigestHourLabel}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {Object.entries(DIGEST_HOUR_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

function useIntelligentSuggestionsController() {
  const [suggestionState, setSuggestionState] = useState<IntelligentSuggestionsState>({
    settings: null,
    rules: null,
    newRuleDraft: null,
    editingRuleId: null,
    editingRuleDraft: null,
    saving: false,
    ruleSaving: false,
    error: null,
  })
  const [pendingDeleteRule, setPendingDeleteRule] = useState<IntelligentSuggestionRule | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const { data: pipelines } = usePipelines()
  const queryClient = useQueryClient()
  const settingsQuery = useQuery({
    queryKey: INTELLIGENT_SUGGESTION_SETTINGS_QUERY_KEY,
    queryFn: getIntelligentSuggestionSettings,
    staleTime: INTELLIGENT_SUGGESTIONS_STALE_TIME_MS,
  })
  const templatesQuery = useQuery({
    queryKey: INTELLIGENT_SUGGESTION_TEMPLATES_QUERY_KEY,
    queryFn: getIntelligentSuggestionTemplates,
    staleTime: INTELLIGENT_SUGGESTIONS_STALE_TIME_MS,
  })
  const rulesQuery = useQuery({
    queryKey: INTELLIGENT_SUGGESTION_RULES_QUERY_KEY,
    queryFn: getIntelligentSuggestionRules,
    staleTime: INTELLIGENT_SUGGESTIONS_STALE_TIME_MS,
  })
  const {
    settings: settingsOverride,
    rules: rulesOverride,
    newRuleDraft: newRuleDraftOverride,
    editingRuleId,
    editingRuleDraft,
    saving,
    ruleSaving,
    error: localError,
  } = suggestionState

  const stageOptions = buildStageOptions(pipelines)
  const hasLoadedData =
    settingsQuery.data !== undefined &&
    templatesQuery.data !== undefined &&
    rulesQuery.data !== undefined
  const settings = hasLoadedData ? settingsOverride ?? settingsQuery.data : null
  const templates = hasLoadedData ? templatesQuery.data : []
  const rules = hasLoadedData ? rulesOverride ?? rulesQuery.data : []
  const templateSeed = templates.find((template) => template.is_default) ?? templates[0]
  const defaultNewRuleDraft = templateSeed
    ? buildRuleDraft(templateSeed, (rules.at(-1)?.sort_order ?? 0) + 1, stageOptions)
    : null
  const newRuleDraft = newRuleDraftOverride ?? defaultNewRuleDraft
  const loading =
    settingsQuery.isLoading ||
    templatesQuery.isLoading ||
    rulesQuery.isLoading
  const hasLoadError =
    settingsQuery.isError ||
    templatesQuery.isError ||
    rulesQuery.isError
  const error = localError ?? (hasLoadError ? "Unable to load settings. Please retry." : null)

  const setSettings = (updater: React.SetStateAction<IntelligentSuggestionSettings | null>) => {
    setSuggestionState((current) => ({
      ...current,
      settings: resolveStateUpdate(updater, current.settings ?? settingsQuery.data ?? null),
    }))
  }

  const setRules = (updater: React.SetStateAction<IntelligentSuggestionRule[]>) => {
    const queryRules = rulesQuery.data ?? []
    setSuggestionState((current) => ({
      ...current,
      rules: resolveStateUpdate(updater, current.rules ?? queryRules),
    }))
    queryClient.setQueryData<IntelligentSuggestionRule[]>(
      INTELLIGENT_SUGGESTION_RULES_QUERY_KEY,
      (current) => resolveStateUpdate(updater, current ?? queryRules),
    )
  }

  const setNewRuleDraft = (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => {
    setSuggestionState((current) => ({
      ...current,
      newRuleDraft: resolveStateUpdate(
        updater,
        current.newRuleDraft ?? defaultNewRuleDraft,
      ),
    }))
  }

  const setEditingRuleId = (updater: React.SetStateAction<string | null>) => {
    setSuggestionState((current) => ({
      ...current,
      editingRuleId: resolveStateUpdate(updater, current.editingRuleId),
    }))
  }

  const setEditingRuleDraft = (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => {
    setSuggestionState((current) => ({
      ...current,
      editingRuleDraft: resolveStateUpdate(updater, current.editingRuleDraft),
    }))
  }

  const setSaving = (updater: React.SetStateAction<boolean>) => {
    setSuggestionState((current) => ({
      ...current,
      saving: resolveStateUpdate(updater, current.saving),
    }))
  }

  const setRuleSaving = (updater: React.SetStateAction<boolean>) => {
    setSuggestionState((current) => ({
      ...current,
      ruleSaving: resolveStateUpdate(updater, current.ruleSaving),
    }))
  }

  const setError = (updater: React.SetStateAction<string | null>) => {
    setSuggestionState((current) => ({
      ...current,
      error: resolveStateUpdate(updater, current.error),
    }))
  }

  const stageLabelByRef = buildStageLabelByRef(stageOptions)
  const stageOptionByValue = buildStageOptionByValue(stageOptions)
  const templateByKey = buildTemplateByKey(templates)

  const loadSettings = async () => {
    setError(null)
    await Promise.all([
      settingsQuery.refetch(),
      templatesQuery.refetch(),
      rulesQuery.refetch(),
    ])
  }

  const normalizedNewRuleDraft = (() => {
    if (!newRuleDraft) return null
    const template = templateByKey.get(newRuleDraft.template_key)
    if (!requiresStageSelection(template)) return newRuleDraft
    const normalizedStage = resolveStageSlug(template, newRuleDraft.stage_slug, stageOptions)
    if (normalizedStage && normalizedStage !== newRuleDraft.stage_slug) {
      return { ...newRuleDraft, stage_slug: normalizedStage }
    }
    return newRuleDraft
  })()

  const newRuleDuplicateError =
    normalizedNewRuleDraft && findDuplicateRule(rules, normalizedNewRuleDraft, stageOptions)
      ? DUPLICATE_RULE_MESSAGE
      : null
  const editingDuplicateError =
    editingRuleId && editingRuleDraft && findDuplicateRule(rules, editingRuleDraft, stageOptions, editingRuleId)
      ? DUPLICATE_RULE_MESSAGE
      : null

  /** Toggles and single selects save at once and roll back when the request fails. */
  const saveSettingsPatch = async (
    patch: Partial<IntelligentSuggestionSettings>,
    successMessage: string,
  ) => {
    if (!settings) return
    const previous = settings
    setSettings({ ...settings, ...patch })
    setSaving(true)
    try {
      const updated = await updateIntelligentSuggestionSettings(patch)
      setSettings(updated)
      queryClient.setQueryData(INTELLIGENT_SUGGESTION_SETTINGS_QUERY_KEY, updated)
      toast.success(successMessage)
    } catch (saveError) {
      setSettings(previous)
      const message = getActionErrorMessage(saveError, "Couldn't save this setting. Try again.")
      if (message) toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  const handleNewRuleTemplateChange = (templateKey: string | null) => {
    if (!templateKey) return
    const template = templateByKey.get(templateKey)
    if (!template) return
    setNewRuleDraft((previous) =>
      buildRuleDraft(template, previous?.sort_order ?? (rules.at(-1)?.sort_order ?? 0) + 1, stageOptions, {
        enabled: previous?.enabled ?? true,
      }),
    )
  }

  const handleCreateRule = async () => {
    if (!normalizedNewRuleDraft || newRuleDuplicateError) return
    const template = templateByKey.get(normalizedNewRuleDraft.template_key)
    if (!template) {
      toast.error("Select a valid rule template")
      return
    }
    const stageSlug = requiresStageSelection(template)
      ? resolveStageSlug(template, normalizedNewRuleDraft.stage_slug, stageOptions)
      : null
    if (requiresStageSelection(template) && !stageSlug) {
      toast.error("Select a stage for this workflow rule")
      return
    }

    setRuleSaving(true)
    try {
      const selectedStage = stageSlug ? stageOptionByValue.get(stageSlug) : null
      const createdRule = await createIntelligentSuggestionRule({
        template_key: template.template_key,
        name: normalizedNewRuleDraft.name.trim() || template.name,
        stage_key: selectedStage?.stageKey ?? stageSlug,
        stage_slug: selectedStage?.slug ?? stageSlug,
        business_days: Math.max(1, Math.min(60, normalizedNewRuleDraft.business_days)),
        enabled: normalizedNewRuleDraft.enabled,
      })
      setRules((previous) =>
        [...previous, createdRule].sort((left, right) => left.sort_order - right.sort_order),
      )
      const resetDraft = buildRuleDraft(template, createdRule.sort_order + 1, stageOptions, { enabled: true })
      if (resetDraft) setNewRuleDraft(resetDraft)
      toast.success("Workflow rule created")
    } catch (ruleError) {
      const message = getActionErrorMessage(ruleError, "Couldn't create the rule. Try again.")
      if (message) toast.error(message)
    }
    setRuleSaving(false)
  }

  const handleToggleRuleEnabled = async (rule: IntelligentSuggestionRule) => {
    setRuleSaving(true)
    try {
      const updatedRule = await updateIntelligentSuggestionRule(rule.id, { enabled: !rule.enabled })
      setRules((previous) =>
        previous.map((current) => (current.id === rule.id ? updatedRule : current)),
      )
      if (editingRuleId === rule.id) {
        setEditingRuleDraft((currentDraft) =>
          currentDraft ? { ...currentDraft, enabled: updatedRule.enabled } : currentDraft,
        )
      }
      toast.success(`Rule ${updatedRule.enabled ? "enabled" : "disabled"}`)
    } catch (ruleError) {
      const message = getActionErrorMessage(ruleError, "Couldn't update the rule. Try again.")
      if (message) toast.error(message)
    }
    setRuleSaving(false)
  }

  const startEditingRule = (rule: IntelligentSuggestionRule) => {
    const template = templateByKey.get(rule.template_key)
    const nextDraft = buildRuleDraft(template, rule.sort_order, stageOptions, {
      name: rule.name,
      stage_slug: rule.stage_key ?? rule.stage_slug ?? template?.default_stage_key ?? template?.default_stage_slug ?? "",
      business_days: rule.business_days,
      enabled: rule.enabled,
      sort_order: rule.sort_order,
    })
    if (!nextDraft) return
    setEditingRuleId(rule.id)
    setEditingRuleDraft(nextDraft)
  }

  const cancelEditingRule = () => {
    setEditingRuleId(null)
    setEditingRuleDraft(null)
  }

  const handleSaveEditingRule = async () => {
    if (!editingRuleId || !editingRuleDraft || editingDuplicateError) return
    const template = templateByKey.get(editingRuleDraft.template_key)
    if (!template) {
      toast.error("Unknown template for rule")
      return
    }
    const stageSlug = requiresStageSelection(template)
      ? resolveStageSlug(template, editingRuleDraft.stage_slug, stageOptions)
      : null
    if (requiresStageSelection(template) && !stageSlug) {
      toast.error("Select a stage for this workflow rule")
      return
    }

    setRuleSaving(true)
    try {
      const selectedStage = stageSlug ? stageOptionByValue.get(stageSlug) : null
      const updatedRule = await updateIntelligentSuggestionRule(editingRuleId, {
        name: editingRuleDraft.name.trim() || template.name,
        stage_key: selectedStage?.stageKey ?? stageSlug,
        stage_slug: selectedStage?.slug ?? stageSlug,
        business_days: Math.max(1, Math.min(60, editingRuleDraft.business_days)),
        enabled: editingRuleDraft.enabled,
        sort_order: Math.max(0, editingRuleDraft.sort_order),
      })
      setRules((previous) =>
        previous
          .map((rule) => (rule.id === editingRuleId ? updatedRule : rule))
          .sort((left, right) => left.sort_order - right.sort_order),
      )
      cancelEditingRule()
      toast.success("Workflow rule updated")
    } catch (ruleError) {
      const message = getActionErrorMessage(ruleError, "Couldn't update the rule. Try again.")
      if (message) toast.error(message)
    }
    setRuleSaving(false)
  }

  const requestDeleteRule = (rule: IntelligentSuggestionRule) => {
    setPendingDeleteRule(rule)
    setDeleteOpen(true)
  }

  // ConfirmDialog stays open while this runs and shows a rejection inline.
  const confirmDeleteRule = async () => {
    if (!pendingDeleteRule) return
    const rule = pendingDeleteRule
    await deleteIntelligentSuggestionRule(rule.id)
    setRules((previous) => previous.filter((current) => current.id !== rule.id))
    if (editingRuleId === rule.id) cancelEditingRule()
    toast.success("Workflow rule deleted")
  }

  const getRuleStageLabel = (rule: IntelligentSuggestionRule) => {
    if (rule.template_key === "preapproval_stuck") {
      return "Intake Pre-approval Stages"
    }
    return rule.stage_label ?? formatStageLabel(stageLabelByRef, rule.stage_key ?? rule.stage_slug)
  }

  return {
    settings,
    templates,
    rules,
    newRuleDraft: normalizedNewRuleDraft,
    editingRuleId,
    editingRuleDraft,
    loading,
    hasLoadError,
    saving,
    ruleSaving,
    error,
    newRuleDuplicateError,
    editingDuplicateError,
    pendingDeleteRule,
    deleteOpen,
    setDeleteOpen,
    stageOptions,
    stageLabelByRef,
    templateByKey,
    newRuleTemplate: normalizedNewRuleDraft ? templateByKey.get(normalizedNewRuleDraft.template_key) : undefined,
    newRuleNeedsStage: requiresStageSelection(
      normalizedNewRuleDraft ? templateByKey.get(normalizedNewRuleDraft.template_key) : undefined,
    ),
    rulesPaused: settings ? !settings.enabled : false,
    requiresStageSelection,
    setNewRuleDraft,
    setEditingRuleDraft,
    saveSettingsPatch,
    loadSettings,
    handleNewRuleTemplateChange,
    handleCreateRule,
    handleToggleRuleEnabled,
    startEditingRule,
    cancelEditingRule,
    handleSaveEditingRule,
    requestDeleteRule,
    confirmDeleteRule,
    getRuleStageLabel,
  }
}

export function IntelligentSuggestionsSection() {
  const controller = useIntelligentSuggestionsController()

  if (controller.loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2Icon className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden="true" />
      </div>
    )
  }

  if (!controller.settings) {
    return (
      <LoadErrorState
        title="Couldn't load intelligent suggestions"
        onRetry={() => void controller.loadSettings()}
        className="min-h-0 py-10"
      />
    )
  }

  const settings = controller.settings
  const editingRule = controller.editingRuleId
    ? controller.rules.find((rule) => rule.id === controller.editingRuleId)
    : undefined
  const editingTemplate = controller.editingRuleDraft
    ? controller.templateByKey.get(controller.editingRuleDraft.template_key)
    : undefined

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-border p-4">
          <Label htmlFor="intelligent-suggestions-enabled" className="font-medium">
            Enable Intelligent Suggestions
          </Label>
          <Switch
            id="intelligent-suggestions-enabled"
            checked={settings.enabled}
            disabled={controller.saving}
            onCheckedChange={(checked) =>
              void controller.saveSettingsPatch(
                { enabled: checked },
                checked ? "Intelligent suggestions turned on" : "Intelligent suggestions turned off",
              )
            }
          />
        </div>

        {controller.rulesPaused && (
          <p className="text-sm text-muted-foreground">
            Intelligent suggestions are paused globally. You can still configure rules below.
          </p>
        )}

        <WorkflowRuleComposer
          templates={controller.templates}
          templateByKey={controller.templateByKey}
          newRuleDraft={controller.newRuleDraft}
          newRuleTemplate={controller.newRuleTemplate}
          newRuleNeedsStage={controller.newRuleNeedsStage}
          ruleSaving={controller.ruleSaving}
          duplicateError={controller.newRuleDuplicateError}
          stageOptions={controller.stageOptions}
          stageLabelByRef={controller.stageLabelByRef}
          onTemplateChange={controller.handleNewRuleTemplateChange}
          onAddRule={controller.handleCreateRule}
          onDraftChange={controller.setNewRuleDraft}
        />

        <div className="space-y-3">
          <p className="font-medium">Configured Workflow Rules</p>

          {controller.rules.length === 0 ? (
            <EmptyState icon={LightbulbIcon} title="No workflow rules" />
          ) : (
            <WorkflowRulesTable
              rules={controller.rules}
              templateByKey={controller.templateByKey}
              ruleSaving={controller.ruleSaving}
              getRuleStageLabel={controller.getRuleStageLabel}
              onToggleEnabled={controller.handleToggleRuleEnabled}
              onStartEdit={controller.startEditingRule}
              onRequestDelete={controller.requestDeleteRule}
            />
          )}
        </div>

        <DailyDigestSettingsCard
          settings={settings}
          saving={controller.saving}
          onSettingsPatch={controller.saveSettingsPatch}
        />
      </div>

      <EditRuleDialog
        rule={editingRule}
        editingRuleDraft={controller.editingRuleDraft}
        editingNeedsStage={controller.requiresStageSelection(editingTemplate)}
        duplicateError={controller.editingDuplicateError}
        ruleSaving={controller.ruleSaving}
        stageOptions={controller.stageOptions}
        stageLabelByRef={controller.stageLabelByRef}
        onEditingDraftChange={controller.setEditingRuleDraft}
        onSaveEdit={controller.handleSaveEditingRule}
        onCancelEdit={controller.cancelEditingRule}
      />

      <ConfirmDialog
        open={controller.deleteOpen}
        onOpenChange={controller.setDeleteOpen}
        title={`Delete ${controller.pendingDeleteRule?.name ?? "this rule"}?`}
        description="Suggestions from this rule stop."
        confirmLabel="Delete rule"
        errorFallback="Couldn't delete the rule. Try again."
        onConfirm={controller.confirmDeleteRule}
      />
    </div>
  )
}

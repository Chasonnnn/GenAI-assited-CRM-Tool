"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Loader2Icon, CheckIcon, PlusIcon, TrashIcon } from "lucide-react"
import { toast } from "sonner"
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
  templates: IntelligentSuggestionTemplate[]
  rules: IntelligentSuggestionRule[]
  newRuleDraft: IntelligentSuggestionRuleDraft | null
  editingRuleId: string | null
  editingRuleDraft: IntelligentSuggestionRuleDraft | null
  loading: boolean
  saving: boolean
  ruleSaving: boolean
  saved: boolean
  error: string | null
}

function resolveStateUpdate<T>(updater: React.SetStateAction<T>, current: T): T {
  return typeof updater === "function"
    ? (updater as (previous: T) => T)(current)
    : updater
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
              return stageLabelByRef.get(selected) ?? selected.replaceAll("_", " ")
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
  stageOptions: StageOption[]
  stageLabelByRef: Map<string, string>
  onTemplateChange: (templateKey: string | null) => void
  onAddRule: () => Promise<void>
  onDraftChange: (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => void
}) {
  return (
    <div className="rounded-lg border border-border p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">Add Workflow Rule</p>
          <p className="text-sm text-muted-foreground">
            Build rules like "stuck on stage X for Y business days" or "follow up after Y days."
          </p>
        </div>
        <Button
          variant="outline"
          onClick={onAddRule}
          disabled={ruleSaving || !newRuleDraft || templates.length === 0}
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
              onValueChange={onTemplateChange}
              disabled={ruleSaving || templates.length === 0}
            >
              <SelectTrigger id="new-rule-template">
                <SelectValue placeholder="Select template">
                  {(selected: string | null) => {
                    if (!selected) return "Select template"
                    return templateByKey.get(selected)?.name ?? selected.replaceAll("_", " ")
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
                onDraftChange((previous) => (previous ? { ...previous, name: event.target.value } : previous))
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
                  onDraftChange((previous) =>
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
                onDraftChange((previous) =>
                  previous ? { ...previous, business_days: Math.max(1, Math.min(60, normalized)) } : previous,
                )
              }}
            />
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No templates available. Reload to retry.</p>
      )}
    </div>
  )
}

function WorkflowRuleCard({
  rule,
  template,
  isEditing,
  editingRuleDraft,
  editingNeedsStage,
  ruleDescription,
  ruleStageLabel,
  ruleSaving,
  stageOptions,
  stageLabelByRef,
  onToggleEnabled,
  onStartEdit,
  onDelete,
  onEditingDraftChange,
  onSaveEdit,
  onCancelEdit,
}: {
  rule: IntelligentSuggestionRule
  template: IntelligentSuggestionTemplate | undefined
  isEditing: boolean
  editingRuleDraft: IntelligentSuggestionRuleDraft | null
  editingNeedsStage: boolean
  ruleDescription: string
  ruleStageLabel: string
  ruleSaving: boolean
  stageOptions: StageOption[]
  stageLabelByRef: Map<string, string>
  onToggleEnabled: (rule: IntelligentSuggestionRule) => Promise<void>
  onStartEdit: (rule: IntelligentSuggestionRule) => void
  onDelete: (rule: IntelligentSuggestionRule) => Promise<void>
  onEditingDraftChange: (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => void
  onSaveEdit: () => Promise<void>
  onCancelEdit: () => void
}) {
  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">{rule.name}</p>
          <p className="text-sm text-muted-foreground">{ruleDescription}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={rule.enabled ? "default" : "secondary"}>
            {rule.enabled ? "Enabled" : "Disabled"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            disabled={ruleSaving}
            onClick={() => void onToggleEnabled(rule)}
          >
            {rule.enabled ? "Disable" : "Enable"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={ruleSaving}
            onClick={() => onStartEdit(rule)}
          >
            Edit
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={ruleSaving}
            onClick={() => void onDelete(rule)}
          >
            <TrashIcon className="mr-1 size-4" aria-hidden="true" />
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-3 text-sm md:grid-cols-3">
        <p><span className="font-medium">Template:</span> {template?.name ?? rule.template_key}</p>
        <p><span className="font-medium">Stage:</span> {ruleStageLabel}</p>
        <p><span className="font-medium">Priority:</span> {rule.sort_order}</p>
      </div>

      {isEditing && editingRuleDraft && (
        <div className="rounded-md border border-border bg-muted/30 p-3 space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
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

            <div className="space-y-2">
              <Label htmlFor={`edit-rule-enabled-${rule.id}`}>Enabled</Label>
              <div className="flex h-10 items-center rounded-md border border-input px-3">
                <Switch
                  id={`edit-rule-enabled-${rule.id}`}
                  checked={editingRuleDraft.enabled}
                  disabled={ruleSaving}
                  onCheckedChange={(checked) =>
                    onEditingDraftChange((previous) =>
                      previous ? { ...previous, enabled: checked } : previous,
                    )
                  }
                />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" disabled={ruleSaving} onClick={() => void onSaveEdit()}>
              Save Rule
            </Button>
            <Button size="sm" variant="outline" disabled={ruleSaving} onClick={onCancelEdit}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function DailyDigestSettingsCard({
  settings,
  onSettingsChange,
  onDigestHourChange,
}: {
  settings: IntelligentSuggestionSettings
  onSettingsChange: (updater: React.SetStateAction<IntelligentSuggestionSettings | null>) => void
  onDigestHourChange: (rawValue: string) => void
}) {
  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="font-medium">Daily digest notifications</p>
        <Switch
          disabled={!settings.enabled}
          checked={settings.daily_digest_enabled}
          onCheckedChange={(checked) =>
            onSettingsChange((previous) =>
              previous ? { ...previous, daily_digest_enabled: checked } : previous,
            )
          }
        />
      </div>
      <p className="text-sm text-muted-foreground">
        Send a daily digest to users when suggestions are available.
      </p>
      <div className="space-y-2 max-w-xs">
        <Label htmlFor="digest-hour">Digest hour (local org time, 0-23)</Label>
        <Input
          id="digest-hour"
          type="number"
          min={0}
          max={23}
          disabled={!settings.enabled || !settings.daily_digest_enabled}
          value={settings.digest_hour_local}
          onChange={(event) => onDigestHourChange(event.target.value)}
        />
      </div>
    </div>
  )
}

function useIntelligentSuggestionsController() {
  const [suggestionState, setSuggestionState] = useState<IntelligentSuggestionsState>({
    settings: null,
    templates: [],
    rules: [],
    newRuleDraft: null,
    editingRuleId: null,
    editingRuleDraft: null,
    loading: true,
    saving: false,
    ruleSaving: false,
    saved: false,
    error: null,
  })
  const { data: pipelines } = usePipelines()
  const {
    settings,
    templates,
    rules,
    newRuleDraft,
    editingRuleId,
    editingRuleDraft,
    loading,
    saving,
    ruleSaving,
    saved,
    error,
  } = suggestionState

  const setSettings = (updater: React.SetStateAction<IntelligentSuggestionSettings | null>) => {
    setSuggestionState((current) => ({
      ...current,
      settings: resolveStateUpdate(updater, current.settings),
    }))
  }

  const setTemplates = (updater: React.SetStateAction<IntelligentSuggestionTemplate[]>) => {
    setSuggestionState((current) => ({
      ...current,
      templates: resolveStateUpdate(updater, current.templates),
    }))
  }

  const setRules = (updater: React.SetStateAction<IntelligentSuggestionRule[]>) => {
    setSuggestionState((current) => ({
      ...current,
      rules: resolveStateUpdate(updater, current.rules),
    }))
  }

  const setNewRuleDraft = (updater: React.SetStateAction<IntelligentSuggestionRuleDraft | null>) => {
    setSuggestionState((current) => ({
      ...current,
      newRuleDraft: resolveStateUpdate(updater, current.newRuleDraft),
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

  const setLoading = (updater: React.SetStateAction<boolean>) => {
    setSuggestionState((current) => ({
      ...current,
      loading: resolveStateUpdate(updater, current.loading),
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

  const setSaved = (updater: React.SetStateAction<boolean>) => {
    setSuggestionState((current) => ({
      ...current,
      saved: resolveStateUpdate(updater, current.saved),
    }))
  }

  const setError = (updater: React.SetStateAction<string | null>) => {
    setSuggestionState((current) => ({
      ...current,
      error: resolveStateUpdate(updater, current.error),
    }))
  }

  const stageOptions = useMemo(() => {
    const byValue = new Map<string, StageOption>()
    for (const pipeline of pipelines ?? []) {
      for (const rawStage of pipeline.stages ?? []) {
        const stage = rawStage as {
          slug?: string
          status?: string
          stage_key?: string
          label?: string
          is_active?: boolean
        }
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
    return Array.from(byValue.values()).sort((left, right) => left.label.localeCompare(right.label))
  }, [pipelines])

  const stageLabelByRef = useMemo(
    () =>
      new Map(
        stageOptions.flatMap((option) => [
          [option.value, option.label] as const,
          [option.slug, option.label] as const,
        ]),
      ),
    [stageOptions],
  )
  const stageOptionByValue = useMemo(
    () => new Map(stageOptions.map((option) => [option.value, option])),
    [stageOptions],
  )
  const templateByKey = useMemo(
    () => new Map(templates.map((template) => [template.template_key, template])),
    [templates],
  )

  const formatStageLabel = useCallback(
    (stageRef: string | null | undefined) => {
      if (!stageRef) return "N/A"
      return stageLabelByRef.get(stageRef) ?? stageRef.replaceAll("_", " ")
    },
    [stageLabelByRef],
  )

  const requiresStageSelection = useCallback((template: IntelligentSuggestionTemplate | undefined) => {
    if (!template) return false
    return template.rule_kind === "stage_inactivity" && template.template_key !== "preapproval_stuck"
  }, [])

  const resolveStageSlug = useCallback(
    (template: IntelligentSuggestionTemplate | undefined, stageSlug: string | null | undefined) => {
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
    },
    [requiresStageSelection, stageOptions],
  )

  const buildRuleDraft = useCallback(
    (
      template: IntelligentSuggestionTemplate | undefined,
      sortOrder: number,
      overrides: Partial<IntelligentSuggestionRuleDraft> = {},
    ): IntelligentSuggestionRuleDraft | null => {
      if (!template) return null
      return {
        template_key: template.template_key,
        name: overrides.name ?? template.name,
        stage_slug: resolveStageSlug(
          template,
          overrides.stage_slug ?? template.default_stage_key ?? template.default_stage_slug,
        ),
        business_days: overrides.business_days ?? template.default_business_days,
        enabled: overrides.enabled ?? true,
        sort_order: overrides.sort_order ?? sortOrder,
      }
    },
    [resolveStageSlug],
  )

  const loadSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [settingsResponse, templatesResponse, rulesResponse] = await Promise.all([
        getIntelligentSuggestionSettings(),
        getIntelligentSuggestionTemplates(),
        getIntelligentSuggestionRules(),
      ])
      setSettings(settingsResponse)
      setTemplates(templatesResponse)
      setRules(rulesResponse)
      const templateSeed = templatesResponse.find((template) => template.is_default) ?? templatesResponse[0]
      if (templateSeed) {
        const draft = buildRuleDraft(templateSeed, (rulesResponse.at(-1)?.sort_order ?? 0) + 1)
        if (draft) setNewRuleDraft(draft)
      }
    } catch (loadError) {
      console.error("Failed to load intelligent suggestion settings:", loadError)
      setError("Unable to load settings. Please retry.")
    } finally {
      setLoading(false)
    }
  }, [buildRuleDraft])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  useEffect(() => {
    if (!newRuleDraft || templates.length === 0) return
    const template = templateByKey.get(newRuleDraft.template_key)
    if (!requiresStageSelection(template)) return
    const normalizedStage = resolveStageSlug(template, newRuleDraft.stage_slug)
    if (normalizedStage && normalizedStage !== newRuleDraft.stage_slug) {
      setNewRuleDraft((previous) => (previous ? { ...previous, stage_slug: normalizedStage } : previous))
    }
  }, [newRuleDraft, templateByKey, templates, requiresStageSelection, resolveStageSlug])

  const setDigestField = (rawValue: string) => {
    const parsed = Number.parseInt(rawValue, 10)
    const normalized = Number.isFinite(parsed) ? parsed : settings?.digest_hour_local ?? 0
    setSettings((previous) =>
      previous ? { ...previous, digest_hour_local: Math.max(0, Math.min(23, normalized)) } : previous,
    )
  }

  const handleSave = async () => {
    if (!settings) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateIntelligentSuggestionSettings(settings)
      setSettings(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      toast.success("Intelligent suggestion settings updated")
    } catch (saveError) {
      console.error("Failed to save intelligent suggestion settings:", saveError)
      setError("Unable to save settings. Please try again.")
      toast.error("Failed to save intelligent suggestion settings")
    } finally {
      setSaving(false)
    }
  }

  const handleNewRuleTemplateChange = (templateKey: string | null) => {
    if (!templateKey) return
    const template = templateByKey.get(templateKey)
    if (!template) return
    setNewRuleDraft((previous) =>
      buildRuleDraft(template, previous?.sort_order ?? (rules.at(-1)?.sort_order ?? 0) + 1, {
        enabled: previous?.enabled ?? true,
      }),
    )
  }

  const handleCreateRule = async () => {
    if (!newRuleDraft) return
    const template = templateByKey.get(newRuleDraft.template_key)
    if (!template) {
      toast.error("Select a valid rule template")
      return
    }
    const stageSlug = requiresStageSelection(template)
      ? resolveStageSlug(template, newRuleDraft.stage_slug)
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
        name: newRuleDraft.name.trim() || template.name,
        stage_key: selectedStage?.stageKey ?? stageSlug,
        stage_slug: selectedStage?.slug ?? stageSlug,
        business_days: Math.max(1, Math.min(60, newRuleDraft.business_days)),
        enabled: newRuleDraft.enabled,
      })
      setRules((previous) =>
        [...previous, createdRule].sort((left, right) => left.sort_order - right.sort_order),
      )
      const resetDraft = buildRuleDraft(template, createdRule.sort_order + 1, { enabled: true })
      if (resetDraft) setNewRuleDraft(resetDraft)
      toast.success("Workflow rule created")
    } catch (ruleError) {
      console.error("Failed to create intelligent suggestion rule:", ruleError)
      toast.error("Failed to create workflow rule")
    } finally {
      setRuleSaving(false)
    }
  }

  const handleToggleRuleEnabled = async (rule: IntelligentSuggestionRule) => {
    setRuleSaving(true)
    try {
      const updatedRule = await updateIntelligentSuggestionRule(rule.id, { enabled: !rule.enabled })
      setRules((previous) =>
        previous.map((current) => (current.id === rule.id ? updatedRule : current)),
      )
      if (editingRuleId === rule.id && editingRuleDraft) {
        setEditingRuleDraft({ ...editingRuleDraft, enabled: updatedRule.enabled })
      }
      toast.success(`Rule ${updatedRule.enabled ? "enabled" : "disabled"}`)
    } catch (ruleError) {
      console.error("Failed to toggle intelligent suggestion rule:", ruleError)
      toast.error("Failed to update rule status")
    } finally {
      setRuleSaving(false)
    }
  }

  const startEditingRule = (rule: IntelligentSuggestionRule) => {
    const template = templateByKey.get(rule.template_key)
    const nextDraft = buildRuleDraft(template, rule.sort_order, {
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
    if (!editingRuleId || !editingRuleDraft) return
    const template = templateByKey.get(editingRuleDraft.template_key)
    if (!template) {
      toast.error("Unknown template for rule")
      return
    }
    const stageSlug = requiresStageSelection(template)
      ? resolveStageSlug(template, editingRuleDraft.stage_slug)
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
      console.error("Failed to update intelligent suggestion rule:", ruleError)
      toast.error("Failed to update workflow rule")
    } finally {
      setRuleSaving(false)
    }
  }

  const handleDeleteRule = async (rule: IntelligentSuggestionRule) => {
    if (!confirm(`Delete rule "${rule.name}"?`)) return
    setRuleSaving(true)
    try {
      await deleteIntelligentSuggestionRule(rule.id)
      setRules((previous) => previous.filter((current) => current.id !== rule.id))
      if (editingRuleId === rule.id) cancelEditingRule()
      toast.success("Workflow rule deleted")
    } catch (ruleError) {
      console.error("Failed to delete intelligent suggestion rule:", ruleError)
      toast.error("Failed to delete workflow rule")
    } finally {
      setRuleSaving(false)
    }
  }

  const describeRule = (rule: IntelligentSuggestionRule) => {
    if (rule.rule_kind === "meeting_outcome_missing") {
      return `Passed scheduled meeting ${rule.business_days} business day${rule.business_days === 1 ? "" : "s"} but no outcome logged`
    }
    if (rule.template_key === "preapproval_stuck") {
      return `No updates in intake pre-approval stages for ${rule.business_days} business day${rule.business_days === 1 ? "" : "s"}`
    }
    return `${rule.stage_label ?? formatStageLabel(rule.stage_key ?? rule.stage_slug)} has no updates for ${rule.business_days} business day${rule.business_days === 1 ? "" : "s"}`
  }

  const getRuleStageLabel = (rule: IntelligentSuggestionRule) => {
    if (rule.rule_kind === "meeting_outcome_missing") {
      return "All Stages Applied"
    }
    if (rule.template_key === "preapproval_stuck") {
      return "Intake Pre-approval Stages"
    }
    return rule.stage_label ?? formatStageLabel(rule.stage_key ?? rule.stage_slug)
  }

  return {
    settings,
    templates,
    rules,
    newRuleDraft,
    editingRuleId,
    editingRuleDraft,
    loading,
    saving,
    ruleSaving,
    saved,
    error,
    stageOptions,
    stageLabelByRef,
    templateByKey,
    newRuleTemplate: newRuleDraft ? templateByKey.get(newRuleDraft.template_key) : undefined,
    newRuleNeedsStage: requiresStageSelection(newRuleDraft ? templateByKey.get(newRuleDraft.template_key) : undefined),
    rulesPaused: settings ? !settings.enabled : false,
    requiresStageSelection,
    setSettings,
    setNewRuleDraft,
    setEditingRuleDraft,
    setDigestField,
    handleSave,
    loadSettings,
    handleNewRuleTemplateChange,
    handleCreateRule,
    handleToggleRuleEnabled,
    startEditingRule,
    cancelEditingRule,
    handleSaveEditingRule,
    handleDeleteRule,
    describeRule,
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
      <div className="space-y-4">
        <p className="text-sm text-destructive">{controller.error ?? "Unable to load settings."}</p>
        <Button variant="outline" onClick={() => void controller.loadSettings()}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {controller.error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {controller.error}
        </div>
      )}

      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-border p-4">
          <div>
            <p className="font-medium">Enable Intelligent Suggestions</p>
            <p className="text-sm text-muted-foreground">
              Turn all intelligent suggestion workflows on or off for your organization.
            </p>
          </div>
          <Switch
            checked={controller.settings.enabled}
            onCheckedChange={(checked) =>
              controller.setSettings((previous) => (previous ? { ...previous, enabled: checked } : previous))
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
          stageOptions={controller.stageOptions}
          stageLabelByRef={controller.stageLabelByRef}
          onTemplateChange={controller.handleNewRuleTemplateChange}
          onAddRule={controller.handleCreateRule}
          onDraftChange={controller.setNewRuleDraft}
        />

        <div className="space-y-3">
          <div>
            <p className="font-medium">Configured Workflow Rules</p>
            <p className="text-sm text-muted-foreground">
              Edit thresholds, target stages, priority, and enabled status.
            </p>
          </div>

          {controller.rules.length === 0 && (
            <div className="rounded-lg border border-border p-4 text-sm text-muted-foreground">
              No intelligent suggestion rules configured.
            </div>
          )}

          {controller.rules.map((rule) => {
            const template = controller.templateByKey.get(rule.template_key)
            const isEditing = controller.editingRuleId === rule.id && controller.editingRuleDraft !== null
            const editingTemplate = isEditing && controller.editingRuleDraft
              ? controller.templateByKey.get(controller.editingRuleDraft.template_key)
              : undefined

            return (
              <WorkflowRuleCard
                key={rule.id}
                rule={rule}
                template={template}
                isEditing={isEditing}
                editingRuleDraft={controller.editingRuleDraft}
                editingNeedsStage={controller.requiresStageSelection(editingTemplate)}
                ruleDescription={controller.describeRule(rule)}
                ruleStageLabel={controller.getRuleStageLabel(rule)}
                ruleSaving={controller.ruleSaving}
                stageOptions={controller.stageOptions}
                stageLabelByRef={controller.stageLabelByRef}
                onToggleEnabled={controller.handleToggleRuleEnabled}
                onStartEdit={controller.startEditingRule}
                onDelete={controller.handleDeleteRule}
                onEditingDraftChange={controller.setEditingRuleDraft}
                onSaveEdit={controller.handleSaveEditingRule}
                onCancelEdit={controller.cancelEditingRule}
              />
            )
          })}
        </div>

        <DailyDigestSettingsCard
          settings={controller.settings}
          onSettingsChange={controller.setSettings}
          onDigestHourChange={controller.setDigestField}
        />
      </div>

      <Button onClick={() => void controller.handleSave()} disabled={controller.saving}>
        {controller.saving ? (
          <>
            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            Saving…
          </>
        ) : controller.saved ? (
          <>
            <CheckIcon className="mr-2 size-4" aria-hidden="true" />
            Saved!
          </>
        ) : (
          "Save Intelligent Suggestion Rules"
        )}
      </Button>
    </div>
  )
}

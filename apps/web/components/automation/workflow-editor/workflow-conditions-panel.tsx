"use client"

import { FilterIcon, PlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import { getConditionFieldLabel } from "@/lib/workflows/workflow-editor-state"
import { ConditionValueInput } from "@/components/automation/workflow-editor/shared"
import { InspectorPanel, InspectorSection } from "./inspector-section"
import { NodeIcon } from "./node-meta"

export function WorkflowConditionsPanel({ controller }: { controller: WorkflowEditorController }) {
    const { state, options, handlers } = controller
    const { conditions, conditionLogic } = state
    const { availableConditionFields, conditionOperators, getConditionOptions } = options
    const { addCondition, removeCondition, updateCondition, setConditionLogic } = handlers

    return (
        <InspectorPanel
            title="Conditions"
            icon={<NodeIcon icon={FilterIcon} tone="amber" size="sm" />}
            actions={
                <Button size="sm" variant="outline" onClick={addCondition}>
                    <PlusIcon aria-hidden="true" />
                    Add
                </Button>
            }
        >
            <InspectorSection title="Continue when">
                <ToggleGroup
                    value={[conditionLogic]}
                    onValueChange={(value) => {
                        const next = value[0]
                        if (next === "AND" || next === "OR") setConditionLogic(next)
                    }}
                    variant="outline"
                    size="sm"
                    aria-label="Condition logic"
                    className="w-full [&>*]:flex-1"
                >
                    <ToggleGroupItem value="AND" aria-label="All conditions match">
                        All match
                    </ToggleGroupItem>
                    <ToggleGroupItem value="OR" aria-label="Any condition matches">
                        Any match
                    </ToggleGroupItem>
                </ToggleGroup>
            </InspectorSection>

            <InspectorSection title="Conditions">
                {conditions.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Runs for every matching trigger.</p>
                ) : (
                    conditions.map((condition, index) => (
                        <div key={condition.clientId} className="space-y-2 rounded-lg border border-border p-3">
                            <div className="flex items-center justify-between">
                                <Label className="text-xs text-muted-foreground">Condition {index + 1}</Label>
                                <Button
                                    size="icon-sm"
                                    variant="ghost"
                                    aria-label="Remove condition"
                                    onClick={() => removeCondition(index)}
                                >
                                    <XIcon aria-hidden="true" />
                                </Button>
                            </div>
                            <Select value={condition.field} onValueChange={(value) => value && updateCondition(index, { field: value })}>
                                <SelectTrigger aria-label={`Condition ${index + 1} field`} className="w-full">
                                    <SelectValue placeholder="Field">
                                        {(value: string | null) => (value ? getConditionFieldLabel(value) : "Field")}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {availableConditionFields.map((field) => (
                                        <SelectItem key={field} value={field}>
                                            {getConditionFieldLabel(field)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Select
                                value={condition.operator}
                                onValueChange={(value) => value && updateCondition(index, { operator: value })}
                            >
                                <SelectTrigger aria-label={`Condition ${index + 1} operator`} className="w-full">
                                    <SelectValue placeholder="Operator">
                                        {(value: string | null) => {
                                            if (!value) return "Operator"
                                            const operator = conditionOperators.find((option) => option.value === value)
                                            return operator?.label ?? "Unknown operator"
                                        }}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {conditionOperators.map((operator) => (
                                        <SelectItem key={operator.value} value={operator.value}>
                                            {operator.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <div className="flex min-w-0">
                                <ConditionValueInput
                                    condition={condition}
                                    options={getConditionOptions(condition.field)}
                                    onChange={(value) => updateCondition(index, { value })}
                                />
                            </div>
                        </div>
                    ))
                )}
            </InspectorSection>
        </InspectorPanel>
    )
}

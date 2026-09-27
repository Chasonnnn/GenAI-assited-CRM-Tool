/**
 * One label helper per select, shared by the trigger, the items, chips, badges and summaries,
 * so a stored id, enum, slug or sentinel never reaches the UI as a raw value.
 */

export type SelectOption = { readonly value: string; readonly label: string }

export type SelectLabelSource = Readonly<Record<string, string>> | ReadonlyArray<SelectOption>

export type SelectLabelOptions = {
    /** Label for null, "" and `allValue`: the default state ("All Stages", "Select outcome"). */
    emptyLabel: string
    /** Sentinel item value that also reads as `emptyLabel`, usually "all". */
    allValue?: string | undefined
    /** Label for a value missing from the source. Never the raw key. */
    unknownLabel?: string | undefined
}

const DEFAULT_UNKNOWN_LABEL = "Unknown selection"

function lookupLabel(source: SelectLabelSource, value: string): string | undefined {
    if (Array.isArray(source)) {
        return (source as ReadonlyArray<SelectOption>).find((option) => option.value === value)?.label
    }
    const labels = source as Readonly<Record<string, string>>
    return Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : undefined
}

export function getSelectLabel(
    value: string | null | undefined,
    source: SelectLabelSource,
    { emptyLabel, allValue, unknownLabel = DEFAULT_UNKNOWN_LABEL }: SelectLabelOptions,
): string {
    if (value == null || value === "" || (allValue !== undefined && value === allValue)) {
        return emptyLabel
    }
    return lookupLabel(source, value) ?? unknownLabel
}

/**
 * Builds the label helper for one select. Pass it as SelectValue children and reuse it for chips:
 * `<SelectValue placeholder="All Stages">{getStageLabel}</SelectValue>`.
 */
export function createSelectLabelGetter(
    source: SelectLabelSource,
    options: SelectLabelOptions,
): (value: string | null | undefined) => string {
    return (value) => getSelectLabel(value, source, options)
}

/** Items in label-map order, so SelectItem children and the trigger read from one map. */
export function toSelectOptions(labels: Readonly<Record<string, string>>): SelectOption[] {
    return Object.entries(labels).map(([value, label]) => ({ value, label }))
}

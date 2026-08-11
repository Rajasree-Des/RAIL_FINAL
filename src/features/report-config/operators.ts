import type { ColumnDataType } from "./types";

export interface FilterOperatorOption {
  value: string;
  label: string;
  requiresValue?: boolean;
  requiresSecondValue?: boolean;
}

export const OPERATORS_BY_TYPE: Record<ColumnDataType, FilterOperatorOption[]> = {
  text: [
    { value: "equals", label: "Equals" },
    { value: "contains", label: "Contains" },
    { value: "starts_with", label: "Starts With" },
    { value: "ends_with", label: "Ends With" },
  ],
  number: [
    { value: "eq", label: "=" },
    { value: "gt", label: ">" },
    { value: "lt", label: "<" },
    { value: "gte", label: ">=" },
    { value: "lte", label: "<=" },
    { value: "between", label: "Between", requiresSecondValue: true },
  ],
  date: [
    { value: "on", label: "On" },
    { value: "before", label: "Before" },
    { value: "after", label: "After" },
    { value: "between", label: "Between", requiresSecondValue: true },
  ],
  status: [
    { value: "equals", label: "Equals" },
    { value: "not_equals", label: "Not Equals" },
  ],
  boolean: [
    { value: "true", label: "True", requiresValue: false },
    { value: "false", label: "False", requiresValue: false },
  ],
};

export function getOperatorsForType(dataType: ColumnDataType): FilterOperatorOption[] {
  return OPERATORS_BY_TYPE[dataType] ?? OPERATORS_BY_TYPE.text;
}

export function getDefaultOperator(dataType: ColumnDataType): string {
  return getOperatorsForType(dataType)[0]?.value ?? "equals";
}

export function operatorRequiresValue(
  dataType: ColumnDataType,
  operator: string,
): { requiresValue: boolean; requiresSecondValue: boolean } {
  const option = getOperatorsForType(dataType).find((item) => item.value === operator);
  return {
    requiresValue: option?.requiresValue !== false,
    requiresSecondValue: option?.requiresSecondValue === true,
  };
}

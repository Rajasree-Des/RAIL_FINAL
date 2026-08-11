import type { FilteringRule } from "@/api/templates";
import type { ColumnMetadata, FilterCondition } from "./types";
import { getDefaultOperator } from "./operators";

function mapDataTypeToValueType(
  dataType: ColumnMetadata["dataType"],
): FilteringRule["value_type"] {
  if (dataType === "number") return "number";
  if (dataType === "date") return "date";
  if (dataType === "boolean") return "boolean";
  return "string";
}

function mapOperatorToTemplate(operator: string): FilteringRule["operator"] {
  const mapping: Record<string, FilteringRule["operator"]> = {
    equals: "equals",
    not_equals: "not_equals",
    contains: "contains",
    starts_with: "contains",
    ends_with: "contains",
    eq: "equals",
    gt: "gt",
    lt: "lt",
    gte: "gte",
    lte: "lte",
    on: "equals",
    before: "lt",
    after: "gt",
    between: "gte",
    true: "equals",
    false: "equals",
  };
  return mapping[operator] ?? "equals";
}

export function filteringRulesToConditions(
  rules: FilteringRule[],
  columns: ColumnMetadata[],
): FilterCondition[] {
  return rules.map((rule) => {
    const column =
      columns.find((item) => item.fieldName === rule.column_name) ??
      columns.find((item) => item.displayName === rule.column_name);

    const storedValue = rule.value ?? "";
    const inferredOperator =
      storedValue === "true"
        ? "true"
        : storedValue === "false"
          ? "false"
          : rule.operator;

    return {
      id: rule.id ?? crypto.randomUUID(),
      columnId: column?.id ?? rule.column_name,
      operator: inferredOperator,
      value: storedValue,
      valueTo: "",
      logic: rule.logic_group,
    };
  });
}

export function conditionsToFilteringRules(
  conditions: FilterCondition[],
  columns: ColumnMetadata[],
): FilteringRule[] {
  return conditions.map((condition) => {
    const column = columns.find((item) => item.id === condition.columnId);

    return {
      id: condition.id,
      column_name: column?.fieldName ?? condition.columnId,
      operator: mapOperatorToTemplate(condition.operator),
      value:
        condition.operator === "true"
          ? "true"
          : condition.operator === "false"
            ? "false"
            : condition.value || null,
      value_type: column ? mapDataTypeToValueType(column.dataType) : "string",
      logic_group: condition.logic,
    };
  });
}

export function createDefaultCondition(columns: ColumnMetadata[]): FilterCondition {
  const firstColumn = columns[0];
  return {
    id: crypto.randomUUID(),
    columnId: firstColumn?.id ?? "",
    operator: firstColumn ? getDefaultOperator(firstColumn.dataType) : "equals",
    value: "",
    valueTo: "",
    logic: "AND",
  };
}

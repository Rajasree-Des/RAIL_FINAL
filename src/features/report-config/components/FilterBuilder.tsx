import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import type { ColumnMetadata, FilterCondition } from "../types";
import { getDefaultOperator, getOperatorsForType } from "../operators";
import { SearchableColumnSelect } from "./SearchableColumnSelect";
import { FilterValueInput } from "./FilterValueInput";

interface FilterBuilderProps {
  columns: ColumnMetadata[];
  conditions: FilterCondition[];
  onChange: (conditions: FilterCondition[]) => void;
  loading?: boolean;
  error?: string | null;
  disabled?: boolean;
  title?: string;
  description?: string;
}

function createCondition(columns: ColumnMetadata[]): FilterCondition {
  const firstColumn = columns[0];
  const operator = firstColumn ? getDefaultOperator(firstColumn.dataType) : "equals";

  return {
    id: crypto.randomUUID(),
    columnId: firstColumn?.id ?? "",
    operator,
    value: "",
    valueTo: "",
    logic: "AND",
  };
}

export function FilterBuilder({
  columns,
  conditions,
  onChange,
  loading = false,
  error = null,
  disabled = false,
  title = "Filters",
  description = "Filter rows from the original RailMadad dataset before generating the report",
}: FilterBuilderProps) {
  const filterableColumns = columns.filter((column) => column.filterable);

  const updateCondition = (id: string, updates: Partial<FilterCondition>) => {
    onChange(
      conditions.map((condition) =>
        condition.id === id ? { ...condition, ...updates } : condition,
      ),
    );
  };

  const handleColumnChange = (id: string, columnId: string) => {
    const column = filterableColumns.find((item) => item.id === columnId);
    if (!column) return;

    updateCondition(id, {
      columnId,
      operator: getDefaultOperator(column.dataType),
      value: "",
      valueTo: "",
    });
  };

  const removeCondition = (id: string) => {
    onChange(conditions.filter((condition) => condition.id !== id));
  };

  const addCondition = () => {
    onChange([...conditions, createCondition(filterableColumns)]);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return <Alert variant="error">{error}</Alert>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <p className="mt-0.5 text-xs text-slate-500">{description}</p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={addCondition}
          disabled={disabled || filterableColumns.length === 0}
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Filter
        </Button>
      </div>

      {filterableColumns.length === 0 ? (
        <EmptyState
          title="No dataset columns available"
          description="Import the original RailMadad Excel file to populate filter columns."
        />
      ) : conditions.length === 0 ? (
        <EmptyState
          title="No filters configured"
          description="Add filters to narrow the original dataset before report generation."
          action={
            <Button variant="primary" size="sm" onClick={addCondition}>
              <Plus className="mr-2 h-4 w-4" />
              Add Filter
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {conditions.map((condition, index) => {
            const column = filterableColumns.find((item) => item.id === condition.columnId);
            const operators = column ? getOperatorsForType(column.dataType) : [];

            return (
              <div
                key={condition.id}
                className="rounded-xl border border-rail-line bg-surface/40 p-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
                  {index > 0 && (
                    <Select
                      value={condition.logic}
                      onChange={(event) =>
                        updateCondition(condition.id, {
                          logic: event.target.value as FilterCondition["logic"],
                        })
                      }
                      className="w-full lg:w-24"
                      disabled={disabled}
                    >
                      <option value="AND">AND</option>
                      <option value="OR">OR</option>
                    </Select>
                  )}

                  <div className="grid flex-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-500">Column</label>
                      <SearchableColumnSelect
                        columns={filterableColumns}
                        value={condition.columnId}
                        onChange={(columnId) => handleColumnChange(condition.id, columnId)}
                        disabled={disabled}
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-500">Operator</label>
                      <Select
                        value={condition.operator}
                        onChange={(event) =>
                          updateCondition(condition.id, {
                            operator: event.target.value,
                            value: "",
                            valueTo: "",
                          })
                        }
                        disabled={disabled || !column}
                      >
                        {operators.map((operator) => (
                          <option key={operator.value} value={operator.value}>
                            {operator.label}
                          </option>
                        ))}
                      </Select>
                    </div>

                    {column && (
                      <div className="space-y-1 md:col-span-2">
                        <label className="text-xs font-medium text-slate-500">Value</label>
                        <FilterValueInput
                          dataType={column.dataType}
                          operator={condition.operator}
                          value={condition.value}
                          valueTo={condition.valueTo}
                          onChange={(value) => updateCondition(condition.id, { value })}
                          onChangeTo={(valueTo) => updateCondition(condition.id, { valueTo })}
                          disabled={disabled}
                        />
                      </div>
                    )}
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeCondition(condition.id)}
                    disabled={disabled}
                    className="self-start text-red-600 hover:bg-red-50"
                    aria-label="Remove filter"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

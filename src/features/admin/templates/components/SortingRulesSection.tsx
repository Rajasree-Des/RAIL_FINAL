import { Plus, Trash2 } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

interface SortingRule {
  column_name: string;
  direction: "asc" | "desc";
  priority: number;
}

interface SortingRulesSectionProps {
  data: SortingRule[];
  columns: string[];
  onChange: (data: SortingRule[]) => void;
}

export function SortingRulesSection({ data, columns, onChange }: SortingRulesSectionProps) {
  const addRule = () => {
    onChange([
      ...data,
      { column_name: columns[0] || "", direction: "asc", priority: data.length + 1 },
    ]);
  };

  const updateRule = (index: number, updates: Partial<SortingRule>) => {
    onChange(data.map((r, i) => (i === index ? { ...r, ...updates } : r)));
  };

  const removeRule = (index: number) => {
    onChange(
      data
        .filter((_, i) => i !== index)
        .map((r, i) => ({ ...r, priority: i + 1 })),
    );
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Sorting Rules</CardTitle>
            <CardDescription>Define how output data should be sorted</CardDescription>
          </div>
          <Button variant="secondary" onClick={addRule} disabled={columns.length === 0}>
            <Plus className="mr-2 h-4 w-4" />
            Add Rule
          </Button>
        </div>
      </CardHeader>
      <CardBody>
        {columns.length === 0 ? (
          <EmptyState
            title="No columns available"
            description="Add column mappings first to configure sorting rules."
          />
        ) : data.length === 0 ? (
          <EmptyState
            title="No sorting rules"
            description="Add sorting rules to order output data."
            action={
              <Button variant="primary" onClick={addRule}>
                <Plus className="mr-2 h-4 w-4" />
                Add Rule
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {data.map((rule, index) => (
              <div
                key={index}
                className="flex items-center gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
                  {rule.priority}
                </div>

                <div className="flex-1 grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-500">Column</label>
                    <Select
                      value={rule.column_name}
                      onChange={(e) => updateRule(index, { column_name: e.target.value })}
                    >
                      {columns.map((col) => (
                        <option key={col} value={col}>
                          {col}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-500">Direction</label>
                    <Select
                      value={rule.direction}
                      onChange={(e) =>
                        updateRule(index, { direction: e.target.value as "asc" | "desc" })
                      }
                    >
                      <option value="asc">Ascending (A-Z, 0-9)</option>
                      <option value="desc">Descending (Z-A, 9-0)</option>
                    </Select>
                  </div>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeRule(index)}
                  className="text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

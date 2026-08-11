import { Plus, Trash2 } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

interface HighlightRule {
  column_name: string;
  condition_type: "equals" | "gt" | "lt" | "gte" | "lte" | "contains" | "between";
  condition_value: string | null;
  highlight_color: string;
  text_color: string | null;
  is_bold: boolean;
  priority: number;
}

interface HighlightRulesSectionProps {
  data: HighlightRule[];
  columns: string[];
  onChange: (data: HighlightRule[]) => void;
}

const conditionTypes = [
  { value: "equals", label: "Equals" },
  { value: "gt", label: "Greater Than" },
  { value: "lt", label: "Less Than" },
  { value: "gte", label: "Greater or Equal" },
  { value: "lte", label: "Less or Equal" },
  { value: "contains", label: "Contains" },
  { value: "between", label: "Between" },
];

export function HighlightRulesSection({ data, columns, onChange }: HighlightRulesSectionProps) {
  const addRule = () => {
    onChange([
      ...data,
      {
        column_name: columns[0] || "",
        condition_type: "gt",
        condition_value: "",
        highlight_color: "#FFFF00",
        text_color: null,
        is_bold: false,
        priority: data.length + 1,
      },
    ]);
  };

  const updateRule = (index: number, updates: Partial<HighlightRule>) => {
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
            <CardTitle>Highlight Rules</CardTitle>
            <CardDescription>Define conditional formatting for output cells</CardDescription>
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
            description="Add column mappings first to configure highlight rules."
          />
        ) : data.length === 0 ? (
          <EmptyState
            title="No highlight rules"
            description="Add highlight rules for conditional cell formatting."
            action={
              <Button variant="primary" onClick={addRule}>
                <Plus className="mr-2 h-4 w-4" />
                Add Rule
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
            {data.map((rule, index) => (
              <div
                key={index}
                className="rounded-lg border border-slate-200 bg-slate-50 p-4"
              >
                <div className="flex items-start gap-4">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
                    {rule.priority}
                  </div>

                  <div className="flex-1 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
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
                      <label className="text-xs font-medium text-slate-500">Condition</label>
                      <Select
                        value={rule.condition_type}
                        onChange={(e) =>
                          updateRule(index, {
                            condition_type: e.target.value as HighlightRule["condition_type"],
                          })
                        }
                      >
                        {conditionTypes.map((ct) => (
                          <option key={ct.value} value={ct.value}>
                            {ct.label}
                          </option>
                        ))}
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-500">Value</label>
                      <Input
                        value={rule.condition_value || ""}
                        onChange={(e) => updateRule(index, { condition_value: e.target.value })}
                        placeholder={rule.condition_type === "between" ? "min,max" : "value"}
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-500">Background</label>
                      <div className="flex gap-2">
                        <input
                          type="color"
                          value={rule.highlight_color}
                          onChange={(e) => updateRule(index, { highlight_color: e.target.value })}
                          className="h-10 w-12 cursor-pointer rounded border border-slate-300"
                        />
                        <Input
                          value={rule.highlight_color}
                          onChange={(e) => updateRule(index, { highlight_color: e.target.value })}
                          className="flex-1"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-500">Text Color</label>
                      <div className="flex gap-2">
                        <input
                          type="color"
                          value={rule.text_color || "#000000"}
                          onChange={(e) => updateRule(index, { text_color: e.target.value })}
                          className="h-10 w-12 cursor-pointer rounded border border-slate-300"
                        />
                        <Input
                          value={rule.text_color || ""}
                          onChange={(e) => updateRule(index, { text_color: e.target.value || null })}
                          placeholder="Auto"
                          className="flex-1"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-500">Bold</label>
                      <div className="flex h-10 items-center">
                        <input
                          type="checkbox"
                          checked={rule.is_bold}
                          onChange={(e) => updateRule(index, { is_bold: e.target.checked })}
                          className="h-4 w-4 rounded border-slate-300"
                        />
                        <span className="ml-2 text-sm text-slate-600">Bold text</span>
                      </div>
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

                <div className="mt-3 ml-12">
                  <div
                    className="inline-block rounded px-3 py-1 text-sm"
                    style={{
                      backgroundColor: rule.highlight_color,
                      color: rule.text_color || "#000000",
                      fontWeight: rule.is_bold ? "bold" : "normal",
                    }}
                  >
                    Preview: Sample Text
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

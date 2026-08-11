import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";

interface RowRule {
  rule_type: "none" | "top_n" | "bottom_n" | "custom";
  limit_value: number | null;
  limit_column: string | null;
  custom_expression: string | null;
}

interface RowRulesSectionProps {
  data: RowRule;
  columns: string[];
  onChange: (data: RowRule) => void;
}

export function RowRulesSection({ data, columns, onChange }: RowRulesSectionProps) {
  const handleChange = <K extends keyof RowRule>(key: K, value: RowRule[K]) => {
    onChange({ ...data, [key]: value });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Row Rules</CardTitle>
        <CardDescription>Limit the number of rows in the output</CardDescription>
      </CardHeader>
      <CardBody>
        <div className="space-y-6">
          <div className="space-y-1.5 max-w-xs">
            <Label htmlFor="rule_type">Rule Type</Label>
            <Select
              id="rule_type"
              value={data.rule_type}
              onChange={(e) => handleChange("rule_type", e.target.value as RowRule["rule_type"])}
            >
              <option value="none">No Limit</option>
              <option value="top_n">Top N Rows</option>
              <option value="bottom_n">Bottom N Rows</option>
              <option value="custom">Custom Expression</option>
            </Select>
          </div>

          {(data.rule_type === "top_n" || data.rule_type === "bottom_n") && (
            <div className="grid gap-6 sm:grid-cols-2 max-w-lg">
              <div className="space-y-1.5">
                <Label htmlFor="limit_value">
                  {data.rule_type === "top_n" ? "Top" : "Bottom"} N Rows
                </Label>
                <Input
                  id="limit_value"
                  type="number"
                  min={1}
                  value={data.limit_value || ""}
                  onChange={(e) =>
                    handleChange("limit_value", e.target.value ? parseInt(e.target.value) : null)
                  }
                  placeholder="e.g., 25"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="limit_column">Order By Column</Label>
                <Select
                  id="limit_column"
                  value={data.limit_column || ""}
                  onChange={(e) => handleChange("limit_column", e.target.value || null)}
                >
                  <option value="">Select column...</option>
                  {columns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </Select>
                <p className="text-xs text-slate-500">
                  Column used to determine {data.rule_type === "top_n" ? "top" : "bottom"} rows
                </p>
              </div>
            </div>
          )}

          {data.rule_type === "custom" && (
            <div className="space-y-1.5 max-w-lg">
              <Label htmlFor="custom_expression">Custom Expression</Label>
              <Textarea
                id="custom_expression"
                value={data.custom_expression || ""}
                onChange={(e) => handleChange("custom_expression", e.target.value || null)}
                placeholder="Enter custom filter expression..."
                rows={4}
              />
              <p className="text-xs text-slate-500">
                Advanced: Enter a custom SQL-like expression for row filtering
              </p>
            </div>
          )}

          {data.rule_type === "none" && (
            <div className="rounded-lg bg-slate-100 p-4 text-sm text-slate-600">
              All rows from the input will be included in the output.
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

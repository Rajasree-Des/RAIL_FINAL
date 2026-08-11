import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Button } from "@/components/ui/Button";

interface InputConfig {
  accepted_file_types: string[];
  required_sheets: string[] | null;
  header_row: number;
  validation_rules: Record<string, unknown>;
}

interface InputConfigSectionProps {
  data: InputConfig;
  onChange: (data: InputConfig) => void;
}

export function InputConfigSection({ data, onChange }: InputConfigSectionProps) {
  const [newFileType, setNewFileType] = useState("");
  const [newSheet, setNewSheet] = useState("");

  const handleChange = <K extends keyof InputConfig>(key: K, value: InputConfig[K]) => {
    onChange({ ...data, [key]: value });
  };

  const addFileType = () => {
    if (newFileType && !data.accepted_file_types.includes(newFileType)) {
      handleChange("accepted_file_types", [...data.accepted_file_types, newFileType]);
      setNewFileType("");
    }
  };

  const removeFileType = (type: string) => {
    handleChange(
      "accepted_file_types",
      data.accepted_file_types.filter((t) => t !== type),
    );
  };

  const addSheet = () => {
    if (newSheet) {
      const sheets = data.required_sheets || [];
      if (!sheets.includes(newSheet)) {
        handleChange("required_sheets", [...sheets, newSheet]);
        setNewSheet("");
      }
    }
  };

  const removeSheet = (sheet: string) => {
    const sheets = data.required_sheets || [];
    const filtered = sheets.filter((s) => s !== sheet);
    handleChange("required_sheets", filtered.length > 0 ? filtered : null);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Configuration</CardTitle>
        <CardDescription>Define what files are accepted and how to parse them</CardDescription>
      </CardHeader>
      <CardBody>
        <div className="space-y-6">
          <div className="space-y-3">
            <Label>Accepted File Types</Label>
            <div className="flex flex-wrap gap-2">
              {data.accepted_file_types.map((type) => (
                <span
                  key={type}
                  className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-sm text-primary"
                >
                  {type}
                  <button
                    type="button"
                    onClick={() => removeFileType(type)}
                    className="ml-1 rounded-full hover:bg-primary/15"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={newFileType}
                onChange={(e) => setNewFileType(e.target.value)}
                placeholder=".xlsx, .csv, etc."
                className="max-w-[200px]"
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addFileType())}
              />
              <Button variant="secondary" size="sm" onClick={addFileType}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="space-y-3">
            <Label>Required Sheets (Optional)</Label>
            <p className="text-xs text-slate-500">Leave empty to accept any sheet name</p>
            <div className="flex flex-wrap gap-2">
              {(data.required_sheets || []).map((sheet) => (
                <span
                  key={sheet}
                  className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700"
                >
                  {sheet}
                  <button
                    type="button"
                    onClick={() => removeSheet(sheet)}
                    className="ml-1 rounded-full hover:bg-slate-200"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={newSheet}
                onChange={(e) => setNewSheet(e.target.value)}
                placeholder="Sheet1, Data, etc."
                className="max-w-[200px]"
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addSheet())}
              />
              <Button variant="secondary" size="sm" onClick={addSheet}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="space-y-1.5 max-w-[200px]">
            <Label htmlFor="header_row">Header Row</Label>
            <Input
              id="header_row"
              type="number"
              min={1}
              value={data.header_row}
              onChange={(e) => handleChange("header_row", parseInt(e.target.value) || 1)}
            />
            <p className="text-xs text-slate-500">Row number containing column headers (1-indexed)</p>
          </div>

          <div className="space-y-3">
            <Label>Validation Rules</Label>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="min_rows" className="text-xs">Minimum Rows</Label>
                <Input
                  id="min_rows"
                  type="number"
                  min={0}
                  value={(data.validation_rules.min_rows as number) || ""}
                  onChange={(e) =>
                    handleChange("validation_rules", {
                      ...data.validation_rules,
                      min_rows: e.target.value ? parseInt(e.target.value) : undefined,
                    })
                  }
                  placeholder="No minimum"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="max_rows" className="text-xs">Maximum Rows</Label>
                <Input
                  id="max_rows"
                  type="number"
                  min={0}
                  value={(data.validation_rules.max_rows as number) || ""}
                  onChange={(e) =>
                    handleChange("validation_rules", {
                      ...data.validation_rules,
                      max_rows: e.target.value ? parseInt(e.target.value) : undefined,
                    })
                  }
                  placeholder="No maximum"
                />
              </div>
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

import { Plus, Trash2, GripVertical } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";

interface ColumnMapping {
  source_column: string;
  internal_field: string;
  output_column: string;
  data_type: "text" | "number" | "date" | "boolean";
  is_required: boolean;
  default_value: string | null;
  transform: "none" | "uppercase" | "lowercase" | "trim";
  sort_order: number;
}

interface ColumnMappingSectionProps {
  data: ColumnMapping[];
  onChange: (data: ColumnMapping[]) => void;
}

const emptyMapping: ColumnMapping = {
  source_column: "",
  internal_field: "",
  output_column: "",
  data_type: "text",
  is_required: false,
  default_value: null,
  transform: "none",
  sort_order: 0,
};

export function ColumnMappingSection({ data, onChange }: ColumnMappingSectionProps) {
  const addMapping = () => {
    onChange([...data, { ...emptyMapping, sort_order: data.length }]);
  };

  const updateMapping = (index: number, updates: Partial<ColumnMapping>) => {
    onChange(data.map((m, i) => (i === index ? { ...m, ...updates } : m)));
  };

  const removeMapping = (index: number) => {
    onChange(data.filter((_, i) => i !== index));
  };

  const moveMapping = (index: number, direction: "up" | "down") => {
    if (
      (direction === "up" && index === 0) ||
      (direction === "down" && index === data.length - 1)
    ) {
      return;
    }

    const newData = [...data];
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    [newData[index], newData[targetIndex]] = [newData[targetIndex], newData[index]];
    onChange(newData.map((m, i) => ({ ...m, sort_order: i })));
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Column Mappings</CardTitle>
            <CardDescription>Map source columns to internal fields and output columns</CardDescription>
          </div>
          <Button variant="secondary" onClick={addMapping}>
            <Plus className="mr-2 h-4 w-4" />
            Add Column
          </Button>
        </div>
      </CardHeader>
      <CardBody>
        {data.length === 0 ? (
          <EmptyState
            title="No column mappings"
            description="Add at least one column mapping to define how data is processed."
            action={
              <Button variant="primary" onClick={addMapping}>
                <Plus className="mr-2 h-4 w-4" />
                Add Column
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-12 gap-2 px-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <div className="col-span-1"></div>
              <div className="col-span-2">Source Column</div>
              <div className="col-span-2">Internal Field</div>
              <div className="col-span-2">Output Column</div>
              <div className="col-span-1">Type</div>
              <div className="col-span-1">Required</div>
              <div className="col-span-1">Transform</div>
              <div className="col-span-1">Default</div>
              <div className="col-span-1"></div>
            </div>

            {data.map((mapping, index) => (
              <div
                key={index}
                className="grid grid-cols-12 gap-2 items-center rounded-lg border border-slate-200 bg-slate-50 p-2"
              >
                <div className="col-span-1 flex items-center justify-center">
                  <button
                    type="button"
                    className="cursor-grab text-slate-400 hover:text-slate-600"
                    onClick={() => moveMapping(index, "up")}
                  >
                    <GripVertical className="h-4 w-4" />
                  </button>
                </div>

                <div className="col-span-2">
                  <Input
                    value={mapping.source_column}
                    onChange={(e) => updateMapping(index, { source_column: e.target.value })}
                    placeholder="Excel column"
                    className="text-sm"
                  />
                </div>

                <div className="col-span-2">
                  <Input
                    value={mapping.internal_field}
                    onChange={(e) =>
                      updateMapping(index, {
                        internal_field: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"),
                      })
                    }
                    placeholder="internal_field"
                    className="text-sm"
                  />
                </div>

                <div className="col-span-2">
                  <Input
                    value={mapping.output_column}
                    onChange={(e) => updateMapping(index, { output_column: e.target.value })}
                    placeholder="Output header"
                    className="text-sm"
                  />
                </div>

                <div className="col-span-1">
                  <Select
                    value={mapping.data_type}
                    onChange={(e) =>
                      updateMapping(index, { data_type: e.target.value as ColumnMapping["data_type"] })
                    }
                    className="text-sm"
                  >
                    <option value="text">Text</option>
                    <option value="number">Number</option>
                    <option value="date">Date</option>
                    <option value="boolean">Boolean</option>
                  </Select>
                </div>

                <div className="col-span-1 flex justify-center">
                  <input
                    type="checkbox"
                    checked={mapping.is_required}
                    onChange={(e) => updateMapping(index, { is_required: e.target.checked })}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                </div>

                <div className="col-span-1">
                  <Select
                    value={mapping.transform}
                    onChange={(e) =>
                      updateMapping(index, { transform: e.target.value as ColumnMapping["transform"] })
                    }
                    className="text-sm"
                  >
                    <option value="none">None</option>
                    <option value="uppercase">Upper</option>
                    <option value="lowercase">Lower</option>
                    <option value="trim">Trim</option>
                  </Select>
                </div>

                <div className="col-span-1">
                  <Input
                    value={mapping.default_value || ""}
                    onChange={(e) =>
                      updateMapping(index, { default_value: e.target.value || null })
                    }
                    placeholder="Default"
                    className="text-sm"
                  />
                </div>

                <div className="col-span-1 flex justify-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeMapping(index)}
                    className="text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import type { ColumnDataType } from "../types";
import { operatorRequiresValue } from "../operators";

interface FilterValueInputProps {
  dataType: ColumnDataType;
  operator: string;
  value: string;
  valueTo?: string;
  onChange: (value: string) => void;
  onChangeTo?: (value: string) => void;
  disabled?: boolean;
}

export function FilterValueInput({
  dataType,
  operator,
  value,
  valueTo = "",
  onChange,
  onChangeTo,
  disabled = false,
}: FilterValueInputProps) {
  const { requiresValue, requiresSecondValue } = operatorRequiresValue(dataType, operator);

  if (!requiresValue) {
    return null;
  }

  const inputType =
    dataType === "number" ? "number" : dataType === "date" ? "date" : "text";

  if (requiresSecondValue) {
    return (
      <div className="grid gap-2 sm:grid-cols-2">
        <Input
          type={inputType}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={dataType === "date" ? "Start date" : "From"}
          disabled={disabled}
        />
        <Input
          type={inputType}
          value={valueTo}
          onChange={(event) => onChangeTo?.(event.target.value)}
          placeholder={dataType === "date" ? "End date" : "To"}
          disabled={disabled}
        />
      </div>
    );
  }

  if (dataType === "status") {
    return (
      <Select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
        <option value="">Select status</option>
        <option value="Open">Open</option>
        <option value="Closed">Closed</option>
        <option value="Pending">Pending</option>
        <option value="In Progress">In Progress</option>
        <option value="Escalated">Escalated</option>
      </Select>
    );
  }

  return (
    <Input
      type={inputType}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder="Enter value"
      disabled={disabled}
    />
  );
}

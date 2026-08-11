import type { SettingItem } from "@/api/settings";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";

type SettingFieldProps = {
  setting: SettingItem;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled?: boolean;
};

export function SettingField({ setting, value, onChange, disabled: disabledProp }: SettingFieldProps) {
  const disabled = disabledProp || !setting.is_editable;
  const id = `${setting.category}-${setting.key}`;

  if (setting.value_type === "boolean") {
    return (
      <Checkbox
        id={id}
        label={setting.label}
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
    );
  }

  if (setting.value_type === "enum" && setting.options) {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>{setting.label}</Label>
        {setting.description && (
          <p className="text-xs text-slate-500">{setting.description}</p>
        )}
        <Select
          id={id}
          value={String(value ?? "")}
          onChange={(e) => {
            const opt = setting.options?.find(
              (o) => String(o.value) === e.target.value,
            );
            onChange(opt?.value ?? e.target.value);
          }}
          disabled={disabled}
        >
          {setting.options.map((opt) => (
            <option key={String(opt.value)} value={String(opt.value)}>
              {opt.label}
            </option>
          ))}
        </Select>
      </div>
    );
  }

  if (setting.value_type === "multiselect" && setting.options) {
    const selected = Array.isArray(value) ? (value as unknown[]) : [];
    return (
      <div className="space-y-2">
        <Label>{setting.label}</Label>
        {setting.description && (
          <p className="text-xs text-slate-500">{setting.description}</p>
        )}
        <div className="flex flex-wrap gap-3">
          {setting.options.map((opt) => {
            const checked = selected.includes(opt.value);
            return (
              <Checkbox
                key={String(opt.value)}
                label={opt.label}
                checked={checked}
                onChange={(e) => {
                  if (e.target.checked) {
                    onChange([...selected, opt.value]);
                  } else {
                    onChange(selected.filter((v) => v !== opt.value));
                  }
                }}
                disabled={disabled}
              />
            );
          })}
        </div>
      </div>
    );
  }

  if (setting.value_type === "number") {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>{setting.label}</Label>
        {setting.description && (
          <p className="text-xs text-slate-500">{setting.description}</p>
        )}
        <Input
          id={id}
          type="number"
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          min={setting.validation?.min as number | undefined}
          max={setting.validation?.max as number | undefined}
        />
      </div>
    );
  }

  if (setting.value_type === "json") {
    const text =
      typeof value === "string" ? value : JSON.stringify(value, null, 2);
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>{setting.label}</Label>
        {setting.description && (
          <p className="text-xs text-slate-500">{setting.description}</p>
        )}
        <Textarea
          id={id}
          rows={5}
          className="font-mono text-xs"
          value={text}
          onChange={(e) => {
            try {
              onChange(JSON.parse(e.target.value));
            } catch {
              onChange(e.target.value);
            }
          }}
          disabled={disabled}
        />
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{setting.label}</Label>
      {setting.description && (
        <p className="text-xs text-slate-500">{setting.description}</p>
      )}
      <Input
        id={id}
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
    </div>
  );
}

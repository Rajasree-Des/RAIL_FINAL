import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { ModuleSetting } from "@/types/workflow";

type SettingsRendererProps = {
  settings: ModuleSetting[];
  values: Record<string, unknown>;
  onChange: (id: string, value: unknown) => void;
};

export function SettingsRenderer({ settings, values, onChange }: SettingsRendererProps) {
  return (
    <div
      className="grid gap-5 sm:grid-cols-2"
      role="group"
      aria-label="Workflow settings"
    >
      {settings.map((setting) => (
        <div key={setting.id} className="space-y-2">
          <Label htmlFor={setting.id} required={setting.required}>
            {setting.label}
          </Label>
          <SettingControl
            setting={setting}
            value={values[setting.id]}
            onChange={(value) => onChange(setting.id, value)}
          />
          {setting.helpText ? (
            <p id={`${setting.id}-help`} className="text-xs text-slate-500">
              {setting.helpText}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

type SettingControlProps = {
  setting: ModuleSetting;
  value: unknown;
  onChange: (value: unknown) => void;
};

function SettingControl({ setting, value, onChange }: SettingControlProps) {
  const describedBy = setting.helpText ? `${setting.id}-help` : undefined;

  if (setting.type === "dropdown" || setting.type === "searchDropdown") {
    return (
      <Select
        id={setting.id}
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
        aria-describedby={describedBy}
        aria-required={setting.required}
      >
        <option value="">{setting.placeholder ?? "Select an option"}</option>
        {setting.options?.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    );
  }

  if (setting.type === "date") {
    return (
      <Input
        id={setting.id}
        type="date"
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
        aria-describedby={describedBy}
        aria-required={setting.required}
      />
    );
  }

  if (setting.type === "dateRange") {
    const range = Array.isArray(value) ? value : ["", ""];
    return (
      <div className="grid grid-cols-2 gap-3">
        <Input
          type="date"
          value={String(range[0] ?? "")}
          onChange={(e) => onChange([e.target.value, range[1]])}
          aria-label="Start date"
        />
        <Input
          type="date"
          value={String(range[1] ?? "")}
          onChange={(e) => onChange([range[0], e.target.value])}
          aria-label="End date"
        />
      </div>
    );
  }

  if (setting.type === "checkbox" || setting.type === "toggle") {
    return (
      <div className="flex h-10 items-center">
        <label className="flex items-center gap-3 text-sm">
          <input
            id={setting.id}
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
            aria-describedby={describedBy}
          />
          <span className="text-slate-700">Enable</span>
        </label>
      </div>
    );
  }

  if (setting.type === "radio") {
    return (
      <div
        className="flex flex-wrap gap-2"
        role="radiogroup"
        aria-label={setting.label}
      >
        {setting.options?.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            onClick={() => onChange(option.value)}
            className={`h-10 rounded-md border px-4 text-sm font-medium ${
              value === option.value
                ? "border-primary bg-primary text-white"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    );
  }

  if (setting.type === "multiSelect") {
    const selected = Array.isArray(value) ? value.map(String) : [];
    return (
      <div className="flex flex-wrap gap-2" role="group" aria-label={setting.label}>
        {setting.options?.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
              onClick={() =>
                onChange(
                  isSelected
                    ? selected.filter((item) => item !== option.value)
                    : [...selected, option.value],
                )
              }
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                isSelected
                  ? "bg-primary text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    );
  }

  if (setting.type === "textarea") {
    return (
      <Textarea
        id={setting.id}
        placeholder={setting.placeholder}
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
        aria-describedby={describedBy}
        aria-required={setting.required}
      />
    );
  }

  return (
    <Input
      id={setting.id}
      type={setting.type === "number" ? "number" : "text"}
      placeholder={setting.placeholder}
      value={String(value ?? "")}
      onChange={(e) =>
        onChange(setting.type === "number" ? Number(e.target.value) : e.target.value)
      }
      aria-describedby={describedBy}
      aria-required={setting.required}
    />
  );
}

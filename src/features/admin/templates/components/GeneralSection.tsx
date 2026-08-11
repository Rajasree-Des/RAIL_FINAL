import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";

interface GeneralData {
  name: string;
  slug: string;
  description: string;
  source_report_id: string;
  is_enabled: boolean;
}

interface GeneralSectionProps {
  data: GeneralData;
  onChange: (data: GeneralData) => void;
}

export function GeneralSection({ data, onChange }: GeneralSectionProps) {
  const handleChange = <K extends keyof GeneralData>(key: K, value: GeneralData[K]) => {
    onChange({ ...data, [key]: value });
  };

  const generateSlug = (name: string) => {
    return name
      .toLowerCase()
      .replace(/[^\w\s-]/g, "")
      .replace(/[\s_]+/g, "-")
      .replace(/-+/g, "-")
      .trim()
      .substring(0, 64);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>General Settings</CardTitle>
        <CardDescription>Basic template information and identification</CardDescription>
      </CardHeader>
      <CardBody>
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="name">Template Name *</Label>
            <Input
              id="name"
              value={data.name}
              onChange={(e) => {
                handleChange("name", e.target.value);
                if (!data.slug) {
                  handleChange("slug", generateSlug(e.target.value));
                }
              }}
              placeholder="e.g., Division Top 25"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="slug">URL Slug *</Label>
            <Input
              id="slug"
              value={data.slug}
              onChange={(e) => handleChange("slug", e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
              placeholder="e.g., division-top-25"
            />
            <p className="text-xs text-slate-500">Used in URLs. Auto-generated from name.</p>
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={data.description}
              onChange={(e) => handleChange("description", e.target.value)}
              placeholder="Describe what this template does..."
              rows={3}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="source_report_id">Source Report ID</Label>
            <Input
              id="source_report_id"
              value={data.source_report_id}
              onChange={(e) => handleChange("source_report_id", e.target.value)}
              placeholder="e.g., division-report"
            />
            <p className="text-xs text-slate-500">Links to a workflow for data source</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="is_enabled">Status</Label>
            <Select
              id="is_enabled"
              value={data.is_enabled ? "enabled" : "disabled"}
              onChange={(e) => handleChange("is_enabled", e.target.value === "enabled")}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </Select>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

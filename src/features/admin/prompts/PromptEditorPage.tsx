import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Save, Play } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import {
  summaryApi,
  SUMMARY_TYPE_LABELS,
  type SummaryType,
} from "@/api/summary";
import { PromptTestPanel } from "./components/PromptTestPanel";
import { VariableReference } from "./components/VariableReference";

interface FormData {
  name: string;
  slug: string;
  summary_type: SummaryType;
  description: string;
  system_prompt: string;
  user_prompt_template: string;
  output_format: "markdown" | "plain_text" | "bullets";
  max_tokens: number;
  temperature: number;
  is_enabled: boolean;
  is_default: boolean;
}

const defaultForm: FormData = {
  name: "",
  slug: "",
  summary_type: "executive",
  description: "",
  system_prompt:
    "You are a railway report summarization assistant. Use only provided statistics.",
  user_prompt_template: `Report: {{ metadata.report_name }}
Period: {{ metadata.report_period }}

STATISTICS:
- Total complaints: {{ statistics.total_complaints }}
- Resolved: {{ statistics.resolved_complaints }} ({{ statistics.resolution_rate }}%)

{% for h in statistics.daily_highlights %}- {{ h }}
{% endfor %}

Write a professional summary using only the facts above.`,
  output_format: "markdown",
  max_tokens: 1024,
  temperature: 0.3,
  is_enabled: true,
  is_default: false,
};

export function PromptEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const isNew = !id || id === "new";

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState<FormData>(defaultForm);
  const [activeTab, setActiveTab] = useState("general");

  const loadTemplate = useCallback(async () => {
    if (isNew || !id) return;
    setLoading(true);
    try {
      const t = await summaryApi.getTemplate(id);
      setFormData({
        name: t.name,
        slug: t.slug,
        summary_type: t.summary_type,
        description: t.description ?? "",
        system_prompt: t.system_prompt,
        user_prompt_template: t.user_prompt_template,
        output_format: t.output_format,
        max_tokens: t.max_tokens,
        temperature: t.temperature,
        is_enabled: t.is_enabled,
        is_default: t.is_default,
      });
    } catch {
      showToast("error", "Failed to load template");
      navigate("/admin/prompts");
    } finally {
      setLoading(false);
    }
  }, [id, isNew, navigate, showToast]);

  useEffect(() => {
    loadTemplate();
  }, [loadTemplate]);

  function updateField<K extends keyof FormData>(key: K, value: FormData[K]) {
    setFormData((prev) => ({ ...prev, [key]: value }));
  }

  function generateSlug(name: string) {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .slice(0, 64);
  }

  async function handleSave() {
    if (!formData.name.trim() || !formData.slug.trim()) {
      showToast("error", "Name and slug are required");
      return;
    }
    setSaving(true);
    try {
      if (isNew) {
        await summaryApi.createTemplate(formData);
        showToast("success", "Template created");
      } else {
        await summaryApi.updateTemplate(id!, formData);
        showToast("success", "Template saved");
      }
      navigate("/admin/prompts");
    } catch {
      showToast("error", isNew ? "Failed to create" : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title={isNew ? "New Prompt Template" : "Edit Prompt Template"}
          description={isNew ? "Create a new AI prompt template" : formData.name}
          breadcrumbs={[
            { label: "Admin" },
            { label: "Prompt Templates", href: "/admin/prompts" },
            { label: isNew ? "New" : "Edit" },
          ]}
        />
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => navigate("/admin/prompts")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="prompt">Prompt</TabsTrigger>
          {!isNew ? (
            <TabsTrigger value="test">
              <Play className="mr-1 h-3 w-3" />
              Test
            </TabsTrigger>
          ) : null}
        </TabsList>

        <TabsContent value="general" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>General Settings</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => {
                      updateField("name", e.target.value);
                      if (isNew) updateField("slug", generateSlug(e.target.value));
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slug">Slug</Label>
                  <Input
                    id="slug"
                    value={formData.slug}
                    onChange={(e) => updateField("slug", e.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="summary_type">Summary Type</Label>
                  <Select
                    id="summary_type"
                    value={formData.summary_type}
                    onChange={(e) =>
                      updateField("summary_type", e.target.value as SummaryType)
                    }
                  >
                    {Object.entries(SUMMARY_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="output_format">Output Format</Label>
                  <Select
                    id="output_format"
                    value={formData.output_format}
                    onChange={(e) =>
                      updateField(
                        "output_format",
                        e.target.value as FormData["output_format"],
                      )
                    }
                  >
                    <option value="markdown">Markdown</option>
                    <option value="plain_text">Plain Text</option>
                    <option value="bullets">Bullets</option>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => updateField("description", e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="max_tokens">Max Tokens</Label>
                  <Input
                    id="max_tokens"
                    type="number"
                    min={100}
                    max={4096}
                    value={formData.max_tokens}
                    onChange={(e) =>
                      updateField("max_tokens", parseInt(e.target.value) || 1024)
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="temperature">Temperature</Label>
                  <Input
                    id="temperature"
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={formData.temperature}
                    onChange={(e) =>
                      updateField("temperature", parseFloat(e.target.value) || 0.3)
                    }
                  />
                </div>
              </div>
              <div className="flex gap-6">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.is_enabled}
                    onChange={(e) => updateField("is_enabled", e.target.checked)}
                  />
                  Enabled
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.is_default}
                    onChange={(e) => updateField("is_default", e.target.checked)}
                  />
                  Default for type
                </label>
              </div>
            </CardBody>
          </Card>
        </TabsContent>

        <TabsContent value="prompt" className="mt-6 space-y-6">
          <VariableReference />
          <Card>
            <CardHeader>
              <CardTitle>Prompt Content</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="system_prompt">System Prompt</Label>
                <Textarea
                  id="system_prompt"
                  value={formData.system_prompt}
                  onChange={(e) => updateField("system_prompt", e.target.value)}
                  rows={4}
                  className="font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="user_prompt">User Prompt Template (Jinja2)</Label>
                <Textarea
                  id="user_prompt"
                  value={formData.user_prompt_template}
                  onChange={(e) =>
                    updateField("user_prompt_template", e.target.value)
                  }
                  rows={12}
                  className="font-mono text-sm"
                />
              </div>
            </CardBody>
          </Card>
        </TabsContent>

        {!isNew && id ? (
          <TabsContent value="test" className="mt-6">
            <PromptTestPanel templateId={id} />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  );
}

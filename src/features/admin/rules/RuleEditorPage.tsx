import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Save, Play, AlertTriangle, CheckCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Spinner } from "@/components/ui/Spinner";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/ui/Toast";

import {
  rulesApi,
  RULE_TYPES_BY_CATEGORY,
  type Rule,
  type RuleCategory,
  type CreateRuleRequest,
  type ValidationResult,
  type ConditionGroup,
} from "@/api/rules";
import { ConditionBuilder } from "./components/ConditionBuilder";
import { RuleConfigForm } from "./components/RuleConfigForm";
import { RuleTester } from "./components/RuleTester";

const CATEGORIES = [
  { value: "column", label: "Column Rules" },
  { value: "conditional", label: "Conditional Rules" },
  { value: "sorting", label: "Sorting Rules" },
  { value: "filter", label: "Filter Rules" },
  { value: "top", label: "Top/Limit Rules" },
  { value: "highlight", label: "Highlight Rules" },
  { value: "calculation", label: "Calculation Rules" },
  { value: "merge", label: "Merge Rules" },
];

interface FormData {
  name: string;
  description: string;
  template_id: string;
  category: RuleCategory;
  rule_type: string;
  config: Record<string, unknown>;
  priority: number;
  group_id: string;
  is_enabled: boolean;
  is_global: boolean;
  conditions: ConditionGroup | null;
}

const defaultFormData: FormData = {
  name: "",
  description: "",
  template_id: "",
  category: "column",
  rule_type: "rename",
  config: {},
  priority: 0,
  group_id: "",
  is_enabled: true,
  is_global: false,
  conditions: null,
};

export function RuleEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const isNew = !id;

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("general");
  const [formData, setFormData] = useState<FormData>(defaultFormData);
  const [validation, setValidation] = useState<ValidationResult | null>(null);

  useEffect(() => {
    if (!isNew && id) {
      loadRule(id);
    }
  }, [id, isNew]);

  async function loadRule(ruleId: string) {
    setLoading(true);
    try {
      const rule = await rulesApi.get(ruleId);
      setFormData({
        name: rule.name,
        description: rule.description || "",
        template_id: rule.template_id || "",
        category: rule.category,
        rule_type: rule.rule_type,
        config: rule.config,
        priority: rule.priority,
        group_id: rule.group_id || "",
        is_enabled: rule.is_enabled,
        is_global: rule.is_global,
        conditions: rule.conditions || null,
      });
    } catch (error) {
      showToast({
        type: "error",
        message: "Failed to load rule",
      });
      navigate("/admin/rules");
    } finally {
      setLoading(false);
    }
  }

  function updateFormData<K extends keyof FormData>(key: K, value: FormData[K]) {
    setFormData((prev) => ({
      ...prev,
      [key]: value,
    }));
    setValidation(null);
  }

  function handleCategoryChange(category: RuleCategory) {
    const types = RULE_TYPES_BY_CATEGORY[category];
    updateFormData("category", category);
    updateFormData("rule_type", types[0]?.value || "");
    updateFormData("config", {});
  }

  async function handleValidate() {
    try {
      const result = await rulesApi.validate(
        formData.category,
        formData.rule_type,
        formData.config
      );
      setValidation(result);
      return result.is_valid;
    } catch (error) {
      showToast({
        type: "error",
        message: "Validation failed",
      });
      return false;
    }
  }

  async function handleSave() {
    if (!formData.name.trim()) {
      showToast({
        type: "error",
        message: "Rule name is required",
      });
      return;
    }

    const isValid = await handleValidate();
    if (!isValid) {
      showToast({
        type: "error",
        message: "Please fix validation errors before saving",
      });
      setActiveTab("config");
      return;
    }

    setSaving(true);
    try {
      const payload: CreateRuleRequest = {
        name: formData.name,
        description: formData.description || undefined,
        template_id: formData.template_id || undefined,
        category: formData.category,
        rule_type: formData.rule_type,
        config: formData.config,
        priority: formData.priority,
        group_id: formData.group_id || undefined,
        is_enabled: formData.is_enabled,
        is_global: formData.is_global,
        conditions: formData.conditions || undefined,
      };

      if (isNew) {
        await rulesApi.create(payload);
        showToast({
          type: "success",
          message: "Rule created successfully",
        });
      } else {
        await rulesApi.update(id!, payload);
        showToast({
          type: "success",
          message: "Rule updated successfully",
        });
      }
      navigate("/admin/rules");
    } catch (error) {
      showToast({
        type: "error",
        message: `Failed to ${isNew ? "create" : "update"} rule`,
      });
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

  const ruleTypes = RULE_TYPES_BY_CATEGORY[formData.category] || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={isNew ? "Create Rule" : "Edit Rule"}
        description={isNew ? "Create a new business rule" : `Editing: ${formData.name}`}
        action={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => navigate("/admin/rules")}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              <Save className="mr-2 h-4 w-4" />
              {saving ? "Saving..." : "Save"}
            </Button>
          </div>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="conditions">Conditions</TabsTrigger>
          <TabsTrigger value="test">Test</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>General Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Rule Name *</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => updateFormData("name", e.target.value)}
                    placeholder="Enter rule name"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="priority">Priority</Label>
                  <Input
                    id="priority"
                    type="number"
                    min={0}
                    value={formData.priority}
                    onChange={(e) =>
                      updateFormData("priority", parseInt(e.target.value) || 0)
                    }
                    placeholder="0"
                  />
                  <p className="text-sm text-gray-500">
                    Lower numbers execute first
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => updateFormData("description", e.target.value)}
                  placeholder="Describe what this rule does"
                  rows={3}
                />
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="category">Category *</Label>
                  <Select
                    value={formData.category}
                    onValueChange={(value) =>
                      handleCategoryChange(value as RuleCategory)
                    }
                  >
                    <SelectTrigger id="category">
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map((cat) => (
                        <SelectItem key={cat.value} value={cat.value}>
                          {cat.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="rule_type">Rule Type *</Label>
                  <Select
                    value={formData.rule_type}
                    onValueChange={(value) => {
                      updateFormData("rule_type", value);
                      updateFormData("config", {});
                    }}
                  >
                    <SelectTrigger id="rule_type">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      {ruleTypes.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="group_id">Group ID</Label>
                  <Input
                    id="group_id"
                    value={formData.group_id}
                    onChange={(e) => updateFormData("group_id", e.target.value)}
                    placeholder="Optional group identifier"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="template_id">Template ID</Label>
                  <Input
                    id="template_id"
                    value={formData.template_id}
                    onChange={(e) => updateFormData("template_id", e.target.value)}
                    placeholder="Leave empty for global rules"
                  />
                </div>
              </div>

              <div className="flex gap-8">
                <div className="flex items-center gap-2">
                  <Switch
                    id="is_enabled"
                    checked={formData.is_enabled}
                    onCheckedChange={(checked) =>
                      updateFormData("is_enabled", checked)
                    }
                  />
                  <Label htmlFor="is_enabled">Enabled</Label>
                </div>

                <div className="flex items-center gap-2">
                  <Switch
                    id="is_global"
                    checked={formData.is_global}
                    onCheckedChange={(checked) =>
                      updateFormData("is_global", checked)
                    }
                  />
                  <Label htmlFor="is_global">Global Rule</Label>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="config" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Rule Configuration</CardTitle>
                <Button variant="outline" size="sm" onClick={handleValidate}>
                  Validate
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {validation && (
                <div
                  className={`mb-6 rounded-lg p-4 ${
                    validation.is_valid
                      ? "bg-green-50 text-green-800"
                      : "bg-red-50 text-red-800"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {validation.is_valid ? (
                      <CheckCircle className="h-5 w-5" />
                    ) : (
                      <AlertTriangle className="h-5 w-5" />
                    )}
                    <span className="font-medium">
                      {validation.is_valid
                        ? "Configuration is valid"
                        : "Configuration has errors"}
                    </span>
                  </div>
                  {validation.errors.length > 0 && (
                    <ul className="mt-2 list-inside list-disc">
                      {validation.errors.map((error, i) => (
                        <li key={i}>{error}</li>
                      ))}
                    </ul>
                  )}
                  {validation.warnings.length > 0 && (
                    <ul className="mt-2 list-inside list-disc text-yellow-700">
                      {validation.warnings.map((warning, i) => (
                        <li key={i}>{warning}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <RuleConfigForm
                category={formData.category}
                ruleType={formData.rule_type}
                config={formData.config}
                onChange={(config) => updateFormData("config", config)}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="conditions" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Apply Conditions</CardTitle>
              <p className="text-sm text-gray-500">
                Define when this rule should be applied (optional)
              </p>
            </CardHeader>
            <CardContent>
              <ConditionBuilder
                conditions={formData.conditions}
                onChange={(conditions) => updateFormData("conditions", conditions)}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="test" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Test Rule</CardTitle>
              <p className="text-sm text-gray-500">
                Test this rule against sample data
              </p>
            </CardHeader>
            <CardContent>
              <RuleTester
                ruleConfig={{
                  name: formData.name,
                  category: formData.category,
                  rule_type: formData.rule_type,
                  config: formData.config,
                  conditions: formData.conditions || undefined,
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

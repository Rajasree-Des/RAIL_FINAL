import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, MoreVertical, Edit, Copy, Trash2, Bot } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { AdminListToolbar } from "@/components/admin/AdminListToolbar";
import { ConfirmDialog } from "@/components/admin/ConfirmDialog";
import { DuplicateNameDialog } from "@/components/admin/DuplicateNameDialog";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { useToast } from "@/components/ui/Toast";
import {
  summaryApi,
  SUMMARY_TYPE_LABELS,
  type PromptTemplateListItem,
  type SummaryType,
} from "@/api/summary";

export function PromptListPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [templates, setTemplates] = useState<PromptTemplateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [deleteTarget, setDeleteTarget] = useState<PromptTemplateListItem | null>(null);
  const [duplicateTarget, setDuplicateTarget] = useState<PromptTemplateListItem | null>(null);
  const [duplicateName, setDuplicateName] = useState("");

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const response = await summaryApi.listTemplates();
      setTemplates(response.templates);
    } catch {
      showToast("error", "Failed to load prompt templates");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const filtered = templates.filter((t) => {
    const q = searchQuery.toLowerCase();
    const matchesSearch =
      t.name.toLowerCase().includes(q) ||
      t.slug.toLowerCase().includes(q) ||
      (t.description?.toLowerCase().includes(q) ?? false);
    const matchesType = typeFilter === "all" || t.summary_type === typeFilter;
    return matchesSearch && matchesType;
  });

  async function handleToggle(template: PromptTemplateListItem) {
    try {
      const result = await summaryApi.toggleTemplate(template.id);
      setTemplates((prev) =>
        prev.map((t) =>
          t.id === template.id ? { ...t, is_enabled: result.is_enabled } : t,
        ),
      );
      showToast("success", result.is_enabled ? "Template enabled" : "Template disabled");
    } catch {
      showToast("error", "Failed to toggle template");
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await summaryApi.deleteTemplate(deleteTarget.id);
      showToast("success", "Template deleted");
      setDeleteTarget(null);
      loadTemplates();
    } catch {
      showToast("error", "Failed to delete template");
    }
  }

  async function handleDuplicate() {
    if (!duplicateTarget || !duplicateName.trim()) return;
    try {
      const created = await summaryApi.duplicateTemplate(
        duplicateTarget.id,
        duplicateName.trim(),
      );
      showToast("success", "Template duplicated");
      setDuplicateTarget(null);
      navigate(`/admin/prompts/${created.id}/edit`);
    } catch {
      showToast("error", "Failed to duplicate template");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="AI Prompt Templates"
          description="Manage configurable prompts for AI summary generation"
          breadcrumbs={[{ label: "Admin" }, { label: "Prompt Templates" }]}
        />
        <Link to="/admin/prompts/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Template
          </Button>
        </Link>
      </div>

      <AdminListToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search templates..."
        createLabel="New Template"
        onCreate={() => navigate("/admin/prompts/new")}
        filterSlot={
          <Select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="w-full md:w-48"
          >
            <option value="all">All Types</option>
            {Object.entries(SUMMARY_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        }
      />

      <Card>
        <CardBody>
          {loading ? (
            <div className="flex justify-center py-12">
              <Spinner size="lg" />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={Bot}
              title="No prompt templates"
              description="Create your first AI prompt template."
              action={
                <Link to="/admin/prompts/new">
                  <Button>Create Template</Button>
                </Link>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="pb-3 font-medium">Name</th>
                    <th className="pb-3 font-medium">Type</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Default</th>
                    <th className="pb-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((template) => (
                    <tr key={template.id} className="border-b last:border-0">
                      <td className="py-3">
                        <Link
                          to={`/admin/prompts/${template.id}/edit`}
                          className="font-medium text-slate-900 hover:text-primary"
                        >
                          {template.name}
                        </Link>
                        <p className="text-xs text-slate-500">{template.slug}</p>
                      </td>
                      <td className="py-3">
                        {SUMMARY_TYPE_LABELS[template.summary_type as SummaryType]}
                      </td>
                      <td className="py-3">
                        <StatusBadge variant={template.is_enabled ? "success" : "neutral"}>
                          {template.is_enabled ? "Enabled" : "Disabled"}
                        </StatusBadge>
                      </td>
                      <td className="py-3">
                        {template.is_default ? (
                          <StatusBadge variant="info">Default</StatusBadge>
                        ) : null}
                      </td>
                      <td className="py-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => navigate(`/admin/prompts/${template.id}/edit`)}
                            >
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => {
                                setDuplicateTarget(template);
                                setDuplicateName(`${template.name} (Copy)`);
                              }}
                            >
                              <Copy className="mr-2 h-4 w-4" />
                              Duplicate
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleToggle(template)}>
                              {template.is_enabled ? "Disable" : "Enable"}
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-red-600"
                              onClick={() => setDeleteTarget(template)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={() => setDeleteTarget(null)}
        title="Delete Template"
        description={
          <>Delete &ldquo;{deleteTarget?.name}&rdquo;? This cannot be undone.</>
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />

      <DuplicateNameDialog
        open={!!duplicateTarget}
        onOpenChange={() => setDuplicateTarget(null)}
        sourceName={duplicateTarget?.name}
        name={duplicateName}
        onNameChange={setDuplicateName}
        onConfirm={handleDuplicate}
        title="Duplicate Template"
      />
    </div>
  );
}

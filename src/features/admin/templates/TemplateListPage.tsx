import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  MoreVertical,
  Edit,
  Copy,
  Trash2,
  ToggleLeft,
  ToggleRight,
  FileText,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { AdminListToolbar } from "@/components/admin/AdminListToolbar";
import { ConfirmDialog } from "@/components/admin/ConfirmDialog";
import { DuplicateNameDialog } from "@/components/admin/DuplicateNameDialog";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { templatesApi, type TemplateListItem } from "@/api/templates";

export function TemplateListPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [templates, setTemplates] = useState<TemplateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "enabled" | "disabled">("all");

  const [deleteDialog, setDeleteDialog] = useState<{ open: boolean; template: TemplateListItem | null }>({
    open: false,
    template: null,
  });
  const [duplicateDialog, setDuplicateDialog] = useState<{
    open: boolean;
    template: TemplateListItem | null;
    newName: string;
  }>({
    open: false,
    template: null,
    newName: "",
  });

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const response = await templatesApi.list();
      setTemplates(response.templates);
    } catch {
      showToast("error", "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const filteredTemplates = templates.filter((template) => {
    const matchesSearch =
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "enabled" && template.is_enabled) ||
      (statusFilter === "disabled" && !template.is_enabled);

    return matchesSearch && matchesStatus;
  });

  const handleToggle = async (template: TemplateListItem) => {
    try {
      const result = await templatesApi.toggle(template.id);
      setTemplates((prev) =>
        prev.map((t) => (t.id === template.id ? { ...t, is_enabled: result.is_enabled } : t)),
      );
      showToast("success", result.message);
    } catch {
      showToast("error", "Failed to toggle template");
    }
  };

  const handleDelete = async () => {
    if (!deleteDialog.template) return;

    try {
      await templatesApi.delete(deleteDialog.template.id);
      setTemplates((prev) => prev.filter((t) => t.id !== deleteDialog.template?.id));
      showToast("success", "Template deleted successfully");
      setDeleteDialog({ open: false, template: null });
    } catch {
      showToast("error", "Failed to delete template");
    }
  };

  const handleDuplicate = async () => {
    if (!duplicateDialog.template || !duplicateDialog.newName.trim()) return;

    try {
      const newTemplate = await templatesApi.duplicate(
        duplicateDialog.template.id,
        duplicateDialog.newName.trim(),
      );
      setTemplates((prev) => [
        ...prev,
        {
          id: newTemplate.id,
          name: newTemplate.name,
          slug: newTemplate.slug,
          description: newTemplate.description,
          source_report_id: newTemplate.source_report_id,
          is_enabled: newTemplate.is_enabled,
          version: newTemplate.version,
          created_at: newTemplate.created_at,
          updated_at: newTemplate.updated_at,
          has_input_config: !!newTemplate.input_config,
          has_output_config: !!newTemplate.output_config,
          column_count: newTemplate.column_mappings.length,
        },
      ]);
      showToast("success", "Template duplicated successfully");
      setDuplicateDialog({ open: false, template: null, newName: "" });
    } catch {
      showToast("error", "Failed to duplicate template");
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  return (
    <div>
      <PageHeader
        title="Report Templates"
        description="Configure and manage report generation templates"
        breadcrumbs={[{ label: "Admin" }, { label: "Templates" }]}
      />

      <AdminListToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search templates..."
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        createLabel="Create Template"
        onCreate={() => navigate("/admin/templates/new")}
      />

      <Card>
        <CardBody>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner size="lg" />
            </div>
          ) : filteredTemplates.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No templates found"
              description={
                searchQuery || statusFilter !== "all"
                  ? "No templates match your current filters."
                  : "Get started by creating your first report template."
              }
              action={
                !searchQuery && statusFilter === "all" ? (
                  <Button variant="primary" onClick={() => navigate("/admin/templates/new")}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Template
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-600">
                      Template
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-600">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-600">
                      Columns
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-600">
                      Version
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-600">
                      Updated
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTemplates.map((template) => (
                    <tr key={template.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-slate-900">{template.name}</p>
                          <p className="text-xs text-slate-500">{template.slug}</p>
                          {template.description && (
                            <p className="mt-1 line-clamp-1 text-xs text-slate-500">
                              {template.description}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge variant={template.is_enabled ? "success" : "neutral"}>
                          {template.is_enabled ? "Enabled" : "Disabled"}
                        </StatusBadge>
                      </td>
                      <td className="px-4 py-3 text-slate-700">{template.column_count}</td>
                      <td className="px-4 py-3 text-slate-700">v{template.version}</td>
                      <td className="px-4 py-3 text-slate-500">{formatDate(template.updated_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => navigate(`/admin/templates/${template.id}/edit`)}
                            >
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() =>
                                setDuplicateDialog({
                                  open: true,
                                  template,
                                  newName: `${template.name} (Copy)`,
                                })
                              }
                            >
                              <Copy className="mr-2 h-4 w-4" />
                              Duplicate
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleToggle(template)}>
                              {template.is_enabled ? (
                                <>
                                  <ToggleLeft className="mr-2 h-4 w-4" />
                                  Disable
                                </>
                              ) : (
                                <>
                                  <ToggleRight className="mr-2 h-4 w-4" />
                                  Enable
                                </>
                              )}
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => setDeleteDialog({ open: true, template })}
                              className="text-red-600"
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

          <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-4">
            <p className="text-sm text-slate-500">
              Showing {filteredTemplates.length} of {templates.length} templates
            </p>
          </div>
        </CardBody>
      </Card>

      <ConfirmDialog
        open={deleteDialog.open}
        onOpenChange={(open) => setDeleteDialog({ open, template: null })}
        title="Delete Template"
        description={
          <>
            Are you sure you want to delete &ldquo;{deleteDialog.template?.name}&rdquo;? This action
            cannot be undone.
          </>
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />

      <DuplicateNameDialog
        open={duplicateDialog.open}
        onOpenChange={(open) =>
          setDuplicateDialog({ open, template: null, newName: "" })
        }
        sourceName={duplicateDialog.template?.name}
        name={duplicateDialog.newName}
        onNameChange={(newName) => setDuplicateDialog((prev) => ({ ...prev, newName }))}
        onConfirm={handleDuplicate}
        title="Duplicate Template"
        nameLabel="New Template Name"
      />
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Plus,
  Search,
  MoreVertical,
  Edit,
  Copy,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Settings2,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/ui/Toast";

import { rulesApi, type RuleListItem, type RuleCategory } from "@/api/rules";

const CATEGORY_OPTIONS = [
  { value: "all", label: "All Categories" },
  { value: "column", label: "Column Rules" },
  { value: "conditional", label: "Conditional Rules" },
  { value: "sorting", label: "Sorting Rules" },
  { value: "filter", label: "Filter Rules" },
  { value: "top", label: "Top/Limit Rules" },
  { value: "highlight", label: "Highlight Rules" },
  { value: "calculation", label: "Calculation Rules" },
  { value: "merge", label: "Merge Rules" },
];

const STATUS_OPTIONS = [
  { value: "all", label: "All Status" },
  { value: "enabled", label: "Enabled" },
  { value: "disabled", label: "Disabled" },
];

export function RuleListPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [rules, setRules] = useState<RuleListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [ruleToDelete, setRuleToDelete] = useState<RuleListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [ruleToDuplicate, setRuleToDuplicate] = useState<RuleListItem | null>(null);
  const [duplicateName, setDuplicateName] = useState("");
  const [isDuplicating, setIsDuplicating] = useState(false);

  useEffect(() => {
    loadRules();
  }, [categoryFilter, statusFilter]);

  async function loadRules() {
    setLoading(true);
    try {
      const params: { category?: string; is_enabled?: boolean } = {};
      if (categoryFilter !== "all") {
        params.category = categoryFilter;
      }
      if (statusFilter === "enabled") {
        params.is_enabled = true;
      } else if (statusFilter === "disabled") {
        params.is_enabled = false;
      }

      const response = await rulesApi.list(params);
      setRules(response.rules);
    } catch (error) {
      showToast({
        type: "error",
        message: "Failed to load rules",
      });
    } finally {
      setLoading(false);
    }
  }

  const filteredRules = rules.filter((rule) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      rule.name.toLowerCase().includes(query) ||
      rule.description?.toLowerCase().includes(query) ||
      rule.rule_type.toLowerCase().includes(query)
    );
  });

  async function handleToggle(rule: RuleListItem) {
    try {
      await rulesApi.toggle(rule.id);
      showToast({
        type: "success",
        message: `Rule ${rule.is_enabled ? "disabled" : "enabled"}`,
      });
      loadRules();
    } catch (error) {
      showToast({
        type: "error",
        message: "Failed to toggle rule",
      });
    }
  }

  async function handleDelete() {
    if (!ruleToDelete) return;

    setIsDeleting(true);
    try {
      await rulesApi.delete(ruleToDelete.id);
      showToast({
        type: "success",
        message: "Rule deleted",
      });
      setDeleteDialogOpen(false);
      setRuleToDelete(null);
      loadRules();
    } catch (error) {
      showToast({
        type: "error",
        message: "Failed to delete rule",
      });
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleDuplicate() {
    if (!ruleToDuplicate || !duplicateName.trim()) return;

    setIsDuplicating(true);
    try {
      const newRule = await rulesApi.duplicate(ruleToDuplicate.id, duplicateName.trim());
      showToast({
        type: "success",
        message: "Rule duplicated",
      });
      setDuplicateDialogOpen(false);
      setRuleToDuplicate(null);
      setDuplicateName("");
      navigate(`/admin/rules/${newRule.id}/edit`);
    } catch (error) {
      showToast({
        type: "error",
        message: "Failed to duplicate rule",
      });
    } finally {
      setIsDuplicating(false);
    }
  }

  function openDuplicateDialog(rule: RuleListItem) {
    setRuleToDuplicate(rule);
    setDuplicateName(`${rule.name} (Copy)`);
    setDuplicateDialogOpen(true);
  }

  function getCategoryLabel(category: string): string {
    const option = CATEGORY_OPTIONS.find((c) => c.value === category);
    return option?.label || category;
  }

  function formatRuleType(type: string): string {
    return type
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Business Rules"
        description="Configure and manage data processing rules"
        action={
          <Link to="/admin/rules/new">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Rule
            </Button>
          </Link>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <Input
                placeholder="Search rules..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex gap-3">
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Spinner size="lg" />
            </div>
          ) : filteredRules.length === 0 ? (
            <EmptyState
              icon={Settings2}
              title="No rules found"
              description={
                searchQuery
                  ? "No rules match your search criteria"
                  : "Create your first business rule to get started"
              }
              action={
                !searchQuery && (
                  <Link to="/admin/rules/new">
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Rule
                    </Button>
                  </Link>
                )
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="pb-3 font-medium">Name</th>
                    <th className="pb-3 font-medium">Category</th>
                    <th className="pb-3 font-medium">Type</th>
                    <th className="pb-3 font-medium">Priority</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Global</th>
                    <th className="pb-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRules.map((rule) => (
                    <tr key={rule.id} className="border-b last:border-0">
                      <td className="py-4">
                        <div>
                          <Link
                            to={`/admin/rules/${rule.id}/edit`}
                            className="font-medium text-gray-900 hover:text-primary"
                          >
                            {rule.name}
                          </Link>
                          {rule.description && (
                            <p className="text-sm text-gray-500 line-clamp-1">
                              {rule.description}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="py-4">
                        <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800">
                          {getCategoryLabel(rule.category)}
                        </span>
                      </td>
                      <td className="py-4 text-sm text-gray-600">
                        {formatRuleType(rule.rule_type)}
                      </td>
                      <td className="py-4 text-sm text-gray-600">{rule.priority}</td>
                      <td className="py-4">
                        <StatusBadge
                          variant={rule.is_enabled ? "success" : "secondary"}
                        >
                          {rule.is_enabled ? "Enabled" : "Disabled"}
                        </StatusBadge>
                      </td>
                      <td className="py-4">
                        {rule.is_global && (
                          <StatusBadge variant="info">Global</StatusBadge>
                        )}
                      </td>
                      <td className="py-4 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => navigate(`/admin/rules/${rule.id}/edit`)}
                            >
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openDuplicateDialog(rule)}>
                              <Copy className="mr-2 h-4 w-4" />
                              Duplicate
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleToggle(rule)}>
                              {rule.is_enabled ? (
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
                              onClick={() => {
                                setRuleToDelete(rule);
                                setDeleteDialogOpen(true);
                              }}
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
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Rule</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{ruleToDelete?.name}&rdquo;? This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Duplicate Dialog */}
      <Dialog open={duplicateDialogOpen} onOpenChange={setDuplicateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Duplicate Rule</DialogTitle>
            <DialogDescription>
              Enter a name for the duplicated rule.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              value={duplicateName}
              onChange={(e) => setDuplicateName(e.target.value)}
              placeholder="New rule name"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDuplicateDialogOpen(false)}
              disabled={isDuplicating}
            >
              Cancel
            </Button>
            <Button
              onClick={handleDuplicate}
              disabled={isDuplicating || !duplicateName.trim()}
            >
              {isDuplicating ? "Duplicating..." : "Duplicate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

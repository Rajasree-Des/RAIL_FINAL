import { Filter, Plus, Search } from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import type { ReactNode } from "react";

interface AdminListToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  createLabel: string;
  onCreate: () => void;
  statusFilter?: "all" | "enabled" | "disabled";
  onStatusFilterChange?: (value: "all" | "enabled" | "disabled") => void;
  filterSlot?: ReactNode;
}

export function AdminListToolbar({
  searchQuery,
  onSearchChange,
  searchPlaceholder = "Search...",
  createLabel,
  onCreate,
  statusFilter,
  onStatusFilterChange,
  filterSlot,
}: AdminListToolbarProps) {
  return (
    <Card className="mb-6">
      <CardBody>
        <div className="flex flex-wrap items-center gap-4">
          <div className="relative min-w-[200px] flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input
              placeholder={searchPlaceholder}
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-10"
            />
          </div>
          {filterSlot}
          {statusFilter !== undefined && onStatusFilterChange && (
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-400" />
              <Select
                value={statusFilter}
                onChange={(e) =>
                  onStatusFilterChange(e.target.value as "all" | "enabled" | "disabled")
                }
                className="w-32"
              >
                <option value="all">All Status</option>
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </Select>
            </div>
          )}
          <Button variant="primary" onClick={onCreate}>
            <Plus className="mr-2 h-4 w-4" />
            {createLabel}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

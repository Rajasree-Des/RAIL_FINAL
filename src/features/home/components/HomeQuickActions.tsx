import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";
import { QUICK_ACTIONS } from "@/features/home/homeData";
import { usePermissions } from "@/hooks/usePermissions";

export function HomeQuickActions() {
  const { canViewLogs, canViewReports } = usePermissions();

  const visible = QUICK_ACTIONS.filter((action) => {
    if (action.permission === "logs") return canViewLogs;
    if (action.permission === "reports") return canViewReports;
    return true;
  });

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-rail-ink">Quick Actions</h2>
        <p className="mt-1 text-sm text-rail-muted">Navigate to common tasks</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((action) => {
          const Icon = action.icon;
          return (
            <Link key={action.path} to={action.path} className="group block">
              <Card className="h-full hover:-translate-y-0.5 hover:shadow-premium">
                <CardBody className="flex items-center gap-4 p-5">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface transition-colors group-hover:bg-primary/8">
                    <Icon className="h-4 w-4 text-rail-muted group-hover:text-primary" strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-1 text-sm font-medium text-rail-ink">
                      {action.label}
                      <ChevronRight className="h-3.5 w-3.5 text-rail-muted opacity-0 transition-opacity group-hover:opacity-100" />
                    </p>
                    <p className="mt-0.5 truncate text-xs text-rail-muted">{action.description}</p>
                  </div>
                </CardBody>
              </Card>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

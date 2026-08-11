import { Link } from "react-router-dom";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/utils/cn";
import { SCHEDULED_REPORTS } from "@/features/home/homeData";

interface HomeReportChecklistProps {
  reports?: typeof SCHEDULED_REPORTS;
}

export function HomeReportChecklist({ reports = SCHEDULED_REPORTS }: HomeReportChecklistProps) {
  return (
    <Card className="h-full hover:shadow-premium">
      <CardHeader className="border-b border-rail-line pb-4">
        <CardTitle className="text-base font-semibold text-[#1F2937]">Today&apos;s Reports</CardTitle>
        <p className="text-xs text-[#64748B]">{reports.length} scheduled for today</p>
      </CardHeader>
      <CardBody className="space-y-2 p-4">
        {reports.map((report) => {
          const Icon = report.icon;
          return (
            <Link
              key={report.id}
              to={report.path}
              className="group flex items-center gap-3 rounded-lg border border-transparent p-3 transition-all duration-200 hover:border-rail-line hover:bg-[#F7F8FA] hover:shadow-soft"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/5 transition-colors group-hover:bg-primary/10">
                <Icon className="h-4 w-4 text-primary" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-snug break-words text-[#1F2937]">
                  {report.name}
                </p>
                <p className="text-xs text-[#64748B]">{report.duration}</p>
              </div>
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                  report.status === "Generated"
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-[#F7F8FA] text-[#64748B]",
                )}
              >
                {report.status}
              </span>
            </Link>
          );
        })}
      </CardBody>
    </Card>
  );
}

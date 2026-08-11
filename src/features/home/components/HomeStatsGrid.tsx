import type { LucideIcon } from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";
import { cn } from "@/utils/cn";

interface StatMetric {
  icon: LucideIcon;
  title: string;
  value: string;
  description: string;
  accent?: boolean;
}

interface HomeStatsGridProps {
  metrics: StatMetric[];
}

export function HomeStatsGrid({ metrics }: HomeStatsGridProps) {
  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <Card
            key={metric.title}
            className="hover:-translate-y-0.5 hover:shadow-premium"
          >
            <CardBody className="p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface">
                <Icon className="h-4 w-4 text-rail-muted" strokeWidth={1.75} />
              </div>
              <p className="mt-5 text-xs font-medium text-rail-muted">{metric.title}</p>
              <p
                className={cn(
                  "mt-1 text-2xl font-semibold tracking-tight",
                  metric.accent ? "text-accent" : "text-rail-ink",
                )}
              >
                {metric.value}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-rail-muted">{metric.description}</p>
            </CardBody>
          </Card>
        );
      })}
    </section>
  );
}

import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { GENERATION_PIPELINE } from "@/features/home/homeData";
import { cn } from "@/utils/cn";

interface HomeGenerationTimelineProps {
  activeStep?: number;
  isRunning?: boolean;
}

export function HomeGenerationTimeline({
  activeStep = 0,
  isRunning = false,
}: HomeGenerationTimelineProps) {
  return (
    <Card className="hover:shadow-premium">
      <CardHeader className="border-b border-rail-line pb-4">
        <CardTitle className="text-base font-semibold text-[#1F2937]">
          Today&apos;s Report Generation
        </CardTitle>
        <p className="text-xs text-[#64748B]">Standard daily pipeline</p>
      </CardHeader>
      <CardBody className="p-6">
        <ol className="space-y-0" role="list">
          {GENERATION_PIPELINE.map((item, index) => {
            const isActive = isRunning && activeStep === item.step;
            const isComplete = isRunning && activeStep > item.step;
            const isLast = index === GENERATION_PIPELINE.length - 1;

            return (
              <li key={item.step} className="relative flex gap-4">
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold transition-all duration-300",
                      isComplete && "border-emerald-500 bg-emerald-500 text-white",
                      isActive && "border-primary bg-primary text-white shadow-soft",
                      !isComplete && !isActive && "border-rail-line bg-white text-[#64748B]",
                    )}
                  >
                    {isComplete ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : isActive ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      item.step
                    )}
                  </div>
                  {!isLast && (
                    <div
                      className={cn(
                        "my-1 w-0.5 flex-1 min-h-[28px] transition-colors duration-300",
                        isComplete ? "bg-emerald-400" : "bg-rail-line",
                      )}
                    />
                  )}
                </div>
                <div className={cn("pb-8", isLast && "pb-0")}>
                  <p
                    className={cn(
                      "text-sm font-medium transition-colors duration-200",
                      isActive ? "text-primary" : isComplete ? "text-[#1F2937]" : "text-[#64748B]",
                    )}
                  >
                    {item.label}
                  </p>
                  {isActive && (
                    <p className="mt-0.5 text-xs text-primary/80 animate-fade-in">In progress…</p>
                  )}
                  {isComplete && (
                    <p className="mt-0.5 text-xs text-emerald-600">Completed</p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </CardBody>
    </Card>
  );
}

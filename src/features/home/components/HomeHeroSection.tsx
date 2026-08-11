import { CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";

interface HomeHeroSectionProps {
  isAdmin: boolean;
  isStarting: boolean;
  reportCount: number;
  onGenerate: () => void;
  disabled?: boolean;
}

export function HomeHeroSection({
  isAdmin,
  isStarting,
  reportCount,
  onGenerate,
  disabled,
}: HomeHeroSectionProps) {
  return (
    <Card className="h-full hover:shadow-premium">
      <CardBody className="p-8 lg:p-10">
        <p className="text-xs font-medium uppercase tracking-wider text-[#64748B]">
          Today&apos;s Reporting Status
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#1F2937] lg:text-4xl">
          Generate Today&apos;s Reports
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-[#64748B]">
          Generate all scheduled RailMadad reports for today. Your dashboard, analytics and report
          files will automatically be updated.
        </p>

        {isAdmin ? (
          <Button
            size="lg"
            className="mt-8 h-12 px-8 text-base shadow-card transition-all duration-200 hover:shadow-premium active:scale-[0.98]"
            onClick={onGenerate}
            disabled={disabled || isStarting}
          >
            {isStarting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Starting generation…
              </>
            ) : (
              "Generate Today's Reports"
            )}
          </Button>
        ) : (
          <p className="mt-8 text-sm text-[#64748B]">
            Contact your administrator to generate today&apos;s reports.
          </p>
        )}

        <ul className="mt-8 space-y-2.5 text-sm text-[#64748B]">
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-primary/60" />
            <span>
              <span className="font-medium text-[#1F2937]">{reportCount} Reports</span> Scheduled
            </span>
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-primary/60" />
            <span>
              Estimated Time:{" "}
              <span className="font-medium text-[#1F2937]">2–3 Minutes</span>
            </span>
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-primary/60" />
            <span>
              Last Generated:{" "}
              <span className="font-medium text-[#1F2937]">Yesterday 5:42 PM</span>
            </span>
          </li>
        </ul>
      </CardBody>
    </Card>
  );
}

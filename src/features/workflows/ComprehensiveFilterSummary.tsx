import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import {
  PORTAL_TAB,
  PORTAL_VIEW,
  PORTAL_ZONE,
  SECTIONS,
} from "@/features/workflows/comprehensiveConstants";

function FilterRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}

export function ComprehensiveFilterSummary() {
  return (
    <Card className="border border-rail-line">
      <CardHeader className="border-b border-rail-line">
        <CardTitle>Portal filter summary</CardTitle>
        <CardDescription>
          Read-only RailMadad settings applied during generation
        </CardDescription>
      </CardHeader>
      <CardBody className="grid gap-4 p-6 sm:grid-cols-2">
        {SECTIONS.map((section) => (
          <div
            key={section.id}
            className="rounded-xl border border-rail-line bg-surface/40 p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {section.validationName}
            </p>
            <dl className="mt-3 space-y-2 text-sm text-slate-800">
              <FilterRow label="Tab" value={PORTAL_TAB} />
              <FilterRow label="Zone" value={PORTAL_ZONE} />
              <FilterRow label="Department" value={section.department} />
              <FilterRow label="Mode" value={section.mode} />
              <FilterRow label="Type" value={section.complaintType} />
              <FilterRow label="View" value={PORTAL_VIEW} />
            </dl>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

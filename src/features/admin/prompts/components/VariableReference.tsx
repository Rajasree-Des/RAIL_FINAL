export function VariableReference() {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
      <p className="mb-2 font-medium text-slate-700">Available Jinja2 variables</p>
      <ul className="list-inside list-disc space-y-1 text-slate-600">
        <li>
          <code>metadata.report_name</code>, <code>metadata.report_period</code>,{" "}
          <code>metadata.division</code>, <code>metadata.included_reports</code>
        </li>
        <li>
          <code>statistics.total_complaints</code>,{" "}
          <code>statistics.resolved_complaints</code>,{" "}
          <code>statistics.pending_complaints</code>,{" "}
          <code>statistics.resolution_rate</code>
        </li>
        <li>
          <code>statistics.daily_highlights</code>,{" "}
          <code>statistics.key_observations</code>,{" "}
          <code>statistics.top_complaint_types</code>
        </li>
        <li>
          <code>preview</code> — truncated dataset text
        </li>
      </ul>
      <p className="mt-2 text-xs text-slate-500">
        Loop example:{" "}
        <code>{`{% for h in statistics.daily_highlights %}- {{ h }}{% endfor %}`}</code>
      </p>
    </div>
  );
}

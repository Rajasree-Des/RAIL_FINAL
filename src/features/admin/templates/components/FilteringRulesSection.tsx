import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import type { FilteringRule } from "@/api/templates";
import type { ColumnMetadata } from "@/features/report-config/types";
import { FilterBuilder } from "@/features/report-config/components/FilterBuilder";
import {
  conditionsToFilteringRules,
  filteringRulesToConditions,
} from "@/features/report-config/adapters";

interface FilteringRulesSectionProps {
  data: FilteringRule[];
  columns: ColumnMetadata[];
  onChange: (data: FilteringRule[]) => void;
  loading?: boolean;
  error?: string | null;
}

export function FilteringRulesSection({
  data,
  columns,
  onChange,
  loading = false,
  error = null,
}: FilteringRulesSectionProps) {
  const conditions = filteringRulesToConditions(data, columns);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Filtering Rules</CardTitle>
        <CardDescription>
          Filter the original RailMadad dataset using dynamically discovered Excel columns
        </CardDescription>
      </CardHeader>
      <CardBody>
        <FilterBuilder
          columns={columns}
          conditions={conditions}
          onChange={(nextConditions) => onChange(conditionsToFilteringRules(nextConditions, columns))}
          loading={loading}
          error={error}
          title="Dataset Filters"
          description="All filters apply to the complete original dataset before report generation"
        />
      </CardBody>
    </Card>
  );
}
